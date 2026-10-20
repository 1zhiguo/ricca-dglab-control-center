from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import MagicMock

from ricca_dglab.localization import CATALOG, translate
from ricca_dglab.product_config import ProductConfig
import test_channel_backend as fixture


class LocalizationTests(unittest.TestCase):
    def test_every_shipped_chinese_message_has_english_and_japanese(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("inventory",root/"tools/extract_localization.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        missing = set(module.sources(root)) - set(CATALOG)
        self.assertFalse(missing, repr(sorted(missing)))
        for source, values in CATALOG.items():
            self.assertEqual(len(values),2,source)
            self.assertTrue(all(isinstance(text,str) and text for text in values),source)
            if source not in {"中文","日本語"}:
                self.assertIsNone(re.search(r"[\u3400-\u9fff]",values[0]),source)

    def test_dynamic_messages_identifiers_and_cache_are_bounded(self):
        self.assertEqual(translate("HP 归零 · 等待场景确认","en"),"HP zero · Confirming scene")
        self.assertEqual(translate("安全上限 60","en"),"Safety cap 60")
        self.assertEqual(translate("A 通道策略已保存","en"),"A channel strategy saved")
        for locale in ("zh","en","ja"):
            self.assertEqual(translate("Scene3D_RiccaFortMobGoblin -1027517838",locale),
                             "Scene3D_RiccaFortMobGoblin -1027517838")
        for index in range(5000): translate("安全上限 " + str(index),"en")
        self.assertLessEqual(translate.cache_info().currsize,4096)

    def test_old_invalid_and_saved_locale(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"settings.json"
            for raw in ({},{"language":"other"},{"language":[]}):
                path.write_text(json.dumps(raw),encoding="utf-8")
                self.assertEqual(ProductConfig(path).values["language"],"zh")
            config = ProductConfig(path)
            config.update({"language":"ja"})
            self.assertEqual(ProductConfig(path).values["language"],"ja")


class LanguageSafetyTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    setUp = fixture.ChannelBackendTests.setUp
    tearDown = fixture.ChannelBackendTests.tearDown
    def test_story_placeholders_are_distinct_from_real_game_text(self):
        backend = self.backend
        backend._state["story"] = {}
        self.assertFalse(backend.hasStorySpeaker)
        self.assertFalse(backend.hasStoryMessage)
        self.assertEqual(translate(backend.storySpeaker,"en"),CATALOG["旁白"][0])
        self.assertEqual(translate(backend.storyText,"ja"),CATALOG["当前不在剧情对话中"][1])
        # Real game text must remain raw even when identical to a UI placeholder.
        backend._state["story"] = {"speaker":"旁白", "message":"当前不在剧情对话中"}
        self.assertTrue(backend.hasStorySpeaker)
        self.assertTrue(backend.hasStoryMessage)
        self.assertEqual(backend.storySpeaker,"旁白")
        self.assertEqual(backend.storyText,"当前不在剧情对话中")

    def test_language_changes_do_not_touch_output_mapping_or_saved_rules(self):
        backend = self.backend
        backend._bridge = MagicMock()
        backend._user_output_paused = True
        backend._stop_latched = True
        original = deepcopy(backend._config.values)
        mapping = backend._mapping
        backend._story_queue_player.elapsed["A"] = 2.5
        for locale in ("en","ja","zh"):
            self.assertTrue(backend.setLanguage(locale))
            self.assertEqual(backend.language,locale)
            self.assertTrue(backend.userOutputPaused)
            self.assertTrue(backend._stop_latched)
            self.assertIs(backend._mapping,mapping)
            self.assertEqual(backend._story_queue_player.elapsed["A"],2.5)
            self.assertEqual({k:v for k,v in backend._config.values.items() if k!="language"},
                             {k:v for k,v in original.items() if k!="language"})
        self.assertEqual(backend._bridge.mock_calls,[])
        self.assertEqual(backend.priorityOutputStatus,"")
        self.assertFalse(backend.setLanguage("invalid"))
