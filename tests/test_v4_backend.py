"""Profile isolation and V4 UI integration; no real sockets or user files."""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch

import test_channel_backend as fixture
from ricca_dglab.dglab_v4 import DGLabV4Bridge
from ricca_dglab.product_config import ProductConfig
from ricca_dglab.ovc import OVC_WAVEFORMS


class V4BackendTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    setUp = fixture.ChannelBackendTests.setUp
    tearDown = fixture.ChannelBackendTests.tearDown

    def test_protocol_defaults_and_switch_never_copy_electrical_settings(self):
        b = self.backend
        original = deepcopy(b._config.values)
        self.assertEqual(b.socketProtocol, "v3")
        b._ovc_connected = True
        b._ovc_route_paused = False
        self.assertTrue(b.selectSocketProtocol("v4"))
        self.assertIsInstance(b._bridge, DGLabV4Bridge)
        self.assertTrue(b.pulseRoutePaused)
        self.assertFalse(b.userOutputPaused)
        self.assertFalse(b._stop_latched)
        self.assertTrue(b._ovc_connected)
        self.assertFalse(b._ovc_route_paused)
        self.assertFalse(b.outputArmed)
        self.assertEqual(b._bridge.selected_slot_id, "")
        self.assertFalse(b.selectOutputProfile("ovc"))
        self.assertEqual(b.hardCap, original["hard_cap"])
        self.assertEqual(b.ovcController.hardCap, 20)
        self.assertTrue(b.ovcController.saveIntensitySettings(20, 40, 60, 80, 120))
        expected = deepcopy(original)
        expected["socket_protocol"] = "v4"
        expected["ovc_profile"] = deepcopy(b._config.values["ovc_profile"])
        self.assertEqual(b._config.values, expected)
        loaded = ProductConfig(b._config.path).values
        self.assertEqual(loaded, b._config.values)
        self.assertTrue(b.selectSocketProtocol("v3"))
        self.assertEqual(b.outputProfile, "coyote")
        self.assertTrue(b._ovc_connected)
        self.assertFalse(b._ovc_route_paused)
        self.assertEqual(b.hardCap, original["hard_cap"])
        self.assertEqual(b._config.values["channel_policies"], original["channel_policies"])
        self.assertEqual(b._config.values["ovc_profile"]["hard_cap"], 120)

    def test_ovc_rules_queue_and_audio_bounds_are_independently_saved(self):
        b = self.backend
        original = deepcopy(b._config.values)
        ovc = b.ovcController
        policy = deepcopy(ovc.channelPolicies["A"])
        policy["rules"]["damage_light"].update(wave="ovc_beat", custom_strength=7, duration=.4)
        self.assertTrue(ovc.saveChannelPolicy("A", policy))
        self.assertTrue(ovc.saveStoryQueue("B", [
            {"wave": "ovc_trapezoid", "duration": 2, "tier": "medium", "custom_strength": 9},
            {"wave": "idle", "duration": .5, "tier": "low", "custom_strength": 0}], True))
        self.assertTrue(ovc.saveAudioGain(2.5))
        self.assertTrue(ovc.saveAudioQueueMinimum(10))
        self.assertEqual(ovc.storyQueues["B"][1]["wave"], "idle")
        self.assertEqual(ovc.audioGain, 2.5)
        self.assertEqual(ovc.audioQueueMinimum, 10)
        self.assertEqual({k: v for k, v in b._config.values.items() if k != "ovc_profile"},
                         {k: v for k, v in original.items() if k != "ovc_profile"})
        self.assertEqual({x["key"] for x in ovc.waveformCatalog}, set(OVC_WAVEFORMS))
        self.assertNotIn("ovc_beat", {x["key"] for x in b.waveformCatalog})
        self.assertTrue(b._frames_for("impact"))
        invalid = deepcopy(ovc.channelPolicies["A"])
        invalid["rules"]["damage_light"]["wave"] = "impact"
        self.assertFalse(ovc.saveChannelPolicy("A", invalid))
        self.assertFalse(ovc.saveStoryQueue("A", [{"wave": "impact", "duration": 1}], True))
        loaded = ProductConfig(b._config.path).values
        self.assertEqual(loaded, b._config.values)

    def test_v3_stays_electrical_while_independent_ovc_settings_are_browsed(self):
        b = self.backend
        self.assertEqual(b.ovcController.outputProfile, "ovc")
        self.assertFalse(b.selectOutputProfile("ovc"))
        b._device_connected = True
        self.assertTrue(b._profile_matches_device())
        b._sync_auto_output()
        self.assertTrue(b.outputArmed)
        self.assertNotIn("device-profile-mismatch", b._output_block_reasons(True))
        self.assertTrue(b.canRunDeviceTest)
        self.assertTrue(b.selectOutputProfile("coyote"))
        self.assertFalse(b._ovc_eligible())

    def test_device_selection_is_typed_and_pauses_only_electrical_route(self):
        b = self.backend
        b.selectSocketProtocol("v4")
        bridge = MagicMock()
        bridge.selected_client_id = ""
        bridge.selected_slot_id = ""
        bridge.device_type = ""
        b._bridge = bridge
        b._apply_bridge({"event": "devices", "devices": [
            {"clientId": "app", "slotId": "coyote", "type": "COYOTE_030", "name": "Coyote", "reason": ""},
            {"clientId": "app", "slotId": "ovc", "type": "OVC_1", "name": "Opossum", "reason": ""}]})
        self.assertTrue(b.selectV4Device(1))
        self.assertEqual(b.outputProfile, "coyote")
        bridge.select_device.assert_called_with("app", "coyote")
        self.assertTrue(b.pulseRoutePaused)
        self.assertFalse(b._stop_latched)
        self.assertFalse(b.userOutputPaused)
        bridge.device_type = "COYOTE_030"
        b._apply_bridge({"event": "connected"})
        self.assertFalse(b.outputArmed)
        self.assertEqual(b._preview_a, 0)
        self.assertFalse(b.selectV4Device(9))
        self.assertTrue(b.selectV4Device(0))
        bridge.select_device.assert_called_with("", "")

    def test_stale_bridge_events_are_discarded_but_telemetry_kept(self):
        b = self.backend
        b._queue.put(("dglab", {"event": "connected"}))
        b._queue.put(("dglab", {"event": "connected", "role": "ovc"}))
        b._queue.put(("telemetry", {"state": {}}))
        b._discard_old_bridge_events()
        self.assertEqual(b._queue.get_nowait()[1]["role"], "ovc")
        self.assertEqual(b._queue.get_nowait()[0], "telemetry")
        self.assertTrue(b._queue.empty())

    def test_deprecated_profile_switch_cannot_clear_electrical_output(self):
        b = self.backend
        b._preview_a, b._preview_b = 30, 30
        b._story_queue_player.elapsed["A"] = 7
        b._audio_strength = 25
        self.assertFalse(b.selectOutputProfile("ovc"))
        self.assertEqual((b.previewA, b.previewB), (30, 30))
        self.assertEqual(b._audio_strength, 25)
        self.assertEqual(b._story_queue_player.elapsed["A"], 7)


if __name__ == "__main__":
    unittest.main()
