"""Discovery selection and actionable enable reasons; mocked routes only."""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock
import test_channel_backend as fixture


def device(slot, kind="OVC_1", connected=True):
    return {"clientId": "phone", "slotId": slot, "type": kind,
            "props": {"connectState": "connected" if connected else "disconnected"},
            "slotState": {"hasDevice": connected}, "channelAReason": "", "channelBReason": ""}


class DiscoveryTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    tearDown = fixture.ChannelBackendTests.tearDown

    def setUp(self):
        fixture.ChannelBackendTests.setUp(self)
        b = self.backend
        b._config.values["socket_protocol"] = "v4"
        b._bridge = MagicMock(selected_client_id="", selected_slot_id="", connected=False)
        b._ovc_bridge = MagicMock(selected_client_id="", selected_slot_id="", connected=False)
        b._v4_hub = MagicMock(app_connected=True)
        b._onboarding_active = False
        b._stop_latched = b._user_output_paused = False
        self.original = deepcopy(b._config.values)

    def publish(self, devices):
        self.backend._apply_bridge({"event": "devices", "role": "hub", "protocol": "v4",
                                    "devices": deepcopy(devices)})

    def test_auto_selects_both_once_and_never_enables(self):
        b = self.backend
        devices = [device("pulse", "COYOTE_030"), device("ovc")]
        self.publish(devices)
        b._bridge.select_device.assert_called_once_with("phone", "pulse")
        b._v4_hub.select_device.assert_called_once_with("ovc", "phone", "ovc")
        self.assertEqual((b.v4DeviceIndex, b.ovcDeviceIndex), (1, 1))
        self.assertTrue(b.pulseRoutePaused and b.ovcRoutePaused)
        self.assertFalse(b.deviceConnected or b.ovcConnected or b.outputArmed)
        for _ in range(3):
            self.publish(devices)
        self.assertEqual(b._bridge.select_device.call_count, 1)
        self.assertEqual(b._v4_hub.select_device.call_count, 1)
        self.assertEqual(b._config.values, self.original)

    def test_new_ovc_preserves_running_pulse_and_new_pulse_preserves_ovc(self):
        b = self.backend
        devices = [device("pulse", "COYOTE_030"), device("ovc")]
        self.publish(devices)
        b._pulse_route_paused = False
        b._device_connected = True
        b._bridge.reset_mock()
        devices.append(device("ovc-new"))
        self.publish(devices)
        self.assertEqual(b.ovcDeviceIndex, 2)
        self.assertFalse(b.pulseRoutePaused)
        self.assertTrue(b.deviceConnected)
        b._bridge.emergency_stop.assert_not_called()
        b._ovc_route_paused = False
        b._ovc_connected = True
        b._ovc_bridge.reset_mock()
        devices.append(device("pulse-new", "COYOTE_030"))
        self.publish(devices)
        self.assertEqual(b.v4DeviceIndex, 2)
        self.assertFalse(b.ovcRoutePaused)
        self.assertTrue(b.ovcConnected)
        b._ovc_bridge.emergency_stop.assert_not_called()

    def test_reconnect_is_selected_but_status_patches_are_not(self):
        b = self.backend
        self.publish([device("ovc", connected=False)])
        b._v4_hub.select_device.assert_not_called()
        self.publish([device("ovc")])
        self.assertEqual(b._v4_hub.select_device.call_count, 1)
        self.publish([device("ovc", connected=False)])
        self.publish([device("ovc")])
        self.assertEqual(b._v4_hub.select_device.call_count, 2)

    def test_initial_snapshot_does_not_restart_an_already_selected_live_route(self):
        b = self.backend
        b._ovc_bridge.selected_client_id = "phone"
        b._ovc_bridge.selected_slot_id = "ovc"
        b._ovc_connected = True
        b._ovc_route_paused = False
        self.publish([device("ovc")])
        b._v4_hub.select_device.assert_not_called()
        b._ovc_bridge.emergency_stop.assert_not_called()
        self.assertTrue(b.ovcConnected)
        self.assertFalse(b.ovcRoutePaused)

    def test_manual_deselection_remains_until_a_new_link_arrives(self):
        b = self.backend
        devices = [device("ovc")]
        self.publish(devices)
        self.assertTrue(b.selectOvcDevice(0))
        calls = b._v4_hub.select_device.call_count
        self.publish(devices)
        self.assertEqual(b.ovcDeviceIndex, 0)
        self.assertEqual(b._v4_hub.select_device.call_count, calls)
        self.publish(devices + [device("next")])
        self.assertEqual(b.ovcDeviceIndex, 2)

    def test_v3_coyote_is_not_replaced_by_v4_discovery(self):
        b = self.backend
        b._config.values["socket_protocol"] = "v3"
        b._device_connected = True
        b._pulse_route_paused = False
        self.publish([device("pulse", "COYOTE_030"), device("ovc")])
        b._bridge.select_device.assert_not_called()
        self.assertTrue(b.deviceConnected)
        self.assertFalse(b.pulseRoutePaused)
        b._v4_hub.select_device.assert_called_once()

    def test_waiting_and_stale_ovc_events_do_not_override_new_choice(self):
        b = self.backend
        self.publish([device("new")])
        b._apply_bridge({"event": "connected", "role": "ovc", "target_id": "phone", "slot_id": "old"})
        self.assertFalse(b.ovcConnected)
        self.assertEqual(b.ovcDeviceIndex, 1)
        b._apply_bridge({"event": "connected", "role": "ovc", "target_id": "phone", "slot_id": "new"})
        self.assertTrue(b.ovcConnected)
        b._apply_bridge({"event": "waiting", "role": "ovc"})
        self.assertFalse(b.ovcConnected)
        self.assertTrue(b.ovcRoutePaused)

    def test_enable_explanation_covers_connection_and_output_gates(self):
        b = self.backend
        b._v4_hub.app_connected = False
        self.assertIn("扫码", b.ovcEnableReason)
        b._v4_hub.app_connected = True
        self.assertIn("尚未发现", b.ovcEnableReason)
        d = device("ovc")
        d["channelAReason"] = d["channelBReason"] = "accessory-not-inserted"
        self.publish([d])
        self.assertIn("未插入", b.ovcEnableReason)
        d["channelAReason"] = d["channelBReason"] = "channel-muted"
        self.publish([d])
        self.assertIn("静音", b.ovcEnableReason)
        d["channelAReason"] = d["channelBReason"] = ""
        self.publish([d])
        self.assertIn("确认归零", b.ovcEnableReason)
        b._ovc_connected = True
        b._config.values["ovc_profile"]["hard_cap"] = 0
        self.assertIn("0", b.ovcEnableReason)
        b._config.values["ovc_profile"]["hard_cap"] = 20
        b._user_output_paused = True
        self.assertIn("全局暂停", b.ovcEnableReason)
        b._stop_latched = True
        self.assertIn("急停", b.ovcEnableReason)
        toasts = []
        b.toastRequested.connect(lambda title, detail: toasts.append((title, detail)))
        b.toggleOvcOutput()
        self.assertEqual(toasts[-1][1], b.ovcEnableReason)
        self.assertTrue(b.ovcRoutePaused)
