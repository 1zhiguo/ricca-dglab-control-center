import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ricca_dglab.product_config import ProductConfig


class SettingsPersistenceTests(unittest.TestCase):
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
