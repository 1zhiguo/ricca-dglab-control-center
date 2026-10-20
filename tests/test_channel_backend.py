from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

from PySide6.QtCore import QCoreApplication

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.models import RuntimeMode, SafetyDecision
from ricca_dglab.product_config import ProductConfig, default_channel_policies


class ChannelBackendTests(unittest.TestCase):
    def test_current_interaction_takeover_is_explicit_and_never_invents_a_death_penalty(self):
        from test_defeat_scene import cg
        backend = self.backend
        backend._bridge = MagicMock()
        backend._device_connected = True
        state = cg(0)
        state["defeat_scene_hint"] = "Scene3D_RiccaGhoul"
        for _ in range(3):
            backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()
        self.assertEqual(backend.previewA, 0)  # Attaching alone must not start output.
        self.assertTrue(backend.canConfirmCurrentDefeatScene)
        self.assertTrue(backend.confirmCurrentDefeatScene())
        for _ in range(3):
            backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()
        self.assertEqual(backend.previewA, backend.mediumStrength)
        self.assertIsNone(backend._defeat_scene.penalty_started)
        self.assertEqual(backend.priorityOutputStatus, "败北互动")
        backend.emergencyStop()
        backend._defeat_scene.reset()
        self.assertFalse(backend.canConfirmCurrentDefeatScene)
        self.assertFalse(backend.confirmCurrentDefeatScene())

    def test_death_priority_never_bypasses_stale_reads_disconnect_zero_cap_or_unsupported_build(self):
        from test_defeat_scene import death
        backend = self.backend
        backend._bridge = MagicMock()
        backend._device_connected = True
        with patch("ricca_dglab.backend.time.monotonic", return_value=10):
            backend._apply_state({"state": dict(death(), current_hp=31, max_hp=31), "received_at": 10, "latency_ms": 1})
        with patch("ricca_dglab.backend.time.monotonic", return_value=11):
            state = dict(death(), max_hp=31, is_paused=True)
            backend._apply_state({"state": state, "received_at": 11, "latency_ms": 1})
            backend._drain()
            backend._bridge.set_auto_enabled.assert_called_with(True)
            for field, value in (("build_supported", False), ("status", "error"), ("process_id", 99)):
                backend._state = dict(state, **{field: value})
                backend._drain()
                backend._bridge.set_auto_enabled.assert_called_with(False)
            backend._state = state
            backend._config.values["hard_cap"] = 0
            backend._drain()
            backend._bridge.set_auto_enabled.assert_called_with(False)
            backend._config.values["hard_cap"] = 30
        with patch("ricca_dglab.backend.time.monotonic", return_value=12):
            backend._drain()
            backend._bridge.set_auto_enabled.assert_called_with(False)
        backend._apply_bridge({"event": "disconnected"})
        backend._drain()
        backend._bridge.set_auto_enabled.assert_called_with(False)

    def test_single_armor_multiplier_applies_once_to_hold_audio_and_cg_and_resets_on_respawn(self):
        from ricca_dglab.models import GameEvent, OutputPreview
        backend, state = self.ready_device()
        now = time.monotonic()
        backend._mapping.accept([GameEvent(900, now, "now", "armor_break", "break",
                                            data={"last_break_time": 12, "level_after": 2})])
        backend._drain()
        self.assertEqual(backend.sensitivityMultiplier, 1.2)
        self.assertEqual(backend.previewB, 30)  # Initial armor-break event, capped.
        backend._mapping.clear_pulses()
        backend._mapping.reconcile_capture(state, now=time.monotonic())
        backend._drain()
        self.assertEqual(backend.previewB, 18)  # Held base 15, not 15 * 1.2 * 1.2.
        backend._mapping.accept([GameEvent(901, now, "now", "armor_break", "break",
                                            data={"last_break_time": 13, "level_after": 3})])
        backend._drain()
        self.assertEqual(backend.previewB, 18)

        policies = default_channel_policies()
        policies["A"]["mode"] = "audio"
        backend._config.values.update(audio_empathy_enabled=True, channel_policies=policies)
        backend._refresh_mapping_config()
        backend._decision = SafetyDecision(RuntimeMode.STORY, False, True, "story")
        backend._audio_last_sample = time.monotonic()
        backend._audio_strength = 10
        backend._drain()
        self.assertEqual(backend.previewA, 12)
        self.assertEqual(backend.audioPulseStrength, 12)
        with patch.object(backend._defeat_scene, "preview", return_value=OutputPreview(29, "impact")):
            backend._drain()
            self.assertEqual(backend.previewA, 30)  # 29 * 1.2 is capped, never 34.8.
            self.assertEqual(backend._bridge.update_auto_outputs.call_args.args[0], 30)

        backend._apply_state({"state": dict(state, current_hp=0), "received_at": time.monotonic(), "latency_ms": 1})
        self.assertEqual(backend.sensitivityMultiplier, 1.2)
        backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
        backend._drain()
        self.assertEqual(backend.sensitivityMultiplier, 1.0)
        self.assertEqual(backend.previewB, 15)

    def test_story_pause_does_not_block_death_penalty_and_does_not_replay_it(self):
        from test_defeat_scene import death, cg
        backend = self.backend
        backend._bridge = MagicMock()
        backend._device_connected = True

        def feed(state, now):
            with patch("ricca_dglab.backend.time.monotonic", return_value=now):
                backend._apply_state({"state": state, "received_at": now, "latency_ms": 1})
                backend._drain()

        feed(death(), 10)
        paused = cg(1)
        paused["story"]["act_screen_paused"] = True
        feed(paused, 11)
        feed(paused, 11.1)
        feed(paused, 11.2)
        self.assertEqual(backend.previewA, backend.deathStrength)
        backend._bridge.set_auto_enabled.assert_called_with(True)
        backend._bridge.set_paused.assert_called_with(False)
        self.assertFalse(backend.outputPaused)
        self.assertEqual(backend.priorityOutputStatus, "死亡惩罚")
        feed(paused, 13.9)
        self.assertEqual(backend.previewA, backend.deathStrength)
        feed(paused, 14.1)
        self.assertEqual(backend.previewA, 0)
        backend._bridge.set_auto_enabled.assert_called_with(False)
        for now in (41, 41.1, 41.2):
            feed(cg(1), now)
        self.assertEqual(backend.previewA, 0)

    def test_ordinary_manual_pause_cannot_cancel_death_but_emergency_can(self):
        from test_defeat_scene import death, cg
        backend = self.backend
        backend._bridge = MagicMock()
        backend._device_connected = True
        now = time.monotonic()
        backend._apply_state({"state": death(), "received_at": now, "latency_ms": 1})
        state = cg(1)
        state["story"]["act_screen_paused"] = True
        backend._apply_state({"state": state, "received_at": now, "latency_ms": 1})
        self.assertTrue(backend._defeat_scene.entry_pending)
        backend.toggleOutputPause()
        self.assertTrue(backend._defeat_scene.entry_pending)
        for _ in range(3):
            backend._apply_state({"state": cg(1), "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()
        self.assertTrue(backend.userOutputPaused)
        self.assertEqual(backend.previewA, backend.deathStrength)
        backend._bridge.set_auto_enabled.assert_called_with(True)
        backend.emergencyStop()
        backend._drain()
        self.assertEqual(backend.previewA, 0)
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertTrue(backend._stop_latched)

    def test_hp_edge_punishment_survives_scene_pause_outranks_stronger_loop_and_never_duplicates(self):
        from test_defeat_scene import death, cg
        backend = self.backend
        backend._bridge = MagicMock()
        backend._device_connected = True
        for policy in backend._config.values["channel_policies"].values():
            policy["rules"]["player_down"]["custom_strength"] = 5
        backend._refresh_mapping_config()

        def feed(state, now):
            with patch("ricca_dglab.backend.time.monotonic", return_value=now):
                backend._apply_state({"state": state, "received_at": now, "latency_ms": 1})
                backend._drain()

        feed(dict(death(), current_hp=31, max_hp=31), 10)
        backend.toggleOutputPause()
        feed(dict(death(), max_hp=31, is_paused=True, pause_mask=1), 11)
        self.assertEqual(backend.previewA, 5)
        self.assertFalse(backend.outputPaused)
        backend._bridge.set_auto_enabled.assert_called_with(True)
        for now in (11.1, 11.2, 11.3):
            feed(dict(cg(0), is_paused=True, pause_mask=1), now)
        self.assertEqual(backend.previewA, 5)  # Even the numerically stronger loop must yield.
        feed(dict(cg(0), is_paused=True, pause_mask=1), 14)
        self.assertEqual(backend.previewA, 0)  # Normal manual pause still stops the loop.
        backend.toggleOutputPause()
        feed(dict(cg(0), is_paused=True, pause_mask=1), 14.1)
        self.assertEqual(backend.previewA, backend.mediumStrength)
        self.assertEqual(backend.priorityOutputStatus, "败北互动")
        backend._bridge.set_paused.assert_called_with(False)
        backend.emergencyStop()
        feed(cg(0), 14.2)
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertEqual(backend.priorityOutputStatus, "")

    def test_scene_read_gap_preserves_death_evidence_and_loop_requires_fresh_confirmation(self):
        from test_defeat_scene import death, cg
        backend = self.backend
        backend._bridge = MagicMock()
        backend._device_connected = True
        backend._apply_state({"state": death(), "received_at": time.monotonic(), "latency_ms": 1})
        backend._queue.put(("telemetry_error", {"detail": "scene transition read gap"}))
        backend._drain()
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertTrue(backend._defeat_scene.pending_root)
        for _ in range(3):
            backend._apply_state({"state": cg(0), "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()
        self.assertEqual(backend.previewA, backend.deathStrength)
        backend._queue.put(("telemetry_error", {"detail": "one failed read"}))
        backend._drain()
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertEqual(backend._defeat_scene.confirm_count, 0)
        for _ in range(3):
            backend._apply_state({"state": cg(0), "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()
        backend._bridge.set_auto_enabled.assert_called_with(True)

    def test_real_hp_edge_allows_interaction_even_when_candidate_hint_was_missing(self):
        from test_defeat_scene import death, cg
        backend = self.backend
        backend._bridge = MagicMock()
        backend._device_connected = True
        for hp in (31, 0):
            state = dict(death(), current_hp=hp, max_hp=31, defeat_scene_hint="")
            backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
        backend._death_penalty.cancel()  # Test only the subsequent loop, not the cue.
        for _ in range(3):
            backend._apply_state({"state": cg(0), "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()
        self.assertEqual(backend.previewA, backend.mediumStrength)
        self.assertEqual(backend.priorityOutputStatus, "败北互动")

    def ready_device(self):
        from test_capture import snapshot
        backend = self.backend
        backend._bridge = MagicMock()
        backend._safety.last_player_address = "0x2000"
        backend._safety.valid_player_samples = 10
        state = snapshot()
        state.update(connected=True, status="ok", build_supported=True)
        backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
        backend._apply_bridge({"event": "connected"})
        backend._drain()
        return backend, state

    def test_connection_automatically_outputs_without_channel_tests(self):
        backend, _ = self.ready_device()
        self.assertFalse(backend.deviceTestsComplete)
        self.assertTrue(backend.outputArmed)
        backend._bridge.manual_test.assert_not_called()
        backend._bridge.set_auto_enabled.assert_called_with(True)
        self.assertEqual(backend._bridge.update_auto_outputs.call_args.kwargs["hard_cap"], 30)

    def test_auto_output_needs_saved_cap_and_completed_onboarding(self):
        backend, _ = self.ready_device()
        backend._config.values["onboarding_completed"] = False
        backend._drain()
        self.assertFalse(backend.outputArmed)
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertTrue(backend.completeOnboarding("0"))
        backend._drain()
        self.assertFalse(backend.outputArmed)
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertTrue(backend.completeOnboarding("20"))
        backend._drain()
        self.assertTrue(backend.outputArmed)
        backend._bridge.set_auto_enabled.assert_called_with(True)
        self.assertEqual(backend._bridge.update_auto_outputs.call_args.kwargs["hard_cap"], 20)

    def test_emergency_stays_stopped_through_reconnect_save_and_telemetry(self):
        backend, state = self.ready_device()
        backend.emergencyStop()
        backend._apply_bridge({"event": "disconnected"})
        backend._apply_bridge({"event": "connected"})
        self.assertTrue(backend.saveIntensitySettings(5, 10, 15, 20, 25))
        for _ in range(3):
            backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()
            self.assertFalse(backend.outputArmed)
            backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertTrue(backend.userOutputPaused)
        backend.toggleOutputPause()
        backend._drain()
        backend._bridge.set_auto_enabled.assert_called_with(True)

    def test_invalid_reads_scene_build_and_stale_remain_zero(self):
        backend, state = self.ready_device()
        for update in ({"build_supported": False}, {"scene": "other"}, {"pause_mask": 1}):
            invalid = dict(state, **update)
            backend._apply_state({"state": invalid, "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()
            backend._bridge.set_auto_enabled.assert_called_with(False)
        backend._queue.put(("telemetry_error", {"detail": "read failed"}))
        backend._drain()
        backend._bridge.set_auto_enabled.assert_called_with(False)
        backend._reader_error = ""
        backend._decision = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        backend._last_received = backend._safety.last_success = time.monotonic() - 1
        backend._drain()
        backend._bridge.set_auto_enabled.assert_called_with(False)

    def test_disconnect_clears_events_and_reconnect_keeps_manual_pause(self):
        backend, _ = self.ready_device()
        backend._mapping.clear_pulses = MagicMock()
        backend._apply_bridge({"event": "disconnected"})
        backend._bridge.set_auto_enabled.assert_called_with(False)
        backend._mapping.clear_pulses.assert_called_once()
        backend.toggleOutputPause()
        backend._apply_bridge({"event": "connected"})
        backend._drain()
        self.assertFalse(backend.outputArmed)
        self.assertTrue(backend.userOutputPaused)
        backend.toggleOutputPause()
        backend._drain()
        self.assertTrue(backend.outputArmed)

    def test_watchdog_requires_explicit_resume(self):
        backend, _ = self.ready_device()
        backend._apply_bridge({"event": "output_timeout"})
        backend._drain()
        self.assertTrue(backend.userOutputPaused)
        backend._bridge.set_auto_enabled.assert_called_with(False)
        backend.toggleOutputPause()
        backend._drain()
        backend._bridge.set_auto_enabled.assert_called_with(True)

    def test_defeat_scene_zero_hp_gate_entry_loop_dialogue_and_manual_stop(self):
        from test_defeat_scene import death, cg
        backend = self.backend
        backend._bridge = MagicMock()
        backend._output_armed = True
        backend._device_connected = True

        def feed(state, now):
            with patch("ricca_dglab.backend.time.monotonic", return_value=now):
                backend._apply_state({"state": state, "received_at": now, "latency_ms": 1})
                backend._drain()

        feed(death(), 10)
        self.assertTrue(backend.outputArmed)  # authorization retained, output zero
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertEqual((backend.previewA, backend.previewB), (0, 0))
        for now in (10.1, 10.2, 10.3):
            feed(cg(1), now)
        self.assertEqual(backend.previewA, backend.deathStrength)
        backend._bridge.set_auto_enabled.assert_called_with(True)
        kwargs = backend._bridge.update_auto_outputs.call_args.kwargs
        self.assertEqual(kwargs["hard_cap"], 30)
        self.assertIn("defeat:", kwargs["wave_key_a"])
        feed(cg(0), 15)
        self.assertEqual(backend.previewA, backend.mediumStrength)
        with patch("ricca_dglab.backend.time.monotonic", return_value=15):
            self.assertIn("互动循环", backend.defeatSceneStatus)
        backend.toggleOutputPause()
        feed(cg(0), 15.1)
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertEqual(backend.previewA, 0)
        backend.toggleOutputPause()
        for now in (15.2, 15.3, 15.4):
            feed(cg(0), now)
        self.assertEqual(backend.previewA, backend.mediumStrength)
        feed(cg(1), 15.5)
        self.assertEqual(backend.previewA, 0)
        backend.emergencyStop()
        feed(cg(0), 15.6)
        self.assertFalse(backend.outputArmed)
        backend._bridge.set_auto_enabled.assert_called_with(False)

    def test_onboarding_blocks_device_output_and_rejects_invalid_manual_input(self):
        backend = self.backend
        backend._config.values["onboarding_completed"] = False
        backend._demo = False
        backend._device_connected = True
        backend._tested_channels = {"A", "B"}
        backend._last_received = time.monotonic()
        backend._state["build_supported"] = True
        backend._decision = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        self.assertFalse(backend.canRunDeviceTest)
        self.assertFalse(backend.canArmOutput)
        for value in ("", " ", "-1", "101", "1.5", "abc", "1e2"):
            self.assertFalse(backend.completeOnboarding(value), value)
            self.assertFalse(backend.onboardingCompleted)
        self.assertTrue(backend.completeOnboarding("37"))
        self.assertEqual(backend.hardCap, 37)
        self.assertTrue(backend.onboardingCompleted)
        restored = ProductConfig(backend._config.path)
        self.assertEqual(restored.values["hard_cap"], 37)
        self.assertTrue(restored.values["onboarding_completed"])
        self.assertFalse(backend.outputArmed)
        self.assertFalse(backend.deviceTestsComplete)

    def test_onboarding_zero_is_saved_and_disables_output_including_manual_tests(self):
        from test_capture import snapshot, READY
        backend = self.backend
        backend._bridge = MagicMock()
        self.assertTrue(backend.completeOnboarding("0"))
        self.assertEqual(backend.hardCap, 0)
        self.assertEqual(backend._mapping.hard_cap, 0)
        self.assertEqual(ProductConfig(backend._config.path).values["hard_cap"], 0)
        backend._mapping.reconcile_capture(snapshot(), now=1)
        self.assertEqual(backend._mapping.preview(READY, 1).strength_b, 0)
        backend._device_connected = True
        self.assertFalse(backend.runDeviceTest("A"))
        self.assertFalse(backend.canArmOutput)
        self.assertIn("0", backend.outputStatus)
        self.assertTrue(backend.completeOnboarding("100"))
        self.assertEqual(backend.hardCap, 100)

    def test_onboarding_failed_save_does_not_complete_or_apply_a_new_cap(self):
        backend = self.backend
        backend._config.values["onboarding_completed"] = False
        backend._output_armed = True
        with patch.object(backend._config, "save", side_effect=OSError("test write denied")):
            self.assertFalse(backend.completeOnboarding("12"))
        self.assertFalse(backend.outputArmed)
        self.assertFalse(backend.onboardingCompleted)
        self.assertEqual(backend.hardCap, 30)
        self.assertEqual(backend._mapping.hard_cap, 30)
        self.assertIn("保存失败", backend.onboardingError)

    def test_small_cap_limits_device_test_and_personal_zero_stops_a_running_test(self):
        backend = self.backend
        backend._bridge = MagicMock()
        self.assertTrue(backend.completeOnboarding("3"))
        backend._device_connected = True
        self.assertTrue(backend.runDeviceTest("A"))
        self.assertEqual(backend._bridge.manual_test.call_args.args[0], 3)
        backend._bridge.emergency_stop.reset_mock()
        self.assertTrue(backend.saveIntensitySettings(0, 0, 0, 0, 0))
        backend._bridge.emergency_stop.assert_called_once()
        self.assertEqual(backend._manual_test_channel, "")
        self.assertFalse(backend.canRunDeviceTest)

    def test_socket_error_clears_qr_and_address_switch_regenerates_it_safely(self):
        backend = self.backend
        bridge = backend._bridge
        bridge.available_lan_ips = ("192.168.1.2", "10.8.0.2")
        bridge.available_lan_interfaces = [
            {"address": "192.168.1.2", "label": "Wi-Fi · 192.168.1.2"},
            {"address": "10.8.0.2", "label": "VPN · 10.8.0.2"},
        ]
        backend._lan_addresses = list(bridge.available_lan_ips)
        backend._lan_ip = bridge.lan_ip = "192.168.1.2"
        bridge.server_ready = True
        bridge.controller_id = "test-controller"
        backend._output_armed = True
        backend.selectLanAddress("10.8.0.2")
        self.assertFalse(backend.outputArmed)
        backend._drain()
        self.assertIn("ws://10.8.0.2:", backend.qrUrl)
        self.assertTrue(backend.qrSource.startswith("data:image/png;base64,"))
        backend._apply_bridge({"event": "server_error", "detail": "端口 9999 已被占用"})
        self.assertFalse(backend.serverReady)
        self.assertEqual(backend.qrSource, "")
        self.assertIn("占用", backend.serverError)
        with patch.object(bridge, "refresh_lan_ips"), patch("ricca_dglab.backend.port_listeners", return_value=[
                {"pid": 1234, "name": "pythonw.exe", "ours": False}]):
            backend.diagnoseConnection()
        self.assertIn("1234", backend.connectionDiagnostics)
        self.assertIn("VPN", backend.connectionDiagnostics)
        self.assertFalse(backend.restartSocket())  # UI tests/demo never open sockets.

    def test_game_and_manual_pause_zero_both_channels_and_resume_current_capture(self):
        from test_capture import snapshot
        backend = self.backend
        backend._bridge = MagicMock()
        policies = default_channel_policies()
        policies["A"]["mode"] = "action"
        backend._config.values["channel_policies"] = policies
        backend._refresh_mapping_config()
        backend._safety.last_player_address = "0x2000"
        backend._safety.valid_player_samples = 10
        backend._output_armed = backend._device_connected = True

        def apply(**updates):
            state = snapshot(**updates)
            state.update(connected=True, status="ok", build_supported=True)
            backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()

        apply()
        self.assertEqual((backend.previewA, backend.previewB), (15, 15))
        backend._manual_test_channel = "A"
        apply(game_ui={"is_user_pause": True})
        self.assertEqual((backend.previewA, backend.previewB), (0, 0))
        backend._bridge.set_paused.assert_called_with(True)
        backend._bridge.set_auto_enabled.assert_called_with(False)
        self.assertTrue(backend.outputArmed)
        self.assertFalse(backend.canRunDeviceTest)
        self.assertEqual(backend._manual_test_channel, "")
        apply()
        self.assertEqual((backend.previewA, backend.previewB), (15, 15))
        backend._bridge.set_paused.assert_called_with(False)
        backend._bridge.set_auto_enabled.assert_called_with(True)
        backend.toggleOutputPause()
        self.assertEqual((backend.previewA, backend.previewB), (0, 0))
        apply(count=5)
        self.assertEqual((backend.previewA, backend.previewB), (0, 0))
        self.assertFalse(backend.outputArmed)
        self.assertTrue(backend.userOutputPaused)
        backend.toggleOutputPause()
        apply(count=6)
        self.assertEqual((backend.previewA, backend.previewB), (15, 15))
        self.assertEqual(backend.channelPolicies, policies)
        backend.emergencyStop()
        apply()
        self.assertFalse(backend.outputArmed)
        backend._bridge.set_auto_enabled.assert_called_with(False)

    def test_story_pause_blocks_audio_in_both_channels_until_fresh_resumed_sample(self):
        backend = self.backend
        backend._bridge = MagicMock()
        policies = default_channel_policies()
        policies["A"]["mode"] = policies["B"]["mode"] = "audio"
        backend._config.values.update(audio_empathy_enabled=True, channel_policies=policies)
        backend._refresh_mapping_config()
        backend._output_armed = backend._device_connected = True

        def apply(paused):
            state = {"connected": True, "status": "ok", "build_supported": True, "scene": "atd",
                     "story": {"asset_name": "ADV/test.csv", "act_screen_paused": paused}}
            backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()

        def audio(when=None):
            if when is None:
                time.sleep(.02)  # Windows monotonic() ticks can be ~15.6 ms.
            backend._apply_audio_sample({"rms": .2, "peak": .3, "points": [80]*16,
                                         "received_at": time.monotonic() if when is None else when})
            backend._drain()

        apply(False)
        audio()
        self.assertGreater(backend.previewA, 0)
        self.assertGreater(backend.previewB, 0)
        old_sample = time.monotonic()
        apply(True)
        audio()
        self.assertEqual((backend.previewA, backend.previewB), (0, 0))
        self.assertEqual(backend.audioPulseStrength, 0)
        self.assertTrue(backend.outputArmed)
        apply(False)
        audio(old_sample)
        self.assertEqual((backend.previewA, backend.previewB), (0, 0))
        audio()
        self.assertGreater(backend.previewB, 0)
        backend.toggleOutputPause()
        audio()
        self.assertEqual((backend.previewA, backend.previewB), (0, 0))

    def test_capture_overview_and_escape_zero_the_mock_bridge(self):
        from test_capture import snapshot
        backend = self.backend
        backend._bridge = MagicMock()  # No socket/device traffic in this test.
        backend._safety.last_player_address = "0x2000"
        backend._safety.valid_player_samples = 10

        def apply(state):
            state.update(connected=True, status="ok", build_supported=True)
            backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
            backend._drain()

        apply(snapshot("0x0", acceptance=False))
        backend._output_armed = backend._device_connected = True
        apply(snapshot(count=1))
        self.assertGreater(backend.previewB, 0)
        self.assertTrue(backend.captureStatus["active"])
        self.assertAlmostEqual(backend.captureStatus["progress"], 1/12)
        self.assertGreater(backend._bridge.update_auto_outputs.call_args.kwargs["strength_b"], 0)
        apply(snapshot(count=5))
        self.assertEqual(backend.waveB, "tap")
        backend._queue.put(("telemetry_error", {"detail": "test read failure"}))
        backend._drain()
        self.assertEqual(backend.previewB, 0)
        self.assertFalse(backend.captureStatus["known"])
        apply(snapshot(count=6))
        self.assertEqual(backend.previewB, backend.mediumStrength)  # Valid state resumes a hold, not a short event.
        apply(snapshot(count=7))
        self.assertGreater(backend.previewB, 0)
        apply(snapshot("0x0", count=12, acceptance=False))
        self.assertFalse(backend.captureStatus["active"])
        self.assertEqual(backend.captureStatus["count"], 0)
        self.assertEqual(backend.previewB, 0)
        self.assertEqual(backend._bridge.update_auto_outputs.call_args.kwargs["strength_b"], 0)
        self.assertEqual(backend._bridge.update_auto_outputs.call_args.kwargs["frames_b"], ())
        backend._last_received = time.monotonic() - 1
        self.assertFalse(backend.captureStatus["known"])

    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        config = ProductConfig(Path(self.temp.name) / "settings.json")
        config.values["onboarding_completed"] = True
        with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
                patch("ricca_dglab.backend.TelemetryWorker.start"), \
                patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
            self.backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
        self.backend._timer.stop()
        # Production eligibility with a stopped fake reader and no Socket thread.
        self.backend._demo = False

    def tearDown(self):
        self.backend.shutdown()
        self.temp.cleanup()

    def test_channel_save_keeps_other_channel_and_disarms(self):
        backend = self.backend
        policy = default_channel_policies()["A"]
        policy["mode"] = "both"
        policy["rules"]["hit_normal"].update(custom_strength=13, duration=0.1, wave="guard")
        backend._output_armed = True
        self.assertTrue(backend.saveChannelPolicy("A", policy))
        self.assertFalse(backend.outputArmed)
        self.assertEqual(backend.channelPolicies["B"]["mode"], "action")
        restored = ProductConfig(backend._config.path).values["channel_policies"]
        self.assertEqual(restored["A"]["rules"]["hit_normal"]["custom_strength"], 13)
        self.assertEqual(restored["A"]["rules"]["hit_normal"]["duration"], 0.1)

    def test_hud_toggle_persists_without_changing_output_permission(self):
        backend = self.backend
        backend._output_armed = True
        self.assertTrue(backend.setGameHudEnabled(False))
        self.assertFalse(backend.gameHudEnabled)
        self.assertTrue(backend.outputArmed)
        self.assertFalse(ProductConfig(backend._config.path).values["game_hud_enabled"])

    def test_audio_routes_only_to_explicit_audio_channel_in_story(self):
        backend = self.backend
        policies = default_channel_policies()
        policies["A"]["mode"] = "audio"
        backend._config.values.update(audio_empathy_enabled=True, channel_policies=policies)
        backend._refresh_mapping_config()
        now = time.monotonic()
        backend._last_received = backend._safety.last_success = now
        backend._audio_last_sample = now
        backend._audio_strength = 12
        backend._decision = SafetyDecision(RuntimeMode.STORY, False, True, "story")
        backend._drain()
        self.assertEqual((backend.previewA, backend.previewB), (12, 0))
        self.assertEqual(backend.waveA, "audio-reactive")
        backend._decision = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        backend._drain()
        self.assertEqual((backend.previewA, backend.previewB), (0, 0))

    def test_atd_audio_sample_has_meter_and_routes_with_explicit_opt_in(self):
        backend = self.backend
        policies = default_channel_policies()
        policies["B"]["mode"] = "audio"
        backend._config.values.update(audio_empathy_enabled=True, channel_policies=policies)
        backend._refresh_mapping_config()
        now = time.monotonic()
        backend._state = {"scene": "atd", "story": {"asset_name": "ADV/Scene3D_RiccaHellplant/Scene3D_RiccaHellplant.csv"},
                          "connected": True, "status": "ok", "build_supported": True}
        backend._decision = backend._safety.observe(backend._state, now)
        backend._last_received = now
        backend._apply_audio_sample({"rms": 0.2, "peak": 0.3, "points": [70] * 16, "received_at": now})
        backend._drain()
        self.assertTrue(backend.storySceneActive)
        self.assertGreater(backend.audioLevel, 0)
        self.assertGreater(backend.audioPulseStrength, 0)
        self.assertGreater(backend.previewB, 0)
        self.assertEqual(backend.previewA, 0)
        self.assertEqual(backend.waveB, "audio-reactive")
        self.assertFalse(backend.outputArmed)


if __name__ == "__main__":
    unittest.main()
