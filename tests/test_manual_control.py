from copy import deepcopy
import time
import unittest
from unittest.mock import MagicMock, patch

from ricca_dglab.manual_control import ManualPlayback
import test_channel_backend as fixture


class ManualPlaybackTests(unittest.TestCase):
    def test_explicit_start_validation_caps_and_expiry(self):
        playback = ManualPlayback()
        args = (50, "wave", 0, "wave", 30)
        self.assertFalse(playback.start(*args, now=10, cap=20, waves={"wave"}))
        playback.enabled = True
        self.assertTrue(playback.start(*args, now=10, cap=20, waves={"wave"}))
        self.assertEqual(playback.strength_a, 20)
        playback.check(now=40)
        self.assertFalse(playback.running)
        self.assertEqual(playback.reason, "manual-timeout")
        playback.check(now=41)
        self.assertFalse(playback.running)

    def test_invalid_start_is_not_an_authorization(self):
        for a, wave, seconds in ((-1,"wave",30),(101,"wave",30),(10,"missing",30),
                                  (10,"wave",0),(10,"wave",301),(float("nan"),"wave",30)):
            playback = ManualPlayback(enabled=True)
            self.assertFalse(playback.start(a,wave,0,"wave",seconds,now=10,cap=50,waves={"wave"}))
            self.assertFalse(playback.running)

    def test_blocker_cancels_not_suspends(self):
        playback = ManualPlayback(enabled=True)
        playback.start(10,"wave",0,"wave",300,now=10,cap=50,waves={"wave"})
        playback.check(now=11, blocker="disconnected")
        playback.check(now=12)
        self.assertFalse(playback.running)
        self.assertEqual(playback.summary(12)["strength_a"],0)


class ManualBackendTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    tearDown = fixture.ChannelBackendTests.tearDown

    def setUp(self):
        fixture.ChannelBackendTests.setUp(self)
        self.backend._bridge = MagicMock(connected=True)
        self.backend._ovc_bridge = MagicMock(connected=True)
        self.backend._v4_hub = MagicMock()
        self.backend._device_connected = self.backend._ovc_connected = True
        self.backend._stop_latched = self.backend._user_output_paused = False
        self.backend._pulse_route_paused = self.backend._ovc_route_paused = False

    def start(self, device, a=10, b=0, seconds=30):
        backend = self.backend
        catalog = backend.ovcController.waveformCatalog if device == "ovc" else backend.waveformCatalog
        wave = catalog[0]["key"]
        self.assertTrue(backend.setManualMode(device,True))
        self.assertTrue(backend.startManualOutput(device,a,wave,b,wave,seconds))
        return backend._manual_playback[device]

    def test_absent_game_or_failed_telemetry_does_not_block_manual(self):
        original = deepcopy(self.backend._config.values)
        self.backend._state = {"status":"error"}
        self.backend._reader_error = "read failed"
        self.backend._last_received = 0
        for device in ("coyote","ovc"):
            self.start(device)
        self.backend._drain()
        for device, sender in (("coyote",self.backend._bridge),("ovc",self.backend._ovc_bridge)):
            self.assertTrue(self.backend._manual_playback[device].running)
            self.assertEqual(sender.update_auto_outputs.call_args.args[0],10)
            self.assertEqual(sender.update_auto_outputs.call_args.kwargs["strength_b"],0)
            self.assertTrue(sender.set_auto_enabled.call_args.args[0])
        self.assertEqual(self.backend._config.values,original)

    def test_timeout_and_route_stop_are_independent(self):
        pulse, vibration = self.start("coyote"), self.start("ovc")
        pulse.deadline = time.monotonic()-1
        self.backend._sync_manual_output("coyote",time.monotonic())
        self.assertFalse(pulse.running)
        self.assertTrue(vibration.running)
        self.backend.stopManualOutput("ovc")
        self.assertFalse(vibration.running)
        self.assertTrue(vibration.enabled)

    def test_global_pause_and_emergency_require_a_new_start(self):
        for device in ("coyote","ovc"):
            self.start(device)
        self.backend.toggleOutputPause()
        self.assertFalse(any(p.running for p in self.backend._manual_playback.values()))
        self.backend.toggleOutputPause()
        self.assertFalse(any(p.running for p in self.backend._manual_playback.values()))
        self.start("ovc")
        self.backend.emergencyStop()
        self.assertFalse(self.backend._manual_playback["ovc"].running)
        self.assertFalse(self.backend.manualOutputs["ovc"]["can_start"])

    def test_vibration_quantization_and_wrong_device_wave_rejected(self):
        playback = self.start("ovc",a=19)
        self.assertEqual(playback.strength_a,10)
        self.backend.stopManualOutput("ovc")
        wave = self.backend.waveformCatalog[0]["key"]
        self.assertFalse(self.backend.startManualOutput("ovc",10,wave,0,wave,30))
        self.assertFalse(playback.running)
        self.assertFalse(self.backend.startManualOutput("ovc",9,"ovc_pinpoint",0,"ovc_pinpoint",30))

    def test_vibration_manual_allows_200_without_extending_coyote(self):
        self.backend._config.values["ovc_profile"]["hard_cap"] = 200
        playback = self.start("ovc", a=200)
        self.assertEqual(playback.strength_a, 200)
        self.backend.stopManualOutput("ovc")
        self.assertEqual(self.start("ovc", a=199).strength_a, 190)
        self.assertFalse(self.backend.startManualOutput("coyote", 200, "impact", 0, "impact", 30))

    def test_disconnect_reconnect_in_same_drain_does_not_resume(self):
        self.start("ovc")
        self.backend._apply_bridge({"event":"disconnected","role":"ovc"})
        self.backend._apply_bridge({"event":"connected","role":"ovc"})
        self.backend._sync_ovc_output(time.monotonic())
        self.assertFalse(self.backend._manual_playback["ovc"].running)

    def test_return_to_auto_is_zero_and_route_paused(self):
        self.start("coyote")
        self.backend.setManualMode("coyote",False)
        self.assertTrue(self.backend.pulseRoutePaused)
        self.assertFalse(self.backend._sync_auto_output())
        self.assertFalse(self.backend.outputArmed)

    def test_guards_never_bypassed(self):
        backend = self.backend
        backend.setManualMode("coyote",True)
        wave = backend.waveformCatalog[0]["key"]
        for flag in ("_stop_latched","_user_output_paused","_onboarding_active","_demo"):
            setattr(backend,flag,True)
            self.assertFalse(backend.startManualOutput("coyote",10,wave,0,wave,30),flag)
            setattr(backend,flag,False)
        backend._bridge.connected = False
        self.assertFalse(backend.startManualOutput("coyote",10,wave,0,wave,30))

    def test_hard_cap_zero_stops_running_without_automatic_replay(self):
        backend=self.backend
        playback=self.start("ovc")
        backend._config.values["ovc_profile"]["hard_cap"]=0
        backend._sync_ovc_output(time.monotonic())
        self.assertFalse(playback.running)
        self.assertFalse(backend._ovc_plan.allowed)
        backend._config.values["ovc_profile"]["hard_cap"]=20
        backend._sync_ovc_output(time.monotonic())
        self.assertFalse(playback.running)

    def test_telemetry_disarm_does_not_revoke_an_explicit_manual_owner(self):
        backend=self.backend
        self.start("coyote")
        backend._bridge.reset_mock()
        backend._disarm_output("telemetry failed")
        backend._bridge.set_auto_enabled.assert_not_called()
        backend._sync_manual_output("coyote",time.monotonic())
        self.assertTrue(backend._manual_playback["coyote"].running)
        self.assertTrue(backend._bridge.set_auto_enabled.call_args.args[0])
