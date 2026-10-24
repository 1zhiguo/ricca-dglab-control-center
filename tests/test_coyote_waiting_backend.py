"""Accepted-but-not-ready Coyote choices stay visible without granting output.

All routes are fake; only a temporary fixture config is used. No device or
network listener is started and no persisted user settings are touched.
"""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

import test_channel_backend as fixture
from ricca_dglab.ovc_pipeline import OvcOutputPlan


def device(slot="electric", name="Coyote", **changes):
    return {"clientId": "app", "slotId": slot, "type": "COYOTE_030", "name": name,
            "channelAReason": "bluetooth-not-connected", "channelBReason": "bluetooth-not-connected",
            "props": {"intensityA": 0, "intensityB": 0}, **changes}


class CoyoteWaitingBackendTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    tearDown = fixture.ChannelBackendTests.tearDown

    def setUp(self):
        fixture.ChannelBackendTests.setUp(self)
        b = self.backend
        b._config.values["socket_protocol"] = "v4"
        b._bridge = MagicMock()
        b._bridge.selected_client_id = b._bridge.selected_slot_id = ""
        b._bridge.device_type = "COYOTE_030"
        b._bridge._thread = None
        b._bridge.select_device.return_value = True
        b._bridge.lan_ip = "192.0.2.1"
        b._bridge.available_lan_ips = ["192.0.2.1"]
        b._ovc_bridge = MagicMock()
        b._v4_hub = MagicMock()
        b._v4_hub.app_connected = True
        b._v4_hub._thread = None
        b._ovc_connected = True
        b._ovc_route_paused = False
        b._ovc_plan = OvcOutputPlan(strength_a=7, allowed=True, paused=False)
        b._ovc_pipeline.queue.elapsed["A"] = 4.25
        b._ovc_pipeline.queue.channel_keys["A"] = (42, "scene", 1)
        b._stop_latched = b._user_output_paused = b._pause_active = False
        b._device_connected = False
        b._state = {"status": "ok", "connected": True, "build_supported": True,
                    "process_id": 42, "scene": "gameplay", "is_paused": False,
                    "game_ui": {"is_user_pause": False},
                    "stage": {"all_resource_loaded": True}}
        b._v4_devices = [device()]
        self.original = deepcopy(b._config.values)
        self.ovc_pipeline, self.ovc_plan = b._ovc_pipeline, b._ovc_plan

    def assert_ovc_untouched(self):
        b = self.backend
        self.assertTrue(b._ovc_connected)
        self.assertFalse(b._ovc_route_paused)
        self.assertFalse(b._stop_latched)
        self.assertFalse(b.userOutputPaused)
        self.assertIs(b._ovc_pipeline, self.ovc_pipeline)
        self.assertIs(b._ovc_plan, self.ovc_plan)
        self.assertEqual(b._ovc_pipeline.queue.elapsed["A"], 4.25)
        self.assertEqual(b._ovc_pipeline.queue.channel_keys["A"], (42, "scene", 1))
        self.assertEqual(b._ovc_bridge.mock_calls, [])
        self.assertEqual(b._v4_hub.mock_calls, [])

    def event(self, kind, slot="electric", **payload):
        self.backend._apply_bridge({"event": kind, "role": "coyote", "protocol": "v4",
                                    "target_id": "app", "slot_id": slot, **payload})

    def test_accepted_async_choice_is_visible_before_bridge_ids_are_updated(self):
        b = self.backend
        self.assertTrue(b.selectV4Device(1))
        b._bridge.select_device.assert_called_once_with("app", "electric")
        self.assertEqual((b._bridge.selected_client_id, b._bridge.selected_slot_id), ("", ""))
        self.assertEqual(b._pulse_requested_selection, ("app", "electric"))
        self.assertEqual(b.v4DeviceIndex, 1)
        self.assertTrue(b.pulseDeviceWaiting)
        self.assertTrue(b.v4DeviceStatus.startswith("等待设备就绪 · "))
        self.assertIn("蓝牙未连接", b.v4DeviceStatus)
        self.assertTrue(b.pulseRoutePaused)
        self.assertFalse(b.deviceConnected or b.outputArmed)
        self.assertEqual(b._config.values, self.original)
        self.assert_ovc_untouched()

    def test_waiting_event_retains_choice_and_only_pauses_electrical_authority(self):
        b = self.backend
        b.selectV4Device(1)
        b._device_connected = b._output_armed = True
        b._pulse_route_paused = False
        pending = object()
        b._detector.pending_damage = pending
        self.event("waiting", reason="bluetooth-not-connected")
        self.assertEqual(b.v4DeviceIndex, 1)
        self.assertEqual(b._pulse_requested_selection, ("app", "electric"))
        self.assertTrue(b.pulseDeviceWaiting)
        self.assertTrue(b.pulseRoutePaused)
        self.assertFalse(b.deviceConnected or b.outputArmed)
        self.assertIs(b._detector.pending_damage, pending)
        b._bridge.set_auto_enabled.assert_called_with(False)
        self.assertEqual(b._config.values, self.original)
        self.assert_ovc_untouched()

    def test_muted_channels_explain_block_without_unmuting_or_touching_ovc(self):
        b=self.backend
        b.selectV4Device(1)
        current=device(channelAReason="channel-muted",channelBReason="channel-muted",reason="channel-muted")
        self.event("devices",devices=[current])
        self.event("waiting",reason="channel-muted")
        self.assertTrue(b.pulseDeviceMuted)
        self.assertIn("DG-LAB App",b.pulseWaitingHint)
        self.assertTrue(b.v4DeviceStatus.startswith("通道已静音"))
        self.assertIn("解除静音",b.bridgeStatus)
        messages=[]
        b.toastRequested.connect(lambda title,message:messages.append((title,message)))
        b._bridge.reset_mock()
        b.togglePulseOutput()
        self.assertEqual(messages[0][0],"暂时无法启用")
        self.assertIn("请在 DG-LAB App 解除静音",messages[0][1])
        self.assertEqual(b._bridge.mock_calls,[])
        self.assertTrue(b.pulseRoutePaused)
        self.assertFalse(b.outputArmed or b.deviceConnected)
        self.assertEqual(b._config.values,self.original)
        self.assert_ovc_untouched()

    def test_muted_label_tracks_state_without_stale_disconnect_reason_in_choice(self):
        b=self.backend
        b.selectV4Device(1)
        self.event("devices",devices=[device(reason="bluetooth-not-connected")])
        self.assertNotIn("bluetooth-not-connected",b.v4Devices[0]["label"])
        self.event("devices",devices=[device(channelAReason="channel-muted",channelBReason="channel-muted")])
        self.assertTrue(b.pulseDeviceMuted)
        self.event("devices",devices=[device(channelAReason="",channelBReason="channel-muted")])
        self.assertFalse(b.pulseDeviceMuted)
        self.assertIn("A · 可用",b.v4DeviceStatus)
        self.assertEqual(b.v4DeviceIndex,1)
        self.assert_ovc_untouched()

    def test_ready_recovery_keeps_route_paused_until_explicit_pulse_toggle(self):
        b = self.backend
        b.selectV4Device(1)
        self.event("waiting")
        # The transport has now successfully bound this exact route.
        b._bridge.selected_client_id, b._bridge.selected_slot_id = "app", "electric"
        self.event("connected")
        self.assertIsNone(b._pulse_requested_selection)
        self.assertEqual(b.v4DeviceIndex, 1)
        self.assertFalse(b.pulseDeviceWaiting)
        self.assertTrue(b.deviceConnected)
        self.assertTrue(b.pulseRoutePaused)
        self.assertFalse(b.outputArmed)
        b._sync_auto_output()
        self.assertFalse(b.outputArmed)
        b.togglePulseOutput()
        b._sync_auto_output()
        self.assertFalse(b.pulseRoutePaused)
        self.assertTrue(b.outputArmed)
        b._bridge.clear_global_emergency_stop.assert_called_once()
        self.assertEqual(b._config.values, self.original)
        self.assert_ovc_untouched()

    def test_enable_attempt_while_waiting_cannot_prearm_later_recovery(self):
        b = self.backend
        b.selectV4Device(1)
        self.event("waiting")
        b._bridge.reset_mock()
        b.togglePulseOutput()
        self.assertTrue(b.pulseRoutePaused)
        self.assertFalse(b.deviceConnected or b.outputArmed)
        self.assertEqual(b._bridge.mock_calls, [])
        self.assert_ovc_untouched()

    def test_repeated_catalog_updates_keep_accepted_choice_and_waiting_state(self):
        b = self.backend
        b.selectV4Device(1)
        for intensity in (0, 3, 0):
            self.event("devices", devices=[device(props={"intensityA": intensity})])
            self.assertEqual(b.v4DeviceIndex, 1)
            self.assertEqual(b._pulse_requested_selection, ("app", "electric"))
            self.assertTrue(b.pulseDeviceWaiting)
            self.assertTrue(b.pulseRoutePaused)
            self.assertFalse(b.outputArmed)
        self.assertEqual(b._config.values, self.original)
        self.assert_ovc_untouched()

    def test_catalog_reordering_follows_route_identity_not_old_list_index(self):
        b = self.backend
        b._v4_devices = [device(), device("other", "Other Coyote")]
        b.selectV4Device(1)
        self.event("devices", devices=[device("other", "Other Coyote"), device()])
        self.assertEqual(b.v4DeviceIndex, 2)
        self.assertEqual(b._pulse_requested_selection, ("app", "electric"))
        self.assertTrue(b.pulseDeviceWaiting)
        self.assert_ovc_untouched()

    def test_real_disconnect_clears_visual_override(self):
        b = self.backend
        b.selectV4Device(1)
        self.event("disconnected", reason="app-disconnected")
        self.assertIsNone(b._pulse_requested_selection)
        self.assertEqual(b.v4DeviceIndex, 0)
        self.assertFalse(b.pulseDeviceWaiting or b.deviceConnected or b.outputArmed)
        self.assertEqual(b.v4DeviceStatus, "尚未选择输出设备")
        self.assertEqual(b._config.values, self.original)
        self.assert_ovc_untouched()

    def test_removed_catalog_slot_clears_visual_override(self):
        b = self.backend
        b.selectV4Device(1)
        self.event("devices", devices=[device("other", "Other Coyote")])
        self.assertIsNone(b._pulse_requested_selection)
        self.assertEqual(b.v4DeviceIndex, 0)
        self.assertFalse(b.pulseDeviceWaiting or b.outputArmed)
        self.assertEqual(b._config.values, self.original)
        self.assert_ovc_untouched()

    def test_switch_to_v3_clears_visual_override_without_changing_ovc(self):
        b = self.backend
        b.selectV4Device(1)
        new_bridge = MagicMock()
        new_bridge.lan_ip, new_bridge.available_lan_ips = "192.0.2.1", ["192.0.2.1"]
        # Keep even this fixture's protocol persistence entirely in-memory.
        with patch.object(b._config, "update", side_effect=b._config.values.update) as save, \
                patch.object(b, "_make_bridge", return_value=new_bridge):
            self.assertTrue(b.selectSocketProtocol("v3"))
        save.assert_called_once_with({"socket_protocol": "v3"})
        self.assertIsNone(b._pulse_requested_selection)
        self.assertEqual(b.v4DeviceIndex, 0)
        self.assertFalse(b.pulseDeviceWaiting or b.outputArmed)
        expected = deepcopy(self.original)
        expected["socket_protocol"] = "v3"
        self.assertEqual(b._config.values, expected)
        self.assert_ovc_untouched()

    def test_late_old_slot_events_do_not_clobber_newly_accepted_choice(self):
        b = self.backend
        b._v4_devices = [device(), device("new", "New Coyote")]
        b.selectV4Device(1)
        b.selectV4Device(2)
        for kind in ("waiting", "connected", "disconnected"):
            with self.subTest(event=kind):
                b._bridge.reset_mock()
                self.event(kind, slot="electric")
                self.assertEqual(b._pulse_requested_selection, ("app", "new"))
                self.assertEqual(b.v4DeviceIndex, 2)
                self.assertTrue(b.pulseDeviceWaiting)
                self.assertTrue(b.pulseRoutePaused)
                self.assertFalse(b.deviceConnected or b.outputArmed)
                self.assertEqual(b._bridge.mock_calls, [])
                self.assertEqual(b._config.values, self.original)
                self.assert_ovc_untouched()

    def test_explicit_unselect_cannot_be_replaced_by_late_old_route_events(self):
        b = self.backend
        b.selectV4Device(1)
        self.assertTrue(b.selectV4Device(0))
        for kind in ("waiting", "connected", "disconnected"):
            with self.subTest(event=kind):
                self.event(kind)
                self.assertEqual(b._pulse_requested_selection, ("", ""))
                self.assertEqual(b.v4DeviceIndex, 0)
                self.assertFalse(b.pulseDeviceWaiting or b.deviceConnected or b.outputArmed)
        self.assertEqual(b._config.values, self.original)
        self.assert_ovc_untouched()


if __name__ == "__main__":
    unittest.main()
