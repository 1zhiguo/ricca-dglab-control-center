"""Separate vibration settings editing without a game, Socket or user files."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, Property, Signal, Slot, QCoreApplication

from ricca_dglab.localization import translate
from ricca_dglab.ovc_controller import OvcController
from ricca_dglab.product_config import ProductConfig


class FakeBackend(QObject):
    languageChanged = Signal()
    toastRequested = Signal(str, str)

    def __init__(self, config):
        super().__init__()
        self._config = config
        self.hooks = 0
        self.audioEmpathyEnabled = False

    @Property(str, notify=languageChanged)
    def language(self):
        return self._config.values["language"]

    @Slot(str, str, result=str)
    def localize(self, source, language):
        return translate(source, language)

    def onOvcSettingsChanged(self):
        self.hooks += 1


class OvcControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.config = ProductConfig(Path(self.temp.name) / "settings.json")
        self.backend = FakeBackend(self.config)
        self.controller = OvcController(self.backend)
        self.original = deepcopy(self.config.values)
        self.toasts = []
        self.backend.toastRequested.connect(lambda title, detail: self.toasts.append((title, detail)))

    def tearDown(self):
        self.temp.cleanup()

    def assert_electrical_unchanged(self):
        self.assertEqual({k: v for k, v in self.config.values.items() if k != "ovc_profile"},
                         {k: v for k, v in self.original.items() if k != "ovc_profile"})

    def test_independent_intensity_persisted_without_touching_coyote(self):
        self.assertTrue(self.controller.saveIntensitySettings(20, 40, 60, 80, 200))
        self.assertEqual((self.controller.lowStrength, self.controller.hardCap), (20, 200))
        self.assertEqual(ProductConfig(self.config.path).values, self.config.values)
        self.assertEqual(self.backend.hooks, 1)
        self.assertEqual(self.toasts[-1][0], "保存成功")
        self.assert_electrical_unchanged()

    def test_invalid_order_or_electrical_wave_never_saved(self):
        self.assertFalse(self.controller.saveIntensitySettings(10, 5, 20, 30, 40))
        policy = deepcopy(self.controller.channelPolicies["A"])
        policy["rules"]["damage_light"]["wave"] = "impact"
        self.assertFalse(self.controller.saveChannelPolicy("A", policy))
        self.assertFalse(self.controller.saveStoryQueue("A", [{"wave": "impact", "duration": 1}], True))
        self.assertEqual(self.config.values, self.original)
        self.assertEqual(self.backend.hooks, 0)

    def test_invalid_channel_mode_or_threshold_does_not_enable_a_default_policy(self):
        policy = deepcopy(self.controller.channelPolicies["A"])
        policy["mode"] = "unknown"
        self.assertFalse(self.controller.saveChannelPolicy("A", policy))
        policy["mode"] = "off"
        policy["damage_light_max"] = float("nan")
        self.assertFalse(self.controller.saveChannelPolicy("A", policy))
        policy["damage_light_max"] = 8
        self.assertFalse(self.controller.saveChannelPolicy("A", policy))
        self.assertEqual(self.config.values, self.original)

    def test_channel_rules_and_queue_are_separate_from_electrical_and_other_channel(self):
        original_b = deepcopy(self.controller.channelPolicies["B"])
        policy = deepcopy(self.controller.channelPolicies["A"])
        policy.update(mode="both", story_mode="queue_audio")
        policy["rules"]["damage_light"].update(wave="ovc_beat", custom_strength=190, duration=.3)
        self.assertTrue(self.controller.saveChannelPolicy("A", policy))
        self.assertEqual(self.controller.channelPolicies["B"], original_b)
        self.assertTrue(self.controller.saveStoryQueue("A", [
            {"wave": "ovc_trapezoid", "duration": 3, "tier": "medium"},
            {"wave": "idle", "duration": .5, "custom_strength": 0}], True))
        self.assertEqual(self.controller.channelPolicies["A"]["story_mode"], "queue_audio")
        self.assertEqual(self.controller.storyQueues["A"][1]["wave"], "idle")
        self.assert_electrical_unchanged()

    def test_audio_mapping_is_independent_but_capture_enable_is_shared(self):
        self.assertTrue(self.controller.saveAudioGain(2.4))
        self.assertTrue(self.controller.saveAudioQueueMinimum(10))
        self.assertEqual(self.controller.audioGain, 2.4)
        self.assertEqual(self.controller.audioQueueMinimum, 10)
        self.assertFalse(self.controller.audioEmpathyEnabled)
        self.backend.audioEmpathyEnabled = True
        self.assertTrue(self.controller.audioEmpathyEnabled)
        self.assertFalse(self.controller.saveAudioGain(float("nan")))
        self.assertFalse(self.controller.saveAudioQueueMinimum(21))
        self.assert_electrical_unchanged()

    def test_queue_status_isolated_and_copied(self):
        status = {"A": {"playing": True, "count": 5, "index": 2}}
        self.controller.updateStatus(status)
        status["A"]["index"] = 4
        self.assertEqual(self.controller.storyQueueStatus["A"]["index"], 2)
        self.assertEqual(self.config.values, self.original)

    def test_save_failure_does_not_call_runtime_hook_or_modify_settings(self):
        with patch.object(self.config, "save", side_effect=OSError("test read-only file")):
            self.assertFalse(self.controller.saveIntensitySettings(10, 20, 30, 40, 50))
        self.assertEqual(self.config.values, self.original)
        self.assertEqual(self.backend.hooks, 0)
        self.assertEqual(self.toasts[-1][0], "保存失败")

    def test_reset_only_vibration_rules_and_not_levels_or_queues(self):
        self.controller.saveIntensitySettings(20, 40, 60, 80, 200)
        queues = deepcopy(self.controller.storyQueues)
        self.assertTrue(self.controller.resetEventMappings())
        self.assertEqual((self.controller.lowStrength, self.controller.hardCap), (20, 200))
        self.assertEqual(self.controller.storyQueues, queues)
        self.assert_electrical_unchanged()

    def test_rejects_non_ten_steps_and_above_200(self):
        for levels in ((11, 20, 30, 40, 200), (10, 20, 30, 40, 201), (10, 20, 30, 40, 199)):
            self.assertFalse(self.controller.saveIntensitySettings(*levels))
        self.assertFalse(self.controller.saveAudioQueueMinimum(11))
        self.assertEqual(self.config.values, self.original)

    def test_queue_200_roundtrip(self):
        self.assertTrue(self.controller.saveIntensitySettings(20, 40, 60, 80, 200))
        self.assertTrue(self.controller.saveStoryQueue("A", [
            {"wave": "ovc_beat", "duration": 5, "custom_strength": 200}], True))
        self.assertEqual(self.controller.storyQueues["A"][0]["custom_strength"], 200)
        self.assertEqual(ProductConfig(self.config.path).values, self.config.values)
        self.assert_electrical_unchanged()


if __name__ == "__main__":
    unittest.main()
