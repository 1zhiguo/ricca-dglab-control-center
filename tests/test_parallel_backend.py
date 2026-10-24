"""Parallel electrical/vibration backend regression, using fake senders only."""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

import test_channel_backend as fixture


def state(hp=31):
    return {"status": "ok", "connected": True, "build_supported": True, "process_id": 42,
            "scene": "gameplay", "player_address": "0x123", "current_hp": hp,
            "max_hp": 31, "stage": {"all_resource_loaded": True}, "is_paused": False,
            "game_ui": {"is_user_pause": False}, "action_trigger_name": "stand_idle",
            "action_trigger_hash": 42, "action_trigger_enabled": True}


class ParallelBackendTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    setUp = fixture.ChannelBackendTests.setUp
    tearDown = fixture.ChannelBackendTests.tearDown

    def enable_senders(self, *, coyote=True, ovc=True):
        b = self.backend
        b._bridge = MagicMock()
        b._bridge.connected = coyote
        b._ovc_bridge = MagicMock()
        b._ovc_bridge.connected = ovc
        b._ovc_bridge.device_type = "OVC_1"
        b._ovc_bridge.selected_client_id = "app"
        b._ovc_bridge.selected_slot_id = "vibration"
        b._ovc_bridge._global_emergency_stop.is_set.return_value = False
        b._device_connected = coyote
        b._ovc_connected = ovc
        b._ovc_route_paused = False
        b._user_output_paused = b._stop_latched = False
        return b

    def feed(self, now, hp=31):
        with patch("ricca_dglab.backend.time.monotonic", return_value=now):
            self.backend._apply_state({"state": state(hp), "received_at": now, "latency_ms": 1})
            self.backend._drain()

    def baseline(self):
        for index in range(8):
            self.feed(10 + index * .1)

    def hit(self):
        self.feed(11, 28)
        with patch("ricca_dglab.backend.time.monotonic", return_value=11.35):
            self.backend._drain()

    def test_primary_is_always_electrical_and_ovc_never_replaces_it(self):
        b = self.backend
        original = deepcopy(b._config.values)
        self.assertEqual(b.outputProfile, "coyote")
        self.assertFalse(b.selectOutputProfile("ovc"))
        self.assertEqual(b.outputProfile, "coyote")
        self.assertEqual(b.hardCap, original["hard_cap"])
        self.assertEqual(b.channelPolicies, original["channel_policies"])
        self.assertEqual(b.ovcController.hardCap, original["ovc_profile"]["hard_cap"])

    def test_vibration_intensity_wave_and_queue_saves_do_not_change_electrical_state(self):
        b = self.enable_senders()
        original = deepcopy(b._config.values)
        mapper = b._mapping
        self.assertTrue(b.ovcController.saveIntensitySettings(20, 40, 60, 80, 100))
        policy = deepcopy(b.ovcController.channelPolicies["A"])
        policy["rules"]["damage_light"].update(wave="ovc_beat", custom_strength=3, duration=.5)
        self.assertTrue(b.ovcController.saveChannelPolicy("A", policy))
        self.assertTrue(b.ovcController.saveStoryQueue("B", [
            {"wave": "ovc_trapezoid", "duration": 2, "tier": "low", "custom_strength": None},
            {"wave": "idle", "duration": .5, "tier": "low", "custom_strength": 0}], True))
        self.assertEqual(b._config.values["hard_cap"], original["hard_cap"])
        self.assertEqual(b._config.values["channel_policies"], original["channel_policies"])
        self.assertEqual(b._config.values["story_queues"], original["story_queues"])
        self.assertIs(b._mapping, mapper)
        self.assertEqual(b._bridge.mock_calls, [])
        self.assertEqual(b.outputProfile, "coyote")
        self.assertEqual(b.ovcController.hardCap, 100)

    def test_device_lists_are_typed_and_ovc_selection_does_not_pause_electrical_output(self):
        b = self.enable_senders()
        b._output_armed = True
        b._v4_devices = [
            {"clientId": "app", "slotId": "electric", "type": "COYOTE_030", "name": "Coyote"},
            {"clientId": "app", "slotId": "vibration", "type": "OVC_1", "name": "Opossum"}]
        self.assertEqual([item["type"] for item in b.v4Devices], ["COYOTE_030"])
        self.assertEqual([item["type"] for item in b.ovcDevices], ["OVC_1"])
        with patch.object(b._v4_hub, "select_device", return_value=True):
            self.assertTrue(b.selectOvcDevice(1))
        self.assertTrue(b._ovc_route_paused)
        self.assertFalse(b._user_output_paused)
        self.assertFalse(b._stop_latched)
        self.assertTrue(b._output_armed)
        self.assertEqual(b._bridge.mock_calls, [])

    def test_one_hp_event_drives_both_separate_waveform_pipelines(self):
        b = self.enable_senders()
        self.baseline()
        self.hit()
        self.assertGreater(b.previewA, 0)
        self.assertGreater(b.ovcPlan["strength_a"], 0)
        self.assertFalse(b.waveA.startswith("ovc_"))
        self.assertTrue(b.ovcPlan["wave_a"].startswith("ovc_"))
        b._bridge.set_auto_enabled.assert_called_with(True)
        b._ovc_bridge.set_auto_enabled.assert_called_with(True)
        self.assertTrue(b._bridge.update_auto_outputs.called)
        self.assertTrue(b._ovc_bridge.update_auto_outputs.called)

    def test_coyote_offline_and_zero_cap_do_not_disable_vibration(self):
        b = self.enable_senders(coyote=False)
        b._config.values["hard_cap"] = 0
        b._refresh_mapping_config()
        self.baseline()
        self.hit()
        self.assertFalse(b.outputArmed)
        self.assertEqual(b.previewA, 0)
        self.assertTrue(b.ovcPlan["allowed"])
        self.assertGreater(b.ovcPlan["strength_a"], 0)
        b._ovc_bridge.set_auto_enabled.assert_called_with(True)

    def test_primary_disconnect_does_not_revoke_vibration_route(self):
        b = self.enable_senders()
        self.baseline()
        with patch("ricca_dglab.backend.time.monotonic", return_value=10.8):
            b._apply_bridge({"event": "disconnected"})
        self.assertTrue(b._ovc_connected)
        self.assertFalse(b._ovc_route_paused)
        self.hit()
        self.assertTrue(b.ovcPlan["allowed"])
        self.assertGreater(b.ovcPlan["strength_a"], 0)

    def test_vibration_disconnect_does_not_disarm_electrical_route(self):
        b = self.enable_senders()
        self.baseline()
        with patch("ricca_dglab.backend.time.monotonic", return_value=10.8):
            b._apply_bridge({"event": "disconnected", "role": "ovc", "protocol": "v4"})
        self.assertTrue(b._device_connected)
        self.hit()
        self.assertTrue(b.outputArmed)
        self.assertGreater(b.previewA, 0)
        self.assertFalse(b.ovcPlan["allowed"])

    def test_death_cue_remains_available_when_electrical_device_is_offline(self):
        b = self.enable_senders(coyote=False)
        self.baseline()
        self.feed(11, 0)
        self.assertEqual(b.ovcPlan["priority_kind"], "death")
        self.assertGreater(b.ovcPlan["strength_a"], 0)
        self.assertTrue(b.ovcPlan["allowed"])

    def test_global_emergency_stops_both_plans_and_requires_manual_resume(self):
        b = self.enable_senders()
        self.baseline()
        self.hit()
        b.emergencyStop()
        with patch("ricca_dglab.backend.time.monotonic", return_value=11.36):
            b._drain()
        self.assertTrue(b._stop_latched)
        self.assertTrue(b.userOutputPaused)
        self.assertFalse(b.outputArmed)
        self.assertFalse(b.ovcPlan["allowed"])
        self.assertEqual(b.ovcPlan["strength_a"], 0)
        b._bridge.set_auto_enabled.assert_called_with(False)
        b._ovc_bridge.set_auto_enabled.assert_called_with(False)

    def test_audio_gain_only_save_keeps_vibration_clock_and_coyote_untouched(self):
        b = self.enable_senders()
        b._ovc_pipeline.queue.elapsed["A"] = 4.25
        b._ovc_pipeline.queue.channel_keys["A"] = (42, "scene", 1)
        self.assertTrue(b.ovcController.saveAudioGain(2.5))
        self.assertEqual(b._ovc_pipeline.queue.elapsed["A"], 4.25)
        self.assertEqual(b._bridge.mock_calls, [])
        self.assertEqual(b._config.values["audio_gain"], 1)


if __name__ == "__main__":
    unittest.main()
