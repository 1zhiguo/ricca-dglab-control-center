from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from ricca_dglab.story_queue import StoryQueuePlayer, sanitize_steps, default_story_queues, sanitize_story_queues
from ricca_dglab.product_config import ProductConfig


def steps():
    return sanitize_steps([{"wave":"tap", "duration":1, "custom_strength":12},
                           {"wave":"idle", "duration":0.5, "custom_strength":0},
                           {"wave":"official_tide", "duration":1, "tier":"medium"}])


class StoryQueueTests(unittest.TestCase):
    def test_default_five_official_waves_and_existing_queues_are_retained(self):
        from ricca_dglab.waveforms import PRESETS
        defaults = default_story_queues()
        for plan in defaults.values():
            self.assertEqual(len(plan), 5)
            self.assertEqual(len({step["wave"] for step in plan}), 5)
            self.assertEqual(sum(step["duration"] for step in plan), 25)
            for step in plan:
                self.assertTrue(step["wave"].startswith("official_"))
                self.assertTrue(PRESETS[step["wave"]].frames)
                self.assertEqual((step["tier"], step["custom_strength"]), ("low", None))
        defaults["A"][0]["duration"] = 7
        self.assertEqual(defaults["B"][0]["duration"], 5)
        self.assertEqual(default_story_queues()["A"][0]["duration"], 5)
        self.assertEqual(sanitize_story_queues({"A":steps()})["A"], steps())
        self.assertEqual(sanitize_story_queues({"A":[]})["A"], [])

    def setUp(self):
        self.player = StoryQueuePlayer()
        self.strengths = {"low":5,"medium":15,"high":25,"death":30}

    def select(self, channel="A", cap=30):
        return self.player.select(channel, steps(), self.strengths, cap)

    def test_sequential_boundary_rest_wrap_and_independent_channels(self):
        self.player.tick("scene",0,{"A"})
        for now in (.25,.5,.75,1): self.player.tick("scene",now,{"A"})
        current = self.select()
        self.assertEqual((current["index"],current["strength"],current["wave"]),(2,0,"idle"))
        self.assertEqual(self.select("B")["index"],1)
        for now in (1.25,1.5): self.player.tick("scene",now,{"A"})
        self.assertEqual(self.select()["index"],3)
        self.assertEqual(self.select()["strength"],15)
        token = self.select()["token"]
        for now in (1.75,2,2.25,2.5): self.player.tick("scene",now,{"A"})
        self.assertEqual((self.select()["index"],self.select()["cycle"]),(1,1))
        self.assertNotEqual(self.select()["token"],token)

    def test_pause_freezes_no_catch_up_and_new_scene_restarts(self):
        self.player.tick("scene",0,{"A"})
        self.player.tick("scene",.25,{"A"})
        self.player.tick("scene",.26,set())
        self.player.tick("scene",20,set())
        self.player.tick("scene",21,{"A"})
        self.assertAlmostEqual(self.player.elapsed["A"],.25)
        self.player.tick("scene",30,{"A"})  # A long telemetry gap never jumps the cursor.
        self.assertAlmostEqual(self.player.elapsed["A"],.25)
        self.player.tick("different",30.1,{"A"})
        self.assertEqual(self.player.elapsed["A"],0)
        self.player.tick(None,30.2,set())
        self.assertEqual(self.player.elapsed["A"],0)

    def test_save_reset_changes_token_and_limits_strength(self):
        self.player.tick("scene",1,{"A"})
        before = self.select()["token"]
        self.assertEqual(self.select(cap=10)["strength"],10)
        self.player.reset("A")
        self.assertNotEqual(self.select()["token"],before)
        self.assertIsNone(self.player.select("A",[],self.strengths,30))

    def test_sanitization_bounds_invalid_values_and_excludes_recursive_sources(self):
        result = sanitize_steps([{"wave":"tap","duration":float("nan"),"custom_strength":float("inf")},
                                 {"wave":"idle","duration":-3,"custom_strength":-5},
                                 {"wave":"story-queue","duration":1},
                                 {"wave":"audio-reactive","duration":1}])
        self.assertEqual(len(result),2)
        self.assertEqual((result[0]["duration"],result[0]["custom_strength"]),(5,0))
        self.assertEqual((result[1]["duration"],result[1]["custom_strength"]),(.5,0))
        self.assertEqual(len(sanitize_steps([{"wave":"tap","duration":999}]*40)),16)
        self.assertEqual(sanitize_steps([{"wave":"tap","tier":[]}])[0]["tier"],"low")

    def test_settings_roundtrip_preserves_old_single_wave_and_separate_queues(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ProductConfig(Path(directory)/"settings.json")
            original = deepcopy(config.values["channel_policies"])
            queues = deepcopy(config.values["story_queues"])
            queues["A"] = steps()
            config.update({"story_queues":queues})
            loaded = ProductConfig(config.path)
            self.assertEqual(loaded.values["channel_policies"],original)
            self.assertEqual(loaded.values["story_queues"]["A"],steps())
            self.assertNotEqual(loaded.values["story_queues"]["A"],loaded.values["story_queues"]["B"])
            policies = deepcopy(original)
            policies["A"]["rules"]["defeat_interaction"]["playback"] = "queue"
            config.update({"channel_policies":policies})
            self.assertEqual(ProductConfig(config.path).values["channel_policies"]["A"]["rules"]["defeat_interaction"]["playback"],"queue")

