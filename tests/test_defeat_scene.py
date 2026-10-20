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
    def test_duration_limits_roundtrip_do_not_change_existing_strength_or_wave(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            config = ProductConfig(Path(directory) / "settings.json")
            policies = default_channel_policies()
            for policy in policies.values():
                policy["rules"]["player_down"].update(duration=99, custom_strength=22, wave="tap")
                policy["rules"]["armor_break"].update(duration=99, custom_strength=13, wave="impact")
                policy["rules"]["hit_normal"]["duration"] = 99
            config.update({"channel_policies": policies})
            loaded = ProductConfig(config.path).values["channel_policies"]
            for policy in loaded.values():
                rules = policy["rules"]
                self.assertEqual(rules["player_down"]["duration"], 10)
                self.assertEqual(rules["armor_break"]["duration"], 5)
                self.assertEqual(rules["hit_normal"]["duration"], 3)
                self.assertEqual((rules["player_down"]["wave"], rules["player_down"]["custom_strength"]), ("tap", 22))
                self.assertEqual((rules["armor_break"]["wave"], rules["armor_break"]["custom_strength"]), ("impact", 13))

    def test_catalogued_gallery_loops_from_dialogue_without_requiring_death_or_atd_controls(self):
        state = cg(1)
        state["atd"] = {}
        for now in (1, 1.08):
            self.session.observe(state, now=now, allow_story=True, paused=False,
                                 registered_scenes=["Scene3D_RiccaGhoul"])
            self.assertEqual(self.preview(now).strength_a, 0)
        self.session.observe(state, now=1.16, allow_story=True, paused=False,
                             registered_scenes=["Scene3D_RiccaGhoul"])
        self.assertEqual(self.preview(1.16).strength_a, 15)
        self.assertFalse(hasattr(self.session, "penalty_started"))
        self.assertEqual(self.session.preview(self.policies, self.strengths, 30,
                         now=1.16, allow=True, allow_loop=False).strength_a, 0)
        self.assertEqual(self.preview(1.7).strength_a, 0)  # Stale read stops, no timer-only loop.

    def test_catalogue_root_switch_exit_loading_and_disabled_channel(self):
        catalog = ["Scene3D_RiccaGhoul", "Scene3D_RiccaFortMobGoblin"]
        def observe(state, now, allow=True):
            self.session.observe(state, now=now, allow_story=allow, paused=False,
                                 registered_scenes=catalog)
        for now in (1, 1.08, 1.16):
            observe(cg(), now)
        self.policies["A"]["mode"] = "off"
        self.assertEqual(self.preview(1.16).strength_a, 0)
        self.assertEqual(self.preview(1.16).strength_b, 15)
        other = cg()
        other["story"]["asset_name"] = "ADV/Scene3D_RiccaFortMobGoblin/intro.csv"
        observe(other, 2)
        self.assertEqual(self.preview(2).strength_b, 0)
        observe(other, 2.08); observe(other, 2.16)
        self.assertEqual(self.preview(2.16).strength_b, 15)
        observe(dict(other, scene="other"), 2.2)
        self.assertEqual(self.preview(2.2).strength_b, 0)
        self.assertFalse(self.session.root)
        for now in (3, 3.08, 3.16):
            observe(other, now)
        observe(dict(other, stage={"scene_change_playing": True}), 3.2, allow=False)
        self.assertEqual(self.preview(3.2).strength_b, 0)

    def setUp(self):
        self.session = DefeatSceneSession()
        self.policies = default_channel_policies()
        self.policies["B"]["mode"] = "action"
        self.policies["B"]["rules"]["defeat_interaction"]["playback"] = "wave"
        # Existing saved profile: keep medium loops independent of fresh defaults.
        self.policies["A"]["rules"]["defeat_interaction"]["tier"] = "medium"
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

    def test_three_samples_loop_only_never_schedule_second_death_penalty(self):
        self.observe(death(), 0, allow=False)
        self.observe(cg(), 1)
        self.assertEqual(self.preview(1).strength_a, 0)
        self.observe(cg(), 1.08)
        self.observe(cg(), 1.16)
        self.assertEqual(self.preview(1.2).strength_a, 0)
        self.observe(cg(0), 1.3)
        self.assertEqual(self.preview(1.3).strength_a, 15)
        self.observe(cg(0, cut=3), 5)
        self.assertEqual(self.preview(5).strength_a, 15)
        self.observe(cg(0, cut=4), 100)
        self.assertEqual(self.preview(100).strength_b, 15)
        self.assertFalse(hasattr(self.session, "penalty_started"))
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
        self.assertFalse(hasattr(self.session, "penalty_started"))
        self.assertEqual(self.preview(2.7).strength_a, 0)

    def test_automatic_story_pause_never_queues_a_deferred_entry_penalty(self):
        self.observe(death(), 0, allow=False)
        for now in (1, 2, 20):
            self.observe(cg(1), now, allow=False)
            self.assertFalse(hasattr(self.session, "entry_pending"))
            self.assertEqual(self.preview(now, allow=False).strength_a, 0)
        self.stable(cg(1), 30)
        self.assertEqual(self.preview(30.16).strength_a, 0)
        self.observe(cg(1), 32.95)
        self.assertEqual(self.preview(32.95).strength_a, 0)
        self.observe(cg(1), 33)
        self.assertEqual(self.preview(33).strength_a, 0)
        self.stable(cg(1), 40)
        self.assertEqual(self.preview(40.16).strength_a, 0)  # Never restart.

    def test_automatic_pause_does_not_manufacture_a_death_penalty(self):
        self.begin(1)
        self.observe(cg(1), 2.16, allow=False)
        self.assertEqual(self.preview(2.16, allow=False).strength_a, 0)
        self.stable(cg(1), 50)
        self.assertEqual(self.preview(50.16).strength_a, 0)
        self.observe(cg(1), 51.9)
        self.assertEqual(self.preview(51.9).strength_a, 0)
        self.observe(cg(1), 52)
        self.assertEqual(self.preview(52).strength_a, 0)

    def test_loading_and_manual_pause_never_create_a_scene_entry_penalty(self):
        self.begin(1)
        loading = {**cg(), "scene": "other", "stage": {"scene_change_playing": True}}
        self.observe(loading, 2, allow=False)
        self.assertEqual(self.preview(2, allow=False).strength_a, 0)
        self.stable(cg(1), 20)
        self.assertEqual(self.preview(20.16).strength_a, 0)
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
        sequence = self.session.sequence
        subsequent = cg(1)
        subsequent["story"]["asset_name"] = "ADV/Scene3D_RiccaGhoul/Scene3D_RiccaGhoul02.csv"
        self.observe(subsequent, 10)
        self.assertEqual(self.preview(10).strength_a, 0)
        self.assertEqual(self.session.sequence, sequence)
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
        old["A"]["rules"]["defeat_scene_enter"] = dict(custom_strength=90, wave="impact", duration=3)
        old["A"]["rules"].pop("defeat_interaction")
        old["A"]["rules"]["player_down"].update(custom_strength=22, wave="tap", duration=1.4)
        migrated = sanitize_channel_policies(old)
        self.assertNotIn("defeat_scene_enter", migrated["A"]["rules"])
        self.assertEqual(migrated["A"]["rules"]["player_down"]["custom_strength"], 22)
        self.assertEqual(migrated["A"]["rules"]["player_down"]["wave"], "tap")
        self.assertEqual(migrated["A"]["rules"]["player_down"]["duration"], 1.4)
        self.assertIsNone(migrated["A"]["rules"]["defeat_interaction"]["duration"])
        old["A"]["rules"].pop("player_down")
        migrated = sanitize_channel_policies(old)
        self.assertEqual(migrated["A"]["rules"]["player_down"]["custom_strength"], 90)
