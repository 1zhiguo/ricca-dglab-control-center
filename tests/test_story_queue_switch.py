"""Story switches stop output, not fall back to fixed waves; no real devices."""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock, patch
import test_channel_backend as fixture
from ricca_dglab.ovc import default_ovc_profile
from ricca_dglab.ovc_pipeline import OvcOutputPipeline
from ricca_dglab.product_config import ProductConfig, story_queue_switch
from test_ovc_pipeline import story, STORY, ROOT


class StorySwitchPipelineTests(unittest.TestCase):
    def test_story_switch_does_not_cancel_witnessed_death_penalty(self):
        profile = default_ovc_profile()
        pipeline = OvcOutputPipeline(profile)
        for now in (10, 10.1, 10.2):
            pipeline.observe(story(), [], STORY, now=now, registered_scenes=[ROOT])
        pipeline.death.trigger(pipeline.state, pipeline.policies, now=10.2, sequence=42)
        profile["channel_policies"]["A"] = story_queue_switch(profile["channel_policies"]["A"], False)
        pipeline.configure_story_channel(profile, "A")
        result = pipeline.render(now=10.3, allow_output=True)
        self.assertEqual(result.strength_a, profile["strength_death"])
        self.assertEqual(pipeline.death.sequence, 42)

    def test_every_story_mode_stops_A_without_resetting_B_or_death(self):
        for mode in ("fixed", "queue", "audio", "fixed_audio", "queue_audio"):
            with self.subTest(mode=mode):
                profile = default_ovc_profile()
                profile["channel_policies"]["A"]["story_mode"] = mode
                pipeline = OvcOutputPipeline(profile)
                for now in (10, 10.1, 10.2):
                    pipeline.observe(story(), [], STORY, now=now, registered_scenes=[ROOT])
                pipeline.render(now=10.2, allow_output=True, audio_enabled=True, audio_fresh=True,
                                audio_factor=1, audio_points=[100])
                clock_b = pipeline.queue.elapsed["B"]
                token_b = pipeline.queue.revision["B"]
                pipeline.death.sequence = 123
                profile["channel_policies"]["A"] = story_queue_switch(profile["channel_policies"]["A"], False)
                pipeline.configure_story_channel(profile, "A")
                result = pipeline.render(now=10.21, allow_output=True, audio_enabled=True,
                                         audio_fresh=True, audio_factor=1, audio_points=[100])
                self.assertEqual(result.strength_a, 0)
                self.assertGreater(result.strength_b, 0)
                self.assertGreaterEqual(pipeline.queue.elapsed["B"], clock_b)
                self.assertEqual(pipeline.queue.revision["B"], token_b)
                self.assertEqual(pipeline.death.sequence, 123)


class StorySwitchBackendTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    setUp = fixture.ChannelBackendTests.setUp
    tearDown = fixture.ChannelBackendTests.tearDown

    def test_v4_gallery_queue_waits_for_explicit_pulse_enable_then_switch_stops_A(self):
        from test_scene_library import anv
        b = self.backend
        b._config.values["socket_protocol"] = "v4"
        b._bridge = MagicMock(device_type="COYOTE_030", connected=True)
        b._device_connected = True
        b._pulse_route_paused = True
        self.assertTrue(b.saveStoryQueue("A", [{"wave": "official_tide", "duration": 5,
                                                "custom_strength": 20}], True))
        def feed(now):
            with patch("ricca_dglab.backend.time.monotonic", return_value=now):
                b._apply_state({"state": anv(), "received_at": now, "latency_ms": 1})
                b._drain()
        for now in (10, 10.1, 10.2):
            feed(now)
        self.assertEqual(b.previewA, 0)
        self.assertTrue(b.pulseRoutePaused)
        b.togglePulseOutput()
        feed(10.3)
        self.assertFalse(b.pulseRoutePaused)
        self.assertEqual(b.previewA, 20)
        self.assertTrue(b.setStoryQueueEnabled("A", False))
        feed(10.4)
        self.assertEqual(b.previewA, 0)
        self.assertFalse(b.pulseRoutePaused)

    def test_pulse_switch_is_persisted_without_changing_route_pause_or_other_channel(self):
        b = self.backend
        original = deepcopy(b._config.values)
        b._bridge = MagicMock()
        b._pulse_route_paused = True
        b._story_queue_player.elapsed["B"] = 4
        self.assertTrue(b.setStoryQueueEnabled("A", False))
        self.assertFalse(b.channelPolicies["A"]["rules"]["defeat_interaction"]["enabled"])
        self.assertTrue(b.pulseRoutePaused)
        self.assertEqual(b._story_queue_player.elapsed["B"], 4)
        self.assertEqual(b.channelPolicies["B"], original["channel_policies"]["B"])
        self.assertEqual(b.storyQueues, original["story_queues"])
        self.assertEqual(b._config.values["ovc_profile"], original["ovc_profile"])
        self.assertFalse(ProductConfig(b._config.path).values["channel_policies"]["A"]["rules"]["defeat_interaction"]["enabled"])
        self.assertEqual(b._bridge.mock_calls, [])
        self.assertTrue(b.setStoryQueueEnabled("A", True))
        self.assertTrue(b.pulseRoutePaused)
        self.assertEqual(b.channelPolicies["A"]["story_mode"], "queue")

    def test_ovc_switch_preserves_other_device_and_B_cursor(self):
        b = self.backend
        b._bridge = MagicMock()
        b._ovc_bridge = MagicMock()
        b._ovc_route_paused = True
        b._ovc_pipeline.queue.elapsed["B"] = 7
        b._ovc_pipeline.queue.revision["B"] = 2
        original = deepcopy(b._config.values)
        self.assertTrue(b.ovcController.setStoryQueueEnabled("A", False))
        self.assertFalse(b.ovcController.channelPolicies["A"]["rules"]["defeat_interaction"]["enabled"])
        self.assertEqual(b.ovcController.channelPolicies["B"], original["ovc_profile"]["channel_policies"]["B"])
        self.assertEqual(b._ovc_pipeline.queue.elapsed["B"], 7)
        self.assertEqual(b._ovc_pipeline.queue.revision["B"], 2)
        self.assertEqual(b._config.values["channel_policies"], original["channel_policies"])
        self.assertEqual(b._bridge.mock_calls, [])
        b._ovc_bridge.emergency_stop.assert_not_called()
        self.assertTrue(b.ovcRoutePaused)
        self.assertEqual(ProductConfig(b._config.path).values, b._config.values)

    def test_toggle_save_failure_keeps_runtime_and_settings(self):
        b = self.backend
        original = deepcopy(b._config.values)
        with patch.object(b._config, "save", side_effect=OSError("test failed save")):
            self.assertFalse(b.setStoryQueueEnabled("A", False))
            self.assertFalse(b.ovcController.setStoryQueueEnabled("A", False))
        self.assertEqual(b._config.values, original)
