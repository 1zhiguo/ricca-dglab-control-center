from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from ricca_dglab.product_config import ProductConfig
import test_channel_backend as fixture
from test_scene_library import anv


class AudioGainConfigTests(unittest.TestCase):
    def test_minimum_defaults_to_zero_and_persists_with_finite_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ProductConfig(Path(directory)/"settings.json")
            self.assertEqual(config.values["audio_queue_minimum"],0)
            for value, expected in ((16,16),(-1,0),(200,100),(float("nan"),0),("bad",0)):
                config.update({"audio_queue_minimum":value})
                self.assertEqual(ProductConfig(config.path).values["audio_queue_minimum"],expected)

    def test_legacy_default_finite_bounds_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ProductConfig(Path(directory)/"settings.json")
            self.assertEqual(config.values["audio_gain"], 1.0)
            for value, expected in ((3.2,3.2), (-1,0), (100,10), (float("nan"),1), ("bad",1)):
                config.update({"audio_gain":value})
                self.assertEqual(ProductConfig(config.path).values["audio_gain"], expected)


class AudioGainBackendTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    setUp = fixture.ChannelBackendTests.setUp
    tearDown = fixture.ChannelBackendTests.tearDown
    enable_hybrid_audio_fixture = fixture.ChannelBackendTests.enable_hybrid_audio_fixture

    def test_minimum_save_keeps_authorization_queue_and_other_settings(self):
        backend = self.backend
        backend._bridge = MagicMock()
        backend._user_output_paused = backend._stop_latched = True
        backend._story_queue_player.elapsed["B"] = 2.5
        before = deepcopy(backend._config.values)
        self.assertTrue(backend.saveAudioQueueMinimum(16))
        self.assertEqual(backend._config.values,{**before,"audio_queue_minimum":16})
        self.assertTrue(backend._user_output_paused and backend._stop_latched)
        self.assertEqual(backend._story_queue_player.elapsed["B"],2.5)
        self.assertEqual(backend._bridge.mock_calls,[])
        self.assertFalse(backend.saveAudioQueueMinimum(-1))
        self.assertFalse(backend.saveAudioQueueMinimum(backend.hardCap+1))
        with patch.object(backend._config,"save",side_effect=OSError("blocked")):
            self.assertFalse(backend.saveAudioQueueMinimum(12))
        self.assertEqual(backend.audioQueueMinimum,16)
        backend._config.values["hard_cap"] = 10
        self.assertEqual(backend.audioQueueMinimum,10)

    def test_minimum_holds_voice_gaps_but_respects_all_stop_conditions(self):
        backend = self.enable_hybrid_audio_fixture()
        backend.saveAudioQueueMinimum(16)
        state = anv()
        state["story"]["asset_name"] = "ADV/SceneANV_UnlistedAudio/test.csv"
        def feed(now, level=70, factor=.5, fresh=True):
            with patch("ricca_dglab.backend.time.monotonic",return_value=now):
                backend._apply_state({"state":state,"received_at":now,"latency_ms":1})
                backend._audio_last_sample = now if fresh else now-1
                backend._audio_strength = backend.hardCap*factor
                backend._audio_level = level
                backend._drain()
        feed(10)
        self.assertEqual(backend.previewB,16)
        feed(10.05,factor=1)
        self.assertEqual(backend.previewB,20)
        feed(10.1,level=0,factor=0)
        self.assertEqual(backend.previewB,16)
        feed(10.15,fresh=False)
        self.assertEqual(backend.previewB,0)
        backend.saveAudioGain(0)
        feed(10.2)
        self.assertEqual(backend.previewB,0)
        backend.saveAudioGain(10)
        feed(10.25)
        self.assertEqual(backend.previewB,backend.hardCap)
        step = backend._config.values["story_queues"]["B"][0]
        for wave, strength in (("idle",20),("missing-wave",20),("tap",0)):
            step.update(wave=wave,custom_strength=strength)
            feed(10.3)
            self.assertEqual(backend.previewB,0)
        step.update(wave="tap",custom_strength=20)
        backend._config.values["channel_policies"]["B"]["story_mode"] = "fixed_audio"
        feed(10.35,level=0,factor=0)
        self.assertEqual(backend.previewB,0)
        backend._config.values["channel_policies"]["B"]["story_mode"] = "queue_audio"
        backend.toggleOutputPause()
        feed(10.4)
        self.assertEqual(backend.previewB,0)
        backend.toggleOutputPause()
        backend._config.values["audio_empathy_enabled"] = False
        feed(10.45)
        self.assertEqual(backend.previewB,0)
        backend._config.values["audio_empathy_enabled"] = True
        backend.emergencyStop()
        feed(10.5)
        self.assertEqual(backend.previewB,0)

    def test_high_gain_still_ignores_battle_audio_and_keeps_action_feedback(self):
        self.backend.saveAudioGain(10)
        fixture.ChannelBackendTests.test_hybrid_loud_battle_audio_is_ignored_but_actions_still_work(self)

    def test_save_changes_only_gain_without_resuming_or_restarting(self):
        backend = self.backend
        backend._bridge = MagicMock()
        backend._user_output_paused = backend._stop_latched = True
        before = deepcopy(backend._config.values)
        backend._story_queue_player.elapsed["B"] = 2.5
        mapper = backend._audio_mapper
        self.assertTrue(backend.saveAudioGain(4))
        self.assertEqual(backend.audioGain,4)
        self.assertEqual(backend._config.values,{**before,"audio_gain":4.0})
        self.assertTrue(backend.userOutputPaused and backend._stop_latched)
        self.assertEqual(backend._story_queue_player.elapsed["B"],2.5)
        self.assertIs(backend._audio_mapper,mapper)
        self.assertEqual(backend._bridge.mock_calls,[])
        for bad in (-1, 11, float("nan"), float("inf")):
            self.assertFalse(backend.saveAudioGain(bad))
        with patch.object(backend._config,"save",side_effect=OSError("blocked")):
            self.assertFalse(backend.saveAudioGain(2))
        self.assertEqual(backend.audioGain,4)

    def test_queue_gain_exceeds_base_but_not_cap_and_never_boosts_silence(self):
        backend = self.enable_hybrid_audio_fixture()
        state = anv()
        state["story"]["asset_name"] = "ADV/SceneANV_UnlistedAudio/test.csv"
        def feed(now, level=70, fresh=True):
            with patch("ricca_dglab.backend.time.monotonic",return_value=now):
                backend._apply_state({"state":state,"received_at":now,"latency_ms":1})
                backend._audio_last_sample = now if fresh else now-1
                backend._audio_strength = backend.hardCap/2
                backend._audio_level = level
                backend._drain()
        feed(10)
        self.assertEqual(backend.previewB,10)
        for offset, gain, expected in ((.1,2,20),(.2,4,30),(.3,10,30),(.4,0,0)):
            self.assertTrue(backend.saveAudioGain(gain))
            feed(10+offset)
            self.assertEqual(backend.previewB,expected)
        backend.saveAudioGain(10)
        feed(10.5,level=0)
        self.assertEqual(backend.previewB,0)
        feed(10.6,fresh=False)
        self.assertEqual(backend.previewB,0)
        backend._config.values["story_queues"]["B"][0]["wave"] = "idle"
        feed(10.7)
        self.assertEqual(backend.previewB,0)
        backend.toggleOutputPause()
        feed(10.8)
        self.assertEqual(backend.previewB,0)
