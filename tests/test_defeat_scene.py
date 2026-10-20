from copy import deepcopy
import json
from pathlib import Path
import unittest

from ricca_dglab.defeat_scene import DefeatSceneSession
from ricca_dglab.product_config import ProductConfig, default_channel_policies, sanitize_channel_policies


def death():
    return {"status": "ok", "connected": True, "build_supported": True, "process_id": 42,
            "scene": "gameplay", "player_address": "0x123", "current_hp": 0,
            "defeat_scene_hint": "Scene3D_RiccaGhoul", "stage": {}}


def cg(playing=1, *, cut=0):
    return {"status": "ok", "connected": True, "build_supported": True, "process_id": 42,
            "scene": "atd", "stage": {"all_resource_loaded": True},
            "story": {"asset_name": "ADV/Scene3D_RiccaGhoul/Scene3D_RiccaGhoul.csv"},
            "atd": {"playing_adv_state": playing, "animation_speed": 1.3188,
                    "cut_index": cut, "cut_name": "cut_test", "ui_start_atd": True}}


class DefeatSceneTests(unittest.TestCase):
    def setUp(self):
        self.session = DefeatSceneSession()
        self.policies = default_channel_policies()
        self.strengths = {"low": 5, "medium": 15, "high": 25, "death": 55}

    def observe(self, state, t, allow=True, paused=False):
        return self.session.observe(state, now=t, allow_story=allow, paused=paused)

    def stable(self, state, t=1):
        for offset in (0, .08, .16):
            self.observe(state, t + offset)

    def preview(self, t, allow=True):
        return self.session.preview(self.policies, self.strengths, 30, now=t, allow=allow)

    def begin(self, playing=1):
        self.observe(death(), 0, allow=False)
        self.stable(cg(playing))

    def test_requires_witnessed_death_and_matching_asset_not_gallery_or_stale_hint(self):
        self.stable(cg(0))
        self.assertEqual(self.preview(1.2).strength_a, 0)
        self.observe(death(), 2, allow=False)
        other = cg(0)
        other["story"]["asset_name"] = "ADV/Scene3D_Other/test.csv"
        self.stable(other, 3)
        self.assertEqual(self.preview(3.2).strength_a, 0)
        self.assertFalse(self.session.root)

    def test_three_samples_one_capped_penalty_then_constant_interaction_until_dialogue(self):
        self.observe(death(), 0, allow=False)
        self.observe(cg(), 1)
        self.assertEqual(self.preview(1).strength_a, 0)
        self.observe(cg(), 1.08)
        self.observe(cg(), 1.16)
        started = self.session.penalty_started
        self.assertEqual(self.preview(1.2).strength_a, 30)
        self.observe(cg(0), 1.3)
        self.assertEqual(self.preview(1.3).strength_a, 30)  # stronger wins, never add
        self.observe(cg(0, cut=3), 5)
        self.assertEqual(self.preview(5).strength_a, 15)
        self.observe(cg(0, cut=4), 100)
        self.assertEqual(self.preview(100).strength_b, 15)
        self.assertEqual(self.session.penalty_started, started)
        self.observe(cg(1), 100.1)
        self.assertEqual(self.preview(100.1).strength_a, 0)
        self.observe(cg(0), 100.2)
        self.assertEqual(self.preview(100.2).strength_a, 15)

    def test_pause_cancels_penalty_resume_only_current_loop_and_freshness(self):
        self.begin(0)
        self.observe(cg(0), 1.2, allow=False, paused=True)
        self.assertEqual(self.preview(1.2, allow=False).strength_a, 0)
        self.stable(cg(0), 2)
        self.assertEqual(self.preview(2.2).strength_a, 15)
        self.assertIsNone(self.session.penalty_started)
        self.assertEqual(self.preview(2.7).strength_a, 0)

    def test_automatic_story_pause_retains_pending_entry_until_three_resumed_samples(self):
        self.observe(death(), 0, allow=False)
        for now in (1, 2, 20):
            self.observe(cg(1), now, allow=False)
            self.assertTrue(self.session.entry_pending)
            self.assertEqual(self.preview(now, allow=False).strength_a, 0)
        self.stable(cg(1), 30)
        self.assertEqual(self.preview(30.16).strength_a, 30)
        self.assertAlmostEqual(self.session.penalty_started, 30.16)
        self.observe(cg(1), 32.95)
        self.assertEqual(self.preview(32.95).strength_a, 30)
        self.observe(cg(1), 33)
        self.assertEqual(self.preview(33).strength_a, 0)
        self.stable(cg(1), 40)
        self.assertEqual(self.preview(40.16).strength_a, 0)  # Never restart.

    def test_automatic_pause_freezes_remaining_duration_instead_of_replaying_full_penalty(self):
        self.begin(1)  # Starts at 1.16, duration 2.8 seconds.
        self.observe(cg(1), 2.16, allow=False)
        self.assertEqual(self.preview(2.16, allow=False).strength_a, 0)
        self.stable(cg(1), 50)
        self.assertEqual(self.preview(50.16).strength_a, 30)
        self.observe(cg(1), 51.9)
        self.assertEqual(self.preview(51.9).strength_a, 30)
        self.observe(cg(1), 52)
        self.assertEqual(self.preview(52).strength_a, 0)

    def test_loading_gap_preserves_remaining_penalty_but_manual_pause_cancels_it(self):
        self.begin(1)
        loading = {**cg(), "scene": "other", "stage": {"scene_change_playing": True}}
        self.observe(loading, 2, allow=False)
        self.assertEqual(self.preview(2, allow=False).strength_a, 0)
        self.stable(cg(1), 20)
        self.assertEqual(self.preview(20.16).strength_a, 30)
        self.observe(cg(1), 20.2, allow=False, paused=True)
        self.stable(cg(1), 30)
        self.assertEqual(self.preview(30.16).strength_a, 0)

    def test_manual_stop_before_cg_entry_cancels_the_same_defeat_penalty(self):
        self.observe(death(), 0, allow=False)
        self.session.cancel_pulses()
        self.stable(cg(1), 10)
        self.assertEqual(self.preview(10.16).strength_a, 0)
        self.observe(cg(0), 11)
        self.assertEqual(self.preview(11).strength_a, 15)  # Current loop may resume.


    def test_custom_strength_wave_disabled_channels_audio_competition_source(self):
        self.begin(0)
        self.policies["A"]["mode"] = "off"
        self.policies["B"]["mode"] = "audio"
        rule = self.policies["B"]["rules"]["defeat_interaction"]
        rule.update(custom_strength=95, wave="tap", duration=0.1)
        self.policies = sanitize_channel_policies(self.policies)
        self.assertIsNone(self.policies["B"]["rules"]["defeat_interaction"]["duration"])
        self.observe(cg(0), 5)
        preview = self.preview(5)
        self.assertEqual((preview.strength_a, preview.strength_b, preview.wave_b), (0, 30, "tap"))
        self.policies["B"]["rules"]["defeat_interaction"]["enabled"] = False
        self.assertEqual(self.preview(5).strength_b, 0)

    def test_missing_invalid_atd_speed_zero_respawn_wrong_build_and_pid_stop(self):
        for mutation in ({"atd": {}}, {"build_supported": False}, {"process_id": 99},
                         {"scene": "other"}, {"atd": {**cg(0)["atd"], "animation_speed": 0}},
                         {"atd": {**cg(0)["atd"], "animation_speed": float("nan")}}):
            self.session.reset()
            self.begin(0)
            state = cg(0); state.update(mutation)
            self.observe(state, 5)
            self.assertEqual(self.preview(5).strength_a, 0, mutation)
        self.begin(0)
        state = death(); state["current_hp"] = 31
        self.observe(state, 5, allow=False)
        self.assertFalse(self.session.root)

    def test_pending_expiry_loading_and_no_penalty_replay_on_new_subscript(self):
        self.observe(death(), 0, allow=False)
        loading = {**cg(), "scene": "other", "stage": {"scene_change_playing": True}}
        self.observe(loading, 1, allow=False)
        self.stable(cg(), 2)
        start = self.session.penalty_started
        subsequent = cg(1)
        subsequent["story"]["asset_name"] = "ADV/Scene3D_RiccaGhoul/Scene3D_RiccaGhoul02.csv"
        self.observe(subsequent, 10)
        self.assertEqual(self.preview(10).strength_a, 0)
        self.assertEqual(self.session.penalty_started, start)
        self.session.reset()
        self.observe(death(), 0, allow=False)
        self.stable(cg(0), 95)
        self.assertEqual(self.preview(95.2).strength_a, 0)

    def test_recorded_ghoul_segments_replay_with_scene_fields(self):
        folder = Path(__file__).resolve().parents[1] / "artifacts"
        self.observe(death(), 0, allow=False)
        cases = [("defeat-cg-20261019-205209.jsonl", "interaction"),
                 ("defeat-cg-20261019-205446.jsonl", "dialogue")]
        for i, (name, phase) in enumerate(cases):
            path = folder / name
            if not path.exists():
                self.skipTest("Local recording is not distributed")
            state = deepcopy(json.loads(path.read_text(encoding="utf-8").splitlines()[0])["state"])
            state["atd"] = state["defeat_diagnostics"]["atd"]
            state["process_id"] = 42
            self.stable(state, 5 + i)
            self.assertEqual(self.session.phase, phase)

    def test_migration_preserves_old_death_customization_and_never_overwrites_new_rule(self):
        old = default_channel_policies()
        old["A"]["rules"].pop("defeat_scene_enter")
        old["A"]["rules"].pop("defeat_interaction")
        old["A"]["rules"]["player_down"].update(custom_strength=22, wave="tap", duration=1.4)
        migrated = sanitize_channel_policies(old)
        self.assertEqual(migrated["A"]["rules"]["defeat_scene_enter"]["custom_strength"], 22)
        self.assertEqual(migrated["A"]["rules"]["defeat_scene_enter"]["wave"], "tap")
        self.assertEqual(migrated["A"]["rules"]["defeat_scene_enter"]["duration"], 1.4)
        self.assertIsNone(migrated["A"]["rules"]["defeat_interaction"]["duration"])
        migrated["A"]["rules"]["defeat_scene_enter"]["custom_strength"] = 19
        self.assertEqual(sanitize_channel_policies(migrated)["A"]["rules"]["defeat_scene_enter"]["custom_strength"], 19)
