"""Route recovery regression tests: temporary configs and mock senders only."""
import queue
import unittest
from unittest.mock import MagicMock, patch

import test_channel_backend as fixture
from ricca_dglab.dglab_v4_hub import DGLabV4Hub
from ricca_dglab.ovc_pipeline import OvcOutputPlan
from test_v4_bridge import device


class RouteRecoveryTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    setUp = fixture.ChannelBackendTests.setUp
    tearDown = fixture.ChannelBackendTests.tearDown

    def mock_routes(self):
        b = self.backend
        b._bridge = MagicMock()
        b._bridge._thread = None
        b._v4_hub = MagicMock()
        b._v4_hub._thread = None
        b._ovc_bridge = MagicMock()
        b._ovc_connected = b._device_connected = b._output_armed = True
        b._pulse_route_paused = b._ovc_route_paused = False
        b._stop_latched = b._user_output_paused = b._pause_active = False
        b._ovc_plan = OvcOutputPlan(strength_a=7, allowed=True, paused=False)
        b._ovc_pipeline.queue.elapsed["A"] = 4.25
        b._ovc_pipeline.stop = MagicMock()
        return b

    def assert_pulse_failure_is_local(self, event):
        b = self.mock_routes()
        pipeline, plan = b._ovc_pipeline, b._ovc_plan
        b._apply_bridge({"event": event, "detail": "mock route failure"})
        self.assertTrue(b._pulse_route_paused)
        self.assertFalse(b._output_armed)
        self.assertFalse(b._stop_latched)
        self.assertFalse(b._user_output_paused)
        self.assertTrue(b._ovc_connected)
        self.assertFalse(b._ovc_route_paused)
        self.assertIs(b._ovc_pipeline, pipeline)
        self.assertIs(b._ovc_plan, plan)
        self.assertEqual(pipeline.queue.elapsed["A"], 4.25)
        pipeline.stop.assert_not_called()
        self.assertEqual(b._ovc_bridge.mock_calls, [])
        self.assertEqual(b._v4_hub.mock_calls, [])

    def test_pulse_error_does_not_revoke_vibration(self):
        self.assert_pulse_failure_is_local("error")

    def test_pulse_timeout_does_not_revoke_vibration(self):
        self.assert_pulse_failure_is_local("output_timeout")

    def test_pulse_server_failure_does_not_revoke_vibration(self):
        self.assert_pulse_failure_is_local("server_error")

    def test_primary_connection_edges_preserve_shared_pending_damage(self):
        b = self.mock_routes()
        pending = object()
        b._detector.pending_damage = pending
        for event in ("connected", "disconnected", "connected"):
            b._apply_bridge({"event": event})
            self.assertIs(b._detector.pending_damage, pending, event)
        self.assertTrue(b._ovc_connected)
        self.assertFalse(b._ovc_route_paused)
        b._ovc_pipeline.stop.assert_not_called()

    def assert_full_restart(self, protocol):
        b = self.mock_routes()
        b._config.values["socket_protocol"] = protocol
        b._start_bridge_enabled = True
        old_primary, old_hub = b._bridge, b._v4_hub
        fresh_hub, fresh_primary, fresh_ovc = MagicMock(), MagicMock(), MagicMock()
        fresh_hub.channel.side_effect = lambda role: fresh_ovc if role == "ovc" else fresh_primary
        b._server_ready = True
        b._qr_url = b._qr_source = "old-primary-qr"
        b._v4_qr_url = b._v4_qr_source = "old-v4-qr"
        b._queue.put(("dglab", {"event": "ready", "role": "hub", "qr_url": "stale"}))
        b._queue.put(("dglab", {"event": "connected", "role": "ovc"}))
        b._queue.put(("telemetry", {"state": {}}))
        with patch("ricca_dglab.backend.DGLabV4Hub", return_value=fresh_hub), \
                patch.object(b, "_make_bridge", return_value=fresh_primary):
            self.assertTrue(b.restartSocket())
        old_primary.stop.assert_called_once()
        old_hub.stop.assert_called_once()
        self.assertIs(b._v4_hub, fresh_hub)
        self.assertIs(b._bridge, fresh_primary)
        self.assertIs(b._ovc_bridge, fresh_ovc)
        fresh_primary.start.assert_called_once()
        fresh_hub.start.assert_called_once()
        fresh_primary.latch_global_emergency_stop.assert_called_once()
        fresh_hub.latch_global_emergency_stop.assert_called_once()
        self.assertTrue(b._stop_latched)
        self.assertTrue(b._user_output_paused)
        self.assertTrue(b._ovc_route_paused)
        self.assertFalse(b._ovc_connected or b._device_connected or b._server_ready)
        self.assertEqual((b._qr_source, b._v4_qr_source), ("", ""))
        self.assertEqual(b._queue.get_nowait()[0], "telemetry")
        self.assertTrue(b._queue.empty())
        b._apply_bridge({"event": "ready", "role": "hub", "protocol": "v4",
                         "qr_url": "https://example.invalid/fresh-v4", "port": 9998,
                         "lan_ip": "192.0.2.1"})
        self.assertEqual(b._v4_qr_url, "https://example.invalid/fresh-v4")
        self.assertTrue(b._v4_qr_source.startswith("data:image/png;base64,"))
        self.assertEqual(b._server_ready, protocol == "v4")
        self.assertTrue(b._stop_latched)
        self.assertTrue(b._user_output_paused)
        if protocol == "v3":
            b._apply_bridge({"event": "ready", "qr_url": "https://example.invalid/fresh-v3",
                             "port": 9999, "lan_ip": "192.0.2.1"})
            self.assertEqual(b._qr_url, "https://example.invalid/fresh-v3")
            self.assertEqual(b._v4_qr_url, "https://example.invalid/fresh-v4")

    def test_full_retry_replaces_both_routes_when_primary_is_v3(self):
        self.assert_full_restart("v3")

    def test_full_retry_replaces_both_routes_when_primary_is_v4(self):
        self.assert_full_restart("v4")

    def test_full_retry_does_not_start_second_hub_when_shutdown_is_incomplete(self):
        b = self.mock_routes()
        b._start_bridge_enabled = True
        b._v4_hub._thread = MagicMock()
        b._v4_hub._thread.is_alive.return_value = True
        with patch("ricca_dglab.backend.DGLabV4Hub") as replacement:
            self.assertFalse(b.restartSocket())
        replacement.assert_not_called()
        self.assertTrue(b._stop_latched)
        self.assertTrue(b._user_output_paused)

    def test_v3_lan_choice_updates_v4_qr_transport_without_stopping_vibration(self):
        b = self.mock_routes()
        b._config.values["socket_protocol"] = "v3"
        b._bridge.set_lan_ip.return_value = True
        b._lan_ip = "192.0.2.1"
        b.selectLanAddress("192.0.2.2")
        b._bridge.set_lan_ip.assert_called_once_with("192.0.2.2")
        b._v4_hub.set_lan_ip.assert_called_once_with("192.0.2.2")
        self.assertEqual(b._lan_ip, "192.0.2.2")
        self.assertFalse(b._ovc_route_paused)
        self.assertFalse(b._stop_latched)
        b._ovc_pipeline.stop.assert_not_called()
        self.assertEqual(b._ovc_bridge.mock_calls, [])


class FailedRouteAuthorityTests(unittest.TestCase):
    def test_route_failure_keeps_selection_but_cannot_auto_reauthorize(self):
        with patch("ricca_dglab.dglab_bridge.ipv4_interfaces", return_value=[{"address": "127.0.0.1"}]):
            hub = DGLabV4Hub(queue.Queue(), port=0)
        route, peer = hub.channel("ovc"), hub.channel("coyote")
        route.selected_client_id, route.selected_slot_id, route.device_type = "app", "ovc", "OVC_1"
        route._devices = {"app": {"ovc": device()}}
        route.connected = route._baseline_ready = route._selection_waiting_for_ready = True
        route._auto_enabled = True
        peer.connected = peer._baseline_ready = True
        route._close_for_route_error("app", "mock-zero-failure")
        self.assertFalse(route.connected or route._baseline_ready or route._auto_enabled)
        self.assertFalse(route._selection_waiting_for_ready)
        self.assertEqual((route.selected_client_id, route.selected_slot_id), ("app", "ovc"))
        route._check_selected()
        self.assertFalse(route.connected)
        self.assertTrue(peer.connected and peer._baseline_ready)
        self.assertFalse(peer._global_emergency_stop.is_set())


if __name__ == "__main__":
    unittest.main()
