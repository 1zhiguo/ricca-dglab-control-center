import json
from pathlib import Path
import tempfile
import unittest

from ricca_dglab.capture import capture_state
from ricca_dglab.events import EventDetector
from ricca_dglab.mapping import RiccaMappingEngine
from ricca_dglab.models import GameEvent, RuntimeMode, SafetyDecision
from ricca_dglab.product_config import ProductConfig, default_channel_policies


READY = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")


def snapshot(address="0x1000", count=1.0, maximum=12.0, acceptance=True, **updates):
    state = dict(scene="gameplay", player_address="0x2000", is_paused=False,
                 current_hp=30.0, max_hp=31.0, action_trigger_hash=362220413,
                 capture=dict(info_address=address, current_break_off_count=count,
                              break_off_count_max=maximum, break_off_acceptance=acceptance))
    state.update(updates)
    return state


class CaptureTests(unittest.TestCase):
    def test_inactive_counter_is_not_a_capture(self):
        capture = capture_state(snapshot("0x0", count=12, acceptance=False))
        self.assertTrue(capture.known)
        self.assertFalse(capture.active)
        self.assertEqual(capture.progress, 0)

    def test_invalid_fields_are_unknown_not_inactive(self):
        for raw in ({}, {"info_address": "bad"},
                    snapshot(count=float("nan"))["capture"],
                    snapshot(count=-1)["capture"], snapshot(maximum=0)["capture"],
                    snapshot(count=50)["capture"]):
            self.assertFalse(capture_state(snapshot(capture=raw)).known)
        self.assertFalse(capture_state(snapshot(capture_read_error="read failed")).known)
        self.assertFalse(capture_state(snapshot(scene="other")).known)

    def test_start_progress_and_escape_without_hash_changes(self):
        detector = EventDetector()
        mapper = RiccaMappingEngine()
        detector.ingest(snapshot("0x0", acceptance=False), 1)
        events = detector.ingest(snapshot(), 1.1)
        self.assertEqual([e.kind for e in events], ["capture_start"])
        mapper.accept(events)
        mapper.reconcile_capture(snapshot(), now=1.1)
        self.assertEqual(mapper.preview(READY, 1.1).wave_b, "tap")
        self.assertEqual(mapper.preview(READY, 1.1).strength_b, 15)
        events = detector.ingest(snapshot(count=5), 1.2)
        self.assertEqual([e.kind for e in events], ["struggle"])
        mapper.accept(events)
        self.assertEqual(mapper.preview(READY, 1.2).wave_b, "tap")
        escaped = snapshot("0x0", count=12, acceptance=False)
        events = detector.ingest(escaped, 1.21)
        self.assertEqual([e.kind for e in events], ["capture_end"])
        mapper.accept(events, allow_output=False)
        mapper.reconcile_capture(escaped, now=1.21)
        self.assertEqual(mapper.preview(READY, 1.21).strength_b, 0)
        self.assertEqual(mapper.preview(READY, 1.3).strength_b, 0)

    def test_no_repeat_decrease_noise_or_exact_keypress_claim(self):
        detector = EventDetector()
        detector.ingest(snapshot(count=5), 1)
        for index, count in enumerate((5, 4, 4.01, 4.02)):
            self.assertFalse(detector.ingest(snapshot(count=count), 1.1 + index * .1))

    def test_pause_resume_and_read_recovery_do_not_replay(self):
        detector = EventDetector()
        detector.ingest(snapshot(), 1)
        events = detector.ingest(snapshot(count=5, is_paused=True), 1.1)
        self.assertFalse(any(e.kind == "struggle" for e in events))
        events = detector.ingest(snapshot(count=6), 1.2)
        self.assertFalse(any(e.kind in {"struggle", "capture_start"} for e in events))
        events = detector.ingest(snapshot(capture=None), 1.3)
        self.assertTrue(any(e.kind == "capture_end" for e in events))
        self.assertFalse(detector.ingest(snapshot(count=7), 1.4))
        events = detector.ingest(snapshot(count=8), 1.5)
        self.assertTrue(any(e.kind == "struggle" for e in events))

    def test_struggle_stops_on_missing_data_or_escape(self):
        for current in (snapshot(capture=None), snapshot("0x0", acceptance=False),
                        snapshot(capture_read_error="bad read")):
            mapper = RiccaMappingEngine()
            mapper.reconcile_capture(snapshot(), now=1)
            self.assertGreater(mapper.preview(READY, 1).strength_b, 0)
            mapper.reconcile_capture(current, now=1.01)
            self.assertEqual(mapper.preview(READY, 1.01).strength_b, 0)

    def test_capture_end_does_not_cancel_independent_hp_pulse(self):
        mapper = RiccaMappingEngine()
        mapper.accept([GameEvent(1, 1, "now", "damage", "hit", data={"amount": 2})])
        mapper.accept([GameEvent(2, 1.01, "now", "capture_end", "escaped")])
        self.assertGreater(mapper.preview(READY, 1.01).strength_a, 0)

    def test_custom_strength_wave_routing_disabled_and_legacy_duration_ignored(self):
        policies = default_channel_policies()
        policies["A"]["mode"] = "both"
        policies["A"]["rules"]["struggle"].update(custom_strength=17, wave="impact", duration=3)
        policies["B"]["rules"]["struggle"]["enabled"] = False
        mapper = RiccaMappingEngine(channel_policies=policies)
        self.assertIsNone(mapper.channel_policies["A"]["rules"]["struggle"]["duration"])
        mapper.reconcile_capture(snapshot(), now=1)
        result = mapper.preview(READY, 1)
        self.assertEqual((result.strength_a, result.wave_a, result.strength_b), (17, "impact", 0))
        mapper.reconcile_capture(snapshot(), now=4)
        self.assertEqual(mapper.preview(READY, 4).strength_a, 17)
        self.assertEqual(mapper.preview(READY, 4.6).strength_a, 0)  # Lost telemetry lease.
        mapper = RiccaMappingEngine(channel_policies=policies)
        mapper.accept([GameEvent(2, 5, "now", "struggle", "progress")], allow_output=False)
        self.assertEqual(mapper.preview(READY, 5).strength_a, 0)

    def test_hold_does_not_decay_or_require_input_and_pauses_safely(self):
        mapper = RiccaMappingEngine()
        mapper.rebase_sensitivity(2)  # Hold keeps configured strength, not armor multiplier.
        tokens = set()
        for index in range(100):
            now = 1 + index * .1
            mapper.reconcile_capture(snapshot(count=1, acceptance=index < 50), now=now)
            result = mapper.preview(READY, now)
            self.assertEqual((result.strength_b, result.wave_b), (15, "tap"))
            tokens.add(mapper.pulse_token("B"))
        self.assertEqual(len(tokens), 1)  # Wave loop does not restart on every poll.
        paused = SafetyDecision(RuntimeMode.PAUSED, False, False, "paused")
        self.assertEqual(mapper.preview(paused, now + .01).strength_b, 0)
        self.assertEqual(mapper.preview(READY, now + .02).strength_b, 0)
        mapper.reconcile_capture(snapshot(), allow_output=False, now=now + .03)
        self.assertEqual(mapper.preview(READY, now + .03).strength_b, 0)
        mapper.reconcile_capture(snapshot(), now=now + .04)
        self.assertEqual(mapper.preview(READY, now + .04).strength_b, 15)

    def test_stronger_hit_temporarily_takes_over_without_adding_to_hold(self):
        policies = default_channel_policies()
        policies["B"]["rules"]["hit_normal"].update(custom_strength=25, duration=1, wave="impact")
        mapper = RiccaMappingEngine(channel_policies=policies)
        mapper.reconcile_capture(snapshot(), now=1)
        mapper.accept([GameEvent(1, 1, "now", "action", "hit", data={"action": "stand_damage"})])
        result = mapper.preview(READY, 1)
        self.assertEqual((result.strength_b, result.wave_b), (25, "impact"))
        mapper.reconcile_capture(snapshot(), now=1.45)
        result = mapper.preview(READY, 1.45)
        self.assertEqual((result.strength_b, result.wave_b), (15, "tap"))

    def test_legacy_policies_add_new_rules_without_changing_existing_values(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            target = Path(directory) / "settings.json"
            policies = default_channel_policies()
            for policy in policies.values():
                policy["rules"].pop("capture_start", None)
                policy["rules"].pop("struggle")
            policies["B"]["rules"]["hit_small"]["custom_strength"] = 19
            target.write_text(json.dumps({"channel_policies": policies}), encoding="utf-8")
            config = ProductConfig(target)
            self.assertEqual(config.values["channel_policies"]["B"]["rules"]["hit_small"]["custom_strength"], 19)
            self.assertTrue(config.values["channel_policies"]["B"]["rules"]["struggle"]["enabled"])

    def test_old_short_struggle_becomes_medium_hold_preserving_custom_wave(self):
        from ricca_dglab.product_config import sanitize_channel_policies
        policies = default_channel_policies()
        legacy = policies["B"]["rules"]["struggle"]
        legacy.pop("behavior")
        legacy.update(tier="low", duration=.4, wave="impact")
        rule = sanitize_channel_policies(policies)["B"]["rules"]["struggle"]
        self.assertEqual((rule["tier"], rule["duration"], rule["wave"]), ("medium", None, "impact"))
        legacy["custom_strength"] = 12
        rule = sanitize_channel_policies(policies)["B"]["rules"]["struggle"]
        self.assertEqual(rule["custom_strength"], 12)

    def test_capture_start_is_diagnostic_only_and_old_alias_preserves_wave(self):
        from ricca_dglab.product_config import sanitize_channel_policies
        policies = default_channel_policies()
        policies["B"]["rules"].pop("struggle")
        policies["B"]["rules"]["capture_start"] = dict(enabled=True, tier="low", wave="impact",
                                                       custom_strength=18, duration=.5)
        migrated = sanitize_channel_policies(policies)
        rule = migrated["B"]["rules"]["struggle"]
        self.assertEqual((rule["wave"], rule["custom_strength"], rule["duration"]), ("impact", 18, None))
        self.assertNotIn("capture_start", migrated["B"]["rules"])
        mapper = RiccaMappingEngine(channel_policies=migrated)
        mapper.accept([GameEvent(1, 1, "now", "capture_start", "captured")])
        self.assertEqual(mapper.preview(READY, 1).strength_b, 0)
        for now in (1, 10, 60):
            mapper.reconcile_capture(snapshot(), now=now)
            self.assertEqual(mapper.preview(READY, now).strength_b, 18)
        mapper.reconcile_capture(snapshot("0x0", acceptance=False), now=60.1)
        self.assertEqual(mapper.preview(READY, 60.1).strength_b, 0)

    def test_recorded_vine_states_replay_as_progress_then_end(self):
        project = Path(__file__).resolve().parents[1]
        files = [project / "artifacts" / ("trap-probe-20261019-" + suffix + ".jsonl")
                 for suffix in ("174502", "174815", "175046")]
        if not all(path.exists() for path in files):
            self.skipTest("Local read-only capture fixtures are not available")
        states = [json.loads(path.read_text(encoding="utf-8").splitlines()[0]) for path in files]
        detector = EventDetector()
        for index, state in enumerate(states):
            state["is_paused"] = False  # Replay transitions, not the user's pause menu.
            events = detector.ingest(state, 1 + index * .1)
            if index == 1:
                self.assertTrue(any(e.kind == "struggle" for e in events))
            if index == 2:
                self.assertTrue(any(e.kind == "capture_end" for e in events))
