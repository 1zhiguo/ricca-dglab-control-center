import json
from pathlib import Path
import re
import tempfile
import unittest

from tools.register_collected_scenes import collected_ids, register_file
from ricca_dglab.scene_catalog import COLLECTED_SCENE_IDS


class SceneRegistrationTests(unittest.TestCase):
    def test_collected_catalogue_has_34_exact_unique_ids(self):
        self.assertEqual(len(COLLECTED_SCENE_IDS), 34)
        self.assertEqual(len(set(COLLECTED_SCENE_IDS)), 34)
        self.assertEqual(sum(key.startswith("Scene3D_") for key in COLLECTED_SCENE_IDS), 24)
        self.assertEqual(sum(key.startswith("SceneANV_") for key in COLLECTED_SCENE_IDS), 10)
        self.assertTrue(all(re.fullmatch(r"Scene(?:3D|ANV)_[A-Za-z0-9_-]+", key) for key in COLLECTED_SCENE_IDS))

    def test_registration_changes_only_allowlist_preserves_original_and_merges_existing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            original = {"format": "RiccaDGLabSettings/1", "hard_cap": 30, "strength_low": 5,
                        "unknown_future_setting": {"keep": True},
                        "channel_policies": {"A": {"wave": "custom:用户波形"}},
                        "scene_catalog": ["Scene3D_PreviouslyRegistered"]}
            source = json.dumps(original, ensure_ascii=False).encode("utf-8")
            path.write_bytes(source)
            result = register_file(path, COLLECTED_SCENE_IDS, "test")
            saved = json.loads(path.read_bytes())
            self.assertEqual(result["scene_count"], 35)
            self.assertEqual(Path(result["backup"]).read_bytes(), source)
            saved.pop("scene_catalog"); original.pop("scene_catalog")
            self.assertEqual(saved, original)
            with self.assertRaises(FileExistsError):
                register_file(path, COLLECTED_SCENE_IDS, "test")

    def test_log_recovery_requires_successful_record_and_matching_session(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "runtime.jsonl"
            entries = [
                {"event": "scene.recorded", "session": "active", "scene_root": "Scene3D_Test"},
                {"event": "scene.recorded", "session": "active", "scene_root": "Scene3D_Test"},
                {"event": "scene.observed", "session": "active", "scene_root": "Scene3D_Unknown"},
                {"event": "scene.recorded", "session": "old", "scene_root": "Scene3D_Old"},
                {"event": "scene.recorded", "session": "active", "scene_root": "../../bad"},
            ]
            path.write_text("\n".join(json.dumps(row) for row in entries) + "\nPARTIAL LINE", encoding="utf-8")
            self.assertEqual(collected_ids(path, "active"), ["Scene3D_Test"])

