import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ricca_dglab.scene_library import SceneLibrary
from ricca_dglab.defeat_scene import scene_root, DefeatSceneSession
from ricca_dglab.product_config import ProductConfig, default_channel_policies
from ricca_dglab.safety import is_story_scene
from ricca_dglab.waveforms import PRESETS


def anv():
    return {"status": "ok", "connected": True, "build_supported": True, "process_id": 42,
            "scene": "anv", "stage": {"all_resource_loaded": True},
            "story": {"asset_name": "ADV/SceneANV_RiccaClaretMp/SceneANV_RiccaClaretMp.csv",
                      "text": "PRIVATE DIALOGUE NOT TO BE RECORDED"}}


class SceneLibraryTests(unittest.TestCase):
    def test_explicitly_disabled_recorded_scene_cannot_restart_via_legacy_defeat_path(self):
        from test_defeat_scene import cg, death
        session = DefeatSceneSession()
        session.observe(death(), now=1, allow_story=False, paused=False)
        session.record_death(death(), 1)
        for now in (2, 2.1, 2.2):
            session.observe(cg(0), now=now, allow_story=True, paused=False,
                            blocked_scenes=["Scene3D_RiccaGhoul"])
        self.assertFalse(session.root)
        self.assertFalse(hasattr(session, "penalty_started"))

    def test_record_anv_deduplicates_preserves_note_and_never_stores_dialogue(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scenes.json"
            library = SceneLibrary(path)
            root = library.record(anv())
            library.save_note(root, "Claret 剧情")
            library.record(anv())
            loaded = SceneLibrary(path)
            self.assertEqual(len(loaded.entries), 1)
            self.assertEqual(loaded.entries[root]["note"], "Claret 剧情")
            self.assertEqual(len(loaded.entries[root]["assets"]), 1)
            self.assertNotIn("PRIVATE DIALOGUE", path.read_text(encoding="utf-8"))
            self.assertFalse(loaded.rows([])[0]["enabled"])
            self.assertTrue(loaded.rows([root])[0]["enabled"])

    def test_menu_candidate_invalid_and_unsupported_build_are_not_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            library = SceneLibrary(Path(folder) / "scenes.json")
            for changes in ({"scene": "other"}, {"build_supported": False},
                            {"status": "error"}, {"story": {}, "defeat_scene_hint": "Scene3D_Test"}):
                with self.assertRaises(ValueError):
                    library.record(dict(anv(), **changes))
            self.assertFalse(library.path.exists())

    def test_corrupt_library_not_overwritten_and_io_failure_retains_memory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "scenes.json"
            path.write_text("CORRUPT ORIGINAL", encoding="utf-8")
            library = SceneLibrary(path)
            with self.assertRaises(OSError):
                library.record(anv())
            self.assertEqual(path.read_text(encoding="utf-8"), "CORRUPT ORIGINAL")
            other = SceneLibrary(Path(folder) / "other.json")
            with patch("ricca_dglab.scene_library.Path.replace", side_effect=OSError("disk failure")):
                with self.assertRaises(OSError):
                    other.record(anv())
            self.assertEqual(other.entries, {})

    def test_anv_scene_requires_actual_asset_and_exact_allowlist(self):
        state = anv()
        root = "SceneANV_RiccaClaretMp"
        self.assertEqual(scene_root(state["story"]["asset_name"]), root)
        self.assertTrue(is_story_scene(state))
        self.assertFalse(is_story_scene(dict(state, story={})))
        session = DefeatSceneSession()
        policies = default_channel_policies()
        policies["B"]["mode"] = "action"
        policies["B"]["rules"]["defeat_interaction"]["playback"] = "wave"
        strengths = {"low": 5, "medium": 15, "high": 25, "death": 25}
        for now in (1, 1.1, 1.2):
            session.observe(state, now=now, allow_story=True, paused=False, registered_scenes=[])
        self.assertFalse(session.root)
        for now in (2, 2.1, 2.2):
            session.observe(state, now=now, allow_story=True, paused=False, registered_scenes=[root])
        preview = session.preview(policies, strengths, 30, now=2.2, allow=True)
        self.assertEqual((preview.strength_a, preview.strength_b), (5, 15))
        self.assertFalse(hasattr(session, "penalty_started"))
        session.observe(dict(state, scene="other"), now=2.3, allow_story=False, paused=False, registered_scenes=[root])
        self.assertFalse(session.root)

    def test_new_presets_round_half_seconds_and_existing_values_remain_exact(self):
        policies = default_channel_policies()
        self.assertEqual(policies["A"]["mode"], "both")
        self.assertEqual(policies["B"]["mode"], "action_audio")
        self.assertEqual(policies["B"]["rules"]["defeat_interaction"]["playback"], "queue")
        self.assertEqual(policies["A"]["rules"]["struggle"]["wave"], "official_bouncy")
        self.assertEqual(policies["A"]["rules"]["player_down"]["wave"], "death_ramp")
        for policy in policies.values():
            for rule in policy["rules"].values():
                if rule["duration"] is not None:
                    self.assertEqual(rule["duration"] * 2, round(rule["duration"] * 2))
        self.assertEqual(PRESETS["death_ramp"].points, (26,60,81,92,94,93,93,89,83,76,67,58,44,29,11,0))
        with tempfile.TemporaryDirectory() as folder:
            config = ProductConfig(Path(folder) / "settings.json")
            policies["A"]["rules"]["damage_medium"]["duration"] = 2.1
            policies["B"]["rules"]["damage_heavy"]["duration"] = 2.4
            config.update({"channel_policies": policies, "scene_catalog": ["SceneANV_RiccaClaretMp"]})
            loaded = ProductConfig(config.path)
            self.assertEqual(loaded.values["channel_policies"]["A"]["rules"]["damage_medium"]["duration"], 2.1)
            self.assertEqual(loaded.values["channel_policies"]["B"]["rules"]["damage_heavy"]["duration"], 2.4)
            self.assertEqual(loaded.values["scene_catalog"], ["SceneANV_RiccaClaretMp"])
            self.assertEqual(loaded.values["hard_cap"], 30)

