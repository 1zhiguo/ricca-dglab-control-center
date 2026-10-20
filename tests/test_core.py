from __future__ import annotations

import json
import queue
import time
from pathlib import Path
import tempfile
import unittest

from ricca_dglab.dglab_bridge import (
    DGLabBridge,
    clamp_strength,
    pulse_message,
    strength_message,
)
from ricca_dglab.audio_pulse import AudioPulseMapper
from ricca_dglab.events import EventDetector
from ricca_dglab.mapping import RiccaMappingEngine
from ricca_dglab.models import GameEvent, RuntimeMode, SafetyDecision
from ricca_dglab.product_config import ProductConfig, default_channel_policies
from ricca_dglab.safety import SafetyGovernor
from ricca_dglab.waveforms import PRESETS, custom_frames, frames_for, waveform_catalog


def gameplay(**updates):
    state = {
        "connected": True,
        "status": "ok",
        "build_supported": True,
        "scene": "gameplay",
        "is_paused": False,
        "player_address": "0x1234",
        "current_hp": 100.0,
        "max_hp": 100.0,
        "action_trigger_name": "stand_idle",
        "action_trigger_enabled": True,
        "direction_time_scale": 1.0,
        "armor": {"current_level": -1, "current_hp": 10.0, "max_hp": 10.0,
                  "last_break_time": -99999.0},
    }
    state.update(updates)
    return state


class SafetyTests(unittest.TestCase):
    def test_observed_atd_story_is_allowed_but_not_unknown_atd_or_loading(self):
        state = gameplay(scene="atd", story={"asset_name": "ADV/Scene3D_RiccaHellplant/Scene3D_RiccaHellplant.csv"})
        decision = SafetyGovernor().observe(state, 1)
        self.assertTrue(decision.allow_story_output)
        self.assertFalse(decision.allow_gameplay_output)
        self.assertFalse(SafetyGovernor().observe(gameplay(scene="atd"), 1).allow_story_output)
        state["stage"] = {"scene_change_playing": True}
        self.assertFalse(SafetyGovernor().observe(state, 1).allow_story_output)
        state["stage"] = {}
        state["is_paused"] = True
        self.assertFalse(SafetyGovernor().observe(state, 1).allow_story_output)

    def test_requires_six_stable_samples(self):
        governor = SafetyGovernor()
        decisions = [governor.observe(gameplay(), index * 0.05) for index in range(6)]
        self.assertTrue(all(not item.allow_gameplay_output for item in decisions[:5]))
        self.assertEqual(decisions[-1].mode, RuntimeMode.GAMEPLAY_READY)

    def test_pause_story_and_unsupported_build_fail_closed(self):
        self.assertEqual(SafetyGovernor().observe(gameplay(is_paused=True), 1).mode,
                         RuntimeMode.PAUSED)
        story = gameplay(scene="adv")
        decision = SafetyGovernor().observe(story, 1)
        self.assertFalse(decision.allow_gameplay_output)
        self.assertTrue(decision.allow_story_output)
        unsupported = gameplay(build_supported=False)
        self.assertEqual(SafetyGovernor().observe(unsupported, 1).mode,
                         RuntimeMode.UNSUPPORTED_BUILD)
        paused_story = SafetyGovernor().observe(gameplay(scene="adv", is_paused=True), 1)
        self.assertFalse(paused_story.allow_story_output)

    def test_zero_hp_closes_output_before_game_over_flag(self):
        decision = SafetyGovernor().observe(gameplay(current_hp=0), 1.0)
        self.assertEqual(decision.mode, RuntimeMode.PLAYER_DOWN)
        self.assertFalse(decision.allow_gameplay_output)


class EventTests(unittest.TestCase):
    def test_pause_discards_unfinished_damage_instead_of_replaying_on_resume(self):
        detector = EventDetector()
        detector.ingest(gameplay(), 1)
        detector.ingest(gameplay(current_hp=95), 1.1)
        detector.ingest(gameplay(current_hp=95, is_paused=True), 1.2)
        self.assertFalse(any(event.kind == "damage" for event in detector.tick(2)))
        events = detector.ingest(gameplay(current_hp=95), 2.1)
        self.assertFalse(any(event.kind == "damage" for event in events))

    def test_damage_writes_are_aggregated(self):
        detector = EventDetector()
        detector.ingest(gameplay(current_hp=100), 1.0)
        self.assertFalse(any(e.kind == "damage" for e in detector.ingest(
            gameplay(current_hp=93), 1.05)))
        self.assertFalse(any(e.kind == "damage" for e in detector.ingest(
            gameplay(current_hp=88), 1.20)))
        events = detector.tick(1.51)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].data["amount"], 12.0)

    def test_action_edges_emit_named_event(self):
        detector = EventDetector()
        detector.ingest(gameplay(), 1.0)
        events = detector.ingest(gameplay(action_trigger_name="air_wall_blowOff"), 1.1)
        self.assertEqual([event.title for event in events if event.kind == "action"],
                         ["撞墙反弹"])

    def test_boss_catch_requires_paired_player_and_boss_hashes(self):
        detector = EventDetector()
        detector.ingest(gameplay(
            action_trigger_hash=0,
            boss={"action_trigger_hash": 0, "action_time": 0.0},
        ), 1.0)
        caught = gameplay(
            action_trigger_name="Unknown",
            action_trigger_hash=362220413,
            action_time=2.0111148,
            character_state_name="StandAction",
            boss={"action_trigger_hash": 662097121,
                  "action_time": 2.0111148,
                  "character_state_name": "StandAttack"},
            story={"speaker": "Iris", "stripped_message": "Look out! Shake him off!",
                   "asset_name": "ADV/stage25/stage25_event_18_02.csv"},
        )
        events = detector.ingest(caught, 1.1)
        catch_events = [event for event in events if event.kind == "boss_catch"]
        self.assertEqual(len(catch_events), 1)
        self.assertEqual(catch_events[0].data["action"], "boss_catch")

        detector = EventDetector()
        detector.ingest(gameplay(action_trigger_hash=0,
                                 boss={"action_trigger_hash": 0}), 2.0)
        player_only = gameplay(action_trigger_name="Unknown",
                               action_trigger_hash=362220413,
                               boss={"action_trigger_hash": 123})
        events = detector.ingest(player_only, 2.1)
        self.assertFalse(any(event.kind == "boss_catch" for event in events))

    def test_player_down_accepts_zero_hp_with_any_action_hash(self):
        detector = EventDetector()
        detector.ingest(gameplay(current_hp=10, action_trigger_hash=0), 1.0)
        events = detector.ingest(gameplay(
            current_hp=0,
            action_trigger_name="Unknown",
            action_trigger_hash=2141194317,
            character_state_name="Damage",
            action_time=3.5666578,
        ), 1.1)
        down_events = [event for event in events if event.kind == "player_down"]
        self.assertEqual(len(down_events), 1)
        self.assertEqual(down_events[0].data["hp"], 0)

        detector = EventDetector()
        detector.ingest(gameplay(current_hp=10, action_trigger_hash=0), 2.0)
        events = detector.ingest(gameplay(current_hp=0,
                                          action_trigger_hash=123), 2.1)
        self.assertEqual(sum(event.kind == "player_down" for event in events), 1)
        repeat = detector.ingest(gameplay(current_hp=0, action_trigger_hash=2141194317), 2.2)
        self.assertFalse(any(event.kind == "player_down" for event in repeat))

    def test_zero_hp_does_not_replay_on_attach_rebind_or_invalid_hp(self):
        for state in (gameplay(current_hp=0, player_address="0x5678"),
                      gameplay(current_hp=0, scene="atd"),
                      gameplay(current_hp=float("nan")),
                      gameplay(current_hp=-1), gameplay(current_hp=0, max_hp=0),
                      gameplay(current_hp=False), gameplay(current_hp=0, build_supported=False)):
            detector = EventDetector()
            detector.ingest(gameplay(current_hp=10), 1)
            self.assertFalse(any(e.kind == "player_down" for e in detector.ingest(state, 2)))
        detector = EventDetector()
        self.assertFalse(any(e.kind == "player_down" for e in detector.ingest(gameplay(current_hp=0), 1)))
        self.assertFalse(any(e.kind == "player_down" for e in detector.ingest(gameplay(current_hp=0), 2)))

    def test_rebind_cannot_become_false_damage(self):
        detector = EventDetector()
        detector.ingest(gameplay(current_hp=100, player_address="0x1111"), 1.0)
        events = detector.ingest(gameplay(current_hp=10, player_address="0x2222"), 1.1)
        self.assertFalse(any(event.kind == "damage" for event in detector.tick(2.0)))
        rebind = next(event for event in events if event.kind == "rebind")
        self.assertEqual(rebind.data["armor_level_after"], -1)

    def test_armor_break_uses_dedicated_break_clock(self):
        detector = EventDetector()
        detector.ingest(gameplay(), 1.0)
        armor = {"current_level": 0, "current_hp": 10.0, "max_hp": 10.0,
                 "last_break_time": 24.86617}
        events = detector.ingest(gameplay(armor=armor), 1.1)
        armor_events = [event for event in events if event.kind == "armor_break"]
        self.assertEqual(len(armor_events), 1)
        self.assertEqual(armor_events[0].data["level_before"], -1)
        self.assertEqual(armor_events[0].data["level_after"], 0)


class MappingTests(unittest.TestCase):
    def test_guard_and_unknown_actions_never_pulse_even_with_legacy_guard_enabled(self):
        policies = default_channel_policies()
        for policy in policies.values():
            policy["mode"] = "both"
            policy["rules"]["guard"] = {"enabled": True, "tier": "high", "wave": "guard", "duration": 3}
        mapper = RiccaMappingEngine(channel_policies=policies)
        safety = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        for index, action in enumerate(["stand_guard_start", "stand_guard_hit", "Unknown"] * 5):
            now = 10 + index * 0.1
            mapper.accept([GameEvent(index, now, "now", "action", action, data={"action": action})])
            preview = mapper.preview(safety, now)
            self.assertEqual((preview.strength_a, preview.strength_b), (0, 0))

    def test_stronger_takes_over_weaker_is_dropped_and_equal_refreshes(self):
        policies = default_channel_policies()
        policies["A"]["mode"] = "both"
        policies["A"]["rules"]["damage_heavy"].update(custom_strength=25, duration=3)
        policies["A"]["rules"]["hit_small"].update(custom_strength=5, duration=3)
        policies["A"]["rules"]["heavy_land"].update(custom_strength=30, duration=0.5)
        mapper = RiccaMappingEngine(channel_policies=policies)
        ready = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        mapper.accept([GameEvent(1, 1.0, "now", "damage", "hit", data={"amount": 10})])
        mapper.accept([GameEvent(2, 1.1, "now", "action", "small", data={"action": "stand_damage_small"})])
        self.assertEqual(mapper.preview(ready, 1.11).wave_a, "heavy_land")
        self.assertTrue(mapper.pulse_token("A").startswith("1:"))
        mapper.accept([GameEvent(3, 1.2, "now", "action", "heavy", data={"action": "stand_landing_blowOff"})])
        self.assertTrue(mapper.pulse_token("A").startswith("3:"))
        mapper.accept([GameEvent(4, 1.2, "now", "action", "heavy", data={"action": "stand_landing_blowOff"})])
        self.assertTrue(mapper.pulse_token("A").startswith("4:"))
        # Superseded/ignored events must never resume, despite their 3s duration.
        self.assertEqual(mapper.preview(ready, 1.71).strength_a, 0)

    def test_per_channel_absolute_hp_boundaries_and_custom_strength(self):
        policies = default_channel_policies()
        policies["B"]["mode"] = "hp"
        policies["B"]["damage_light_max"] = 1
        policies["B"]["damage_medium_max"] = 2
        policies["A"]["rules"]["damage_light"].update(custom_strength=12, duration=0.1, wave="guard")
        mapper = RiccaMappingEngine(channel_policies=policies)
        ready = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        mapper.accept([GameEvent(1, 1, "now", "damage", "damage", data={"amount": 3})])
        result = mapper.preview(ready, 1)
        self.assertEqual((result.strength_a, result.wave_a), (12, "guard"))
        self.assertEqual(result.wave_b, "heavy_land")
        self.assertEqual(mapper.preview(ready, 1.101).strength_a, 0)
        mapper.accept([GameEvent(2, 2, "now", "damage", "damage", data={"amount": 6})])
        self.assertEqual(mapper.preview(ready, 2).wave_a, "impact")
        mapper.accept([GameEvent(3, 4, "now", "damage", "damage", data={"amount": 6.01})])
        self.assertEqual(mapper.preview(ready, 4).wave_a, "heavy_land")

    def test_audio_off_and_cross_routing_do_not_leak_events(self):
        policies = default_channel_policies()
        policies["A"]["mode"] = "action"
        policies["B"]["mode"] = "audio"
        mapper = RiccaMappingEngine(channel_policies=policies)
        ready = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        mapper.accept([GameEvent(1, 1, "now", "damage", "damage", data={"amount": 30})])
        self.assertEqual(mapper.preview(ready, 1).strength_a, 0)
        mapper.accept([GameEvent(2, 1.1, "now", "action", "small", data={"action": "stand_damage_small"})])
        result = mapper.preview(ready, 1.1)
        self.assertEqual(result.wave_a, "tap")
        self.assertEqual(result.strength_b, 0)
        paused = SafetyDecision(RuntimeMode.PAUSED, False, False, "paused")
        mapper.preview(paused, 1.12)
        self.assertEqual(mapper.preview(ready, 1.13).strength_a, 0)

    def test_preview_never_exceeds_cap_and_closes_when_unsafe(self):
        detector = EventDetector()
        detector.ingest(gameplay(current_hp=100), 1.0)
        detector.ingest(gameplay(current_hp=50), 1.1)
        damage = detector.tick(1.5)
        mapper = RiccaMappingEngine(hard_cap=30)
        mapper.accept(damage)
        governor = SafetyGovernor()
        ready = None
        for index in range(6):
            ready = governor.observe(gameplay(), 1.5 + index * 0.01)
        preview = mapper.preview(ready, 1.56)
        self.assertLessEqual(preview.strength_a, 30)
        unsafe = governor.observe(gameplay(is_paused=True), 1.57)
        self.assertEqual(mapper.preview(unsafe, 1.57).strength_a, 0)

    def test_armor_break_latches_at_one_point_two_without_stacking(self):
        mapper = RiccaMappingEngine(hard_cap=30)

        def armor_break(sequence, break_time, level_after=None):
            data = {"last_break_time": break_time, "action": "armor_break"}
            if level_after is not None:
                data["level_after"] = level_after
            return GameEvent(sequence, 10.0 + sequence, "now", "armor_break",
                             "护甲破碎", data=data)

        mapper.accept([armor_break(1, 24.86617, 0)])
        self.assertEqual(mapper.sensitivity_stage, 1)
        self.assertEqual(mapper.sensitivity_multiplier, 1.2)

        # Replaying an already handled break must not raise the stage twice.
        mapper.accept([armor_break(1, 24.86617, 0)])
        self.assertEqual(mapper.sensitivity_stage, 1)

        # A repeated/lower tier without a confirmed rebind cannot raise the
        # current sensitivity stage.
        mapper.accept([armor_break(2, 5.0, 0)])
        self.assertEqual(mapper.sensitivity_stage, 1)

        mapper.accept([armor_break(3, 37.566204, 1),
                       armor_break(4, 49.0, 2)])
        self.assertEqual(mapper.sensitivity_stage, mapper.max_sensitivity_stage)
        self.assertEqual(mapper.sensitivity_multiplier, 1.2)

        mapper.reset_sensitivity()
        self.assertEqual(mapper.sensitivity_stage, 0)

    def test_mid_session_sync_does_not_override_manual_reset(self):
        mapper = RiccaMappingEngine(hard_cap=30)
        mapper.synchronize_sensitivity(1)
        self.assertEqual(mapper.sensitivity_stage, 0)  # Stored tiers never synthesize a break.

        mapper.reset_sensitivity()
        mapper.synchronize_sensitivity(2)
        self.assertEqual(mapper.sensitivity_stage, 0)

    def test_respawn_rebind_rebases_sensitivity_to_restored_armor(self):
        mapper = RiccaMappingEngine(hard_cap=30)
        mapper.observe_life(gameplay(armor={"current_level": 1}))
        mapper.rebase_sensitivity(1)
        self.assertEqual(mapper.sensitivity_stage, 1)
        mapper.observe_life(gameplay(player_address="0x2000", armor={"current_level": -1}))
        self.assertEqual(mapper.sensitivity_stage, 0)
        self.assertEqual(mapper.sensitivity_multiplier, 1.0)

    def test_same_actor_respawn_resets_even_if_armor_stays_broken(self):
        mapper = RiccaMappingEngine()
        mapper.observe_life(gameplay())
        mapper.rebase_sensitivity(2)
        mapper.observe_life(gameplay(current_hp=0))
        self.assertEqual(mapper.sensitivity_multiplier, 1.2)
        mapper.observe_life(gameplay(current_hp=100, armor={"current_level": 2}))
        self.assertEqual(mapper.sensitivity_multiplier, 1.0)

    def test_menu_reentry_and_process_restart_reset_but_story_pause_and_rebind_do_not(self):
        mapper = RiccaMappingEngine()
        mapper.observe_life(gameplay())
        mapper.rebase_sensitivity(2)
        mapper.observe_life(gameplay(is_paused=True))
        mapper.observe_life({**gameplay(), "scene": "adv"})
        mapper.observe_life(gameplay(player_address="0x2000", armor={"current_level": 2}))
        self.assertEqual(mapper.sensitivity_multiplier, 1.2)
        mapper.observe_life({**gameplay(), "scene": "other"})
        mapper.observe_life(gameplay())
        self.assertEqual(mapper.sensitivity_multiplier, 1.0)
        mapper.observe_life(gameplay(process_id=123455))
        mapper.rebase_sensitivity(1)
        mapper.observe_life(gameplay(process_id=123456))
        self.assertEqual(mapper.sensitivity_multiplier, 1.0)

    def test_death_penalty_is_bounded_and_visible_only_as_dry_run(self):
        mapper = RiccaMappingEngine(
            hard_cap=24,
            strengths={"low": 5, "medium": 10, "high": 18, "death": 24},
        )
        event = GameEvent(1, 10.0, "now", "player_down", "玩家倒下")
        mapper.accept([event])
        decision = SafetyDecision(RuntimeMode.PLAYER_DOWN, False, False, "hp is zero")
        preview = mapper.preview(decision, 10.2)
        self.assertEqual(preview.strength_a, 24)
        self.assertEqual(preview.strength_b, 24)
        self.assertEqual(preview.wave_a, "death_penalty")
        self.assertEqual(preview.reason, "death-preview-only")

    def test_disabled_boss_catch_remains_silent(self):
        mapper = RiccaMappingEngine()
        mapper.accept([GameEvent(1, 5.0, "now", "boss_catch", "Boss 捕获")])
        decision = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        preview = mapper.preview(decision, 5.1)
        self.assertEqual(preview.strength_b, 0)


class ProductConfigTests(unittest.TestCase):
    def test_channel_policy_migration_round_trip_and_limits(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            path = Path(temporary) / "settings.json"
            path.write_text(json.dumps({"event_rules": {"hit_small": {"wave": "guard"}}}), encoding="utf-8")
            config = ProductConfig(path)
            self.assertEqual(config.values["channel_policies"]["B"]["rules"]["hit_small"]["wave"], "guard")
            policies = config.values["channel_policies"]
            policies["A"]["mode"] = "both"
            policies["A"]["rules"]["hit_small"].update(duration=99, custom_strength=180)
            policies["B"]["rules"]["hit_small"]["duration"] = 0.001
            config.update({"channel_policies": policies})
            restored = ProductConfig(path).values["channel_policies"]
            self.assertEqual(restored["A"]["mode"], "both")
            self.assertEqual(restored["A"]["rules"]["hit_small"]["duration"], 3)
            self.assertEqual(restored["B"]["rules"]["hit_small"]["duration"], 0.1)
            self.assertEqual(restored["A"]["rules"]["hit_small"]["custom_strength"], 100)

    def test_default_strength_tiers_match_product_profile(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            config = ProductConfig(Path(temporary) / "settings.json")
            self.assertEqual(
                [config.values[key] for key in (
                    "strength_low", "strength_medium", "strength_high",
                    "strength_death", "hard_cap",
                )],
                [5, 15, 25, 25, 30],
            )

    def test_settings_round_trip_and_sanitize(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            path = Path(temporary) / "settings.json"
            config = ProductConfig(path)
            config.update({
                "strength_low": 4,
                "strength_medium": 9,
                "strength_high": 15,
                "strength_death": 22,
                "hard_cap": 24,
                "audio_empathy_enabled": True,
                "audio_device_id": "loopback-test",
                "audio_gate": 18,
                "game_executable_path": r"D:\Games\Ricca\HolyKnightRicca.exe",
            })
            restored = ProductConfig(path)
            self.assertEqual(restored.values["strength_death"], 22)
            self.assertEqual(restored.values["hard_cap"], 24)
            self.assertTrue(restored.values["audio_empathy_enabled"])
            self.assertEqual(restored.values["audio_device_id"], "loopback-test")
            self.assertEqual(restored.values["audio_gate"], 18)
            self.assertEqual(
                restored.values["game_executable_path"],
                r"D:\Games\Ricca\HolyKnightRicca.exe",
            )
            self.assertNotIn("story_audio", restored.values["event_rules"])

    def test_audio_pulse_mapper_respects_gate_and_cap(self):
        mapper = AudioPulseMapper()
        quiet = mapper.map(1e-8, sensitivity=55, gate=12, hard_cap=30)
        self.assertFalse(quiet["active"])
        loud = mapper.map(1.0, sensitivity=100, gate=12, hard_cap=30)
        self.assertTrue(loud["active"])
        self.assertLessEqual(loud["strength"], 30)

    def test_waveform_catalog_and_custom_frame_validation(self):
        catalog = waveform_catalog()
        self.assertGreaterEqual(len(catalog), 10)
        self.assertIn("official", {item["group"] for item in catalog})
        self.assertIn("builtin", {item["group"] for item in catalog})
        self.assertIn("official_heartbeat", PRESETS)
        self.assertTrue(frames_for("death_penalty"))
        frames = custom_frames(range(0, 80, 5), 80)
        self.assertEqual(len(frames), 16)
        self.assertTrue(all(len(frame) == 16 for frame in frames))
        with self.assertRaises(ValueError):
            custom_frames([0, 1], 80)


class SocketProtocolTests(unittest.TestCase):
    def test_strength_and_frame_validation(self):
        self.assertEqual(clamp_strength(80, 30), 30)
        self.assertEqual(strength_message("B", 99, 10), "strength-2+2+10")
        self.assertEqual(pulse_message("A", ["0011223344556677"]),
                         'pulse-A:["0011223344556677"]')
        with self.assertRaises(ValueError):
            pulse_message("A", ["not-a-frame"])

    def test_local_pairing_and_live_output_path(self):
        from websockets.sync.client import connect

        events = queue.Queue()
        bridge = DGLabBridge(events, port=0)
        bridge.start()
        try:
            deadline = time.monotonic() + 3.0
            while not bridge.server_ready and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(bridge.server_ready)
            with connect(f"ws://127.0.0.1:{bridge.port}/", open_timeout=2.0) as phone:
                hello = json.loads(phone.recv(timeout=2.0))
                phone_id = hello["clientId"]
                phone.send(json.dumps({
                    "type": "bind",
                    "clientId": bridge.controller_id,
                    "targetId": phone_id,
                    "message": "DGLAB",
                }))
                reply = json.loads(phone.recv(timeout=2.0))
                self.assertEqual(reply["message"], "200")
                deadline = time.monotonic() + 2.0
                while not bridge.connected and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(bridge.connected)

                frame = "1818181830303030"
                bridge.update_auto_outputs(
                    7, (frame,), wave_key_a="integration-test",
                    strength_b=0, frames_b=(), wave_key_b="idle", hard_cap=10,
                )
                bridge.set_auto_enabled(True)
                received: list[str] = []
                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline:
                    packet = json.loads(phone.recv(timeout=1.0))
                    received.append(str(packet.get("message", "")))
                    if any(item.startswith("pulse-A:") for item in received):
                        break
                pause_requested = time.monotonic()
                bridge.set_paused(True)
                def receive_until(predicate, seconds=1.5):
                    messages = []
                    expires = time.monotonic() + seconds
                    while time.monotonic() < expires:
                        message = str(json.loads(phone.recv(timeout=seconds)).get("message", ""))
                        messages.append(message)
                        if predicate(message):
                            return messages
                    self.fail(f"Expected Socket message not received: {messages}")

                receive_until(lambda message: message == "clear-2")
                self.assertLess(time.monotonic() - pause_requested, .4)
                self.assertEqual(bridge._desired_strength, {"A": 0, "B": 0})
                bridge.set_auto_enabled(True)
                time.sleep(.04)
                self.assertFalse(bridge._auto_enabled)  # Cannot bypass master pause.
                bridge.set_paused(False)
                release_deadline = time.monotonic() + .5
                while bridge._paused and time.monotonic() < release_deadline:
                    time.sleep(.005)
                self.assertFalse(bridge._paused)
                self.assertFalse(bridge._auto_enabled)  # Needs a fresh update below.
                # A 100 ms pulse must reach the phone without being swallowed
                # by the old 150 ms clear/sleep, and must queue only one frame.
                started = time.monotonic()
                bridge.update_auto_outputs(
                    0, (), wave_key_a="idle", strength_b=9,
                    frames_b=(frame, frame, frame), wave_key_b="short-b", hard_cap=10,
                )
                bridge.set_auto_enabled(True)
                short = receive_until(lambda message: message.startswith("pulse-B:"))
                self.assertLess(time.monotonic() - started, 0.15)
                sent_frame = next(message for message in short if message.startswith("pulse-B:"))
                self.assertEqual(len(json.loads(sent_frame.split(":", 1)[1])), 1)
                time.sleep(max(0, 0.1 - (time.monotonic() - started)))
                bridge.update_auto_outputs(
                    0, (), wave_key_a="idle", strength_b=0,
                    frames_b=(), wave_key_b="idle", hard_cap=10,
                )
                receive_until(lambda message: message == "strength-2+2+0")
                self.assertLess(time.monotonic() - started, 0.3)

                # Stop refreshing desired output to emulate a frozen Qt loop.
                bridge.update_auto_outputs(
                    8, (frame,), wave_key_a="watchdog", strength_b=0,
                    frames_b=(), wave_key_b="idle", hard_cap=10,
                )
                receive_until(lambda message: message.startswith("pulse-A:"))
                receive_until(lambda message: message == "clear-2")
                self.assertFalse(bridge._auto_enabled)
                self.assertTrue(any(payload.get("event") == "output_timeout" for _, payload in list(events.queue)))
            self.assertIn("strength-1+2+7", received)
            self.assertIn("strength-1+2+0", received)
            self.assertIn("strength-2+2+0", received)
            self.assertTrue(any(item.startswith("pulse-A:") for item in received))
            deadline = time.monotonic() + 1.0
            while bridge.connected and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertFalse(bridge.connected)
        finally:
            bridge.stop()


if __name__ == "__main__":
    unittest.main()
