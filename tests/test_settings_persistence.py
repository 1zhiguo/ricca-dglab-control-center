import tempfile
import json
from copy import deepcopy
import unittest
from pathlib import Path
from unittest.mock import patch

from ricca_dglab.product_config import ProductConfig, DEFAULT_SETTINGS


class SettingsPersistenceTests(unittest.TestCase):
    def test_scene_loop_user_tier_wave_and_custom_strength_survive_save(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config = ProductConfig(path)
            policies = deepcopy(config.values["channel_policies"])
            policies["A"]["rules"]["defeat_interaction"].update(tier="low", wave="custom:mine")
            policies["B"]["rules"]["defeat_interaction"].update(tier="high", custom_strength=23)
            config.update({"channel_policies": policies})
            saved = ProductConfig(path).values["channel_policies"]
            self.assertEqual(saved["A"]["rules"]["defeat_interaction"]["tier"], "low")
            self.assertEqual(saved["A"]["rules"]["defeat_interaction"]["wave"], "custom:mine")
            self.assertEqual(saved["B"]["rules"]["defeat_interaction"]["custom_strength"], 23)
            self.assertIsNone(saved["B"]["rules"]["defeat_interaction"]["duration"])

    def test_scene_catalogue_roundtrip_preserves_empty_and_filters_invalid_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config = ProductConfig(path)
            config.update({"scene_catalog": ["Scene3D_Custom", "Scene3D_Custom", "ADV/test.csv", None]})
            self.assertEqual(ProductConfig(path).values["scene_catalog"], ["Scene3D_Custom"])
            config.update({"scene_catalog": []})
            self.assertEqual(ProductConfig(path).values["scene_catalog"], [])

    def test_legacy_merges_only_missing_backup_fields_and_preserves_primary_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            legacy = {"format":"RiccaDGLabSettings/1", "hard_cap":30,
                      "strength_low":5,"strength_medium":15,"strength_high":25,"strength_death":25,
                      "event_rules":{"player_down":{"enabled":True,"wave":"custom:old-death","tier":"death"}}}
            prior = deepcopy(DEFAULT_SETTINGS)
            prior.update({"hard_cap":60,"onboarding_completed":True})
            prior["channel_policies"]["A"]["rules"]["player_down"]["duration"] = 2.3
            prior["channel_policies"]["B"]["mode"] = "off"
            primary_text, backup_text = json.dumps(legacy), json.dumps(prior)
            path.write_text(primary_text, encoding="utf-8")
            backup = path.with_suffix(".json.bak")
            backup.write_text(backup_text, encoding="utf-8")
            config = ProductConfig(path)
            self.assertTrue(config.values["onboarding_completed"])
            self.assertTrue(config.migration_info["onboarding_recovered"])
            for key in ("hard_cap","strength_low","strength_medium","strength_high","strength_death"):
                self.assertEqual(config.values[key], legacy[key])
            policies = config.values["channel_policies"]
            self.assertEqual(policies["B"]["mode"], "off")
            self.assertEqual(policies["A"]["rules"]["player_down"]["wave"], "custom:old-death")
            self.assertEqual(policies["A"]["rules"]["player_down"]["duration"], 2.3)
            self.assertEqual(path.read_text(encoding="utf-8"), primary_text)  # Read-only until Save.
            config.save()
            self.assertEqual(Path(str(path)+".pre-migration").read_text(encoding="utf-8"),primary_text)
            self.assertEqual(Path(str(backup)+".pre-migration").read_text(encoding="utf-8"),backup_text)
            self.assertTrue(ProductConfig(path).values["onboarding_completed"])

    def test_legacy_migration_does_not_invent_completion_or_raise_a_zero_limit(self):
        for completed, cap, expected in ((None,30,True),(False,30,False),(None,0,True),(None,None,False)):
            with self.subTest(completed=completed, cap=cap), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/"settings.json"
                primary = {"format":"RiccaDGLabSettings/1"}
                if cap is not None: primary["hard_cap"] = cap
                if completed is not None: primary["onboarding_completed"] = completed
                path.write_text(json.dumps(primary),encoding="utf-8")
                prior = {**deepcopy(DEFAULT_SETTINGS),"onboarding_completed":True,"hard_cap":60}
                path.with_suffix(".json.bak").write_text(json.dumps(prior),encoding="utf-8")
                config = ProductConfig(path)
                self.assertEqual(config.values["onboarding_completed"],expected)
                self.assertEqual(config.values["hard_cap"],cap if cap is not None else 0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"settings.json"
            path.write_text(json.dumps({"format":"RiccaDGLabSettings/1","hard_cap":30}),encoding="utf-8")
            self.assertFalse(ProductConfig(path).values["onboarding_completed"])

    def test_current_format_never_recovers_an_explicit_incomplete_state(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"settings.json"
            path.write_text(json.dumps(DEFAULT_SETTINGS),encoding="utf-8")
            path.with_suffix(".json.bak").write_text(json.dumps({**DEFAULT_SETTINGS,"onboarding_completed":True}),encoding="utf-8")
            self.assertFalse(ProductConfig(path).values["onboarding_completed"])

    def test_migration_never_overwrites_a_concurrent_configuration_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"settings.json"
            path.write_text(json.dumps({"format":"RiccaDGLabSettings/1","hard_cap":30}),encoding="utf-8")
            config=ProductConfig(path)
            changed=json.dumps({"format":"RiccaDGLabSettings/1","hard_cap":10})
            path.write_text(changed,encoding="utf-8")
            with self.assertRaises(OSError): config.save()
            self.assertEqual(path.read_text(encoding="utf-8"),changed)

    def test_existing_archive_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"settings.json"
            original=json.dumps({"format":"RiccaDGLabSettings/1","hard_cap":30})
            path.write_text(original,encoding="utf-8")
            archive=Path(str(path)+".pre-migration")
            archive.write_text('older recovery copy',encoding="utf-8")
            ProductConfig(path).save()
            self.assertEqual(archive.read_text(encoding="utf-8"),'older recovery copy')
            copies=list(Path(directory).glob('settings.json.pre-migration-*'))
            self.assertEqual(len(copies),1)
            self.assertEqual(copies[0].read_text(encoding="utf-8"),original)

    def test_backup_and_corrupt_primary_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config = ProductConfig(path)
            config.update({"hard_cap": 60, "strength_high": 40})
            config.update({"hard_cap": 90})
            self.assertEqual(ProductConfig(path).values["hard_cap"], 90)
            path.write_text("{broken", encoding="utf-8")
            recovered = ProductConfig(path)
            self.assertEqual(recovered.values["hard_cap"], 60)
            recovered.update({"audio_gate": 20})
            self.assertEqual(ProductConfig(path).values["strength_high"], 40)
            self.assertEqual(ProductConfig(path.with_suffix(".json.bak")).values["hard_cap"], 60)

    def test_failed_save_rolls_back_memory_and_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config = ProductConfig(path)
            config.update({"hard_cap": 60})
            original = path.read_bytes()
            with patch.object(config, "save", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    config.update({"hard_cap": 90})
            self.assertEqual(config.values["hard_cap"], 60)
            self.assertEqual(path.read_bytes(), original)
