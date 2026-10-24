from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from ricca_dglab.dglab_bridge import pulse_message
from ricca_dglab.ovc import (
    DEFAULT_OVC_PROFILE, OVC_WAVEFORMS, default_ovc_profile,
    ovc_frames_for, ovc_waveform_catalog, sanitize_ovc_profile,
)
from ricca_dglab.product_config import DEFAULT_SETTINGS, ProductConfig


class OvcProfileTests(unittest.TestCase):
    def test_official_frames_are_valid_socket_frames_and_bounded(self):
        self.assertEqual(len(OVC_WAVEFORMS), 5)
        for key, frames in OVC_WAVEFORMS.items():
            with self.subTest(key=key):
                self.assertTrue(pulse_message("A", frames).startswith("pulse-A:"))
                for frame in frames:
                    self.assertEqual(frame[:8], "0A0A0A0A")
                    self.assertTrue(all(0 <= int(frame[i:i+2], 16) <= 100
                                        for i in range(8, 16, 2)))
        self.assertEqual(ovc_frames_for("ovc_pinpoint"), (
            "0A0A0A0A64646464", "0A0A0A0A64646464", "0A0A0A0A00000000"))
        self.assertEqual(len(ovc_frames_for("ovc_beat")), 24)

    def test_electrical_or_unknown_wave_does_not_fallback(self):
        for key in ("official_tide", "impact", "custom:mine", "unknown", ""):
            self.assertEqual(ovc_frames_for(key), ())

    def test_catalogue_has_same_ui_fields_and_only_ovc_data(self):
        for row in ovc_waveform_catalog():
            self.assertTrue({"key", "name", "points", "frequency", "color", "group",
                             "source", "description"}.issubset(row))
            self.assertEqual(row["points"], [int(frame[8:10], 16)
                                            for frame in ovc_frames_for(row["key"])])

    def test_default_profile_is_independent_and_mutable_without_aliasing(self):
        profile = default_ovc_profile()
        profile["channel_policies"]["A"]["rules"]["player_down"]["wave"] = "ovc_pinpoint"
        profile["story_queues"]["A"].clear()
        self.assertEqual(profile["channel_policies"]["B"]["rules"]["player_down"]["wave"], "ovc_trapezoid")
        self.assertEqual(len(profile["story_queues"]["B"]), 5)
        self.assertEqual(default_ovc_profile(), DEFAULT_OVC_PROFILE)
        self.assertEqual(profile["hard_cap"], 20)

    def test_all_defaults_use_vibration_waves(self):
        profile = default_ovc_profile()
        for policy in profile["channel_policies"].values():
            self.assertTrue(all(rule["wave"] in OVC_WAVEFORMS for rule in policy["rules"].values()))
        self.assertTrue(all(step["wave"] in OVC_WAVEFORMS
                            for queue in profile["story_queues"].values() for step in queue))

    def test_profile_sanitizes_bounds_and_never_imports_electrical_wave(self):
        profile = sanitize_ovc_profile({
            "hard_cap": 11, "strength_low": 50, "strength_medium": float("inf"),
            "audio_gain": float("nan"), "audio_queue_minimum": -1,
            "channel_policies": {"A": {"mode": [], "story_mode": {}, "rules": {
                "struggle": {"duration": 0.1, "wave": "impact"},
                "player_down": {"duration": 100, "wave": []},
            }}},
            "story_queues": {"A": [
                {"wave": "official_tide", "duration": 5},
                {"wave": "ovc_beat", "duration": 100, "custom_strength": 120},
            ], "B": []},
        })
        self.assertEqual(profile["strength_low"], 11)
        self.assertLessEqual(profile["strength_medium"], 11)
        self.assertEqual(profile["audio_gain"], 1.0)
        self.assertEqual(profile["audio_queue_minimum"], 0)
        rules = profile["channel_policies"]["A"]["rules"]
        self.assertIsNone(rules["struggle"]["duration"])
        self.assertEqual(rules["struggle"]["wave"], "ovc_surf_wave")
        self.assertEqual(rules["player_down"]["duration"], 10.0)
        self.assertEqual(len(profile["story_queues"]["A"]), 1)
        self.assertEqual(profile["story_queues"]["A"][0]["duration"], 30)
        self.assertEqual(profile["story_queues"]["B"], [])

    def test_custom_event_and_queue_settings_roundtrip(self):
        profile = default_ovc_profile()
        rule = profile["channel_policies"]["B"]["rules"]["damage_medium"]
        rule.update(wave="ovc_surf_wave", custom_strength=12, duration=2.3, enabled=False)
        profile["channel_policies"]["B"]["story_mode"] = "queue_audio"
        profile["story_queues"]["A"] = [
            {"wave": "ovc_beat", "duration": 7.5, "tier": "high", "custom_strength": 13},
            {"wave": "idle", "duration": 0.5, "tier": "low", "custom_strength": None},
        ]
        self.assertEqual(sanitize_ovc_profile(profile), profile)


class OvcConfigPreservationTests(unittest.TestCase):
    def test_existing_config_load_is_read_only_and_does_not_inherit_strength(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            old = deepcopy(DEFAULT_SETTINGS)
            old.pop("ovc_profile")
            old.pop("socket_protocol")
            old.update(hard_cap=90, strength_low=25, strength_medium=40,
                       strength_high=60, strength_death=80)
            old["channel_policies"]["A"]["rules"]["player_down"].update(
                wave="custom:my-old-wave", custom_strength=77, duration=8.5)
            original = json.dumps(old, ensure_ascii=False)
            path.write_text(original, encoding="utf-8")
            config = ProductConfig(path)
            self.assertEqual(path.read_text(encoding="utf-8"), original)
            self.assertEqual(config.values["socket_protocol"], "v3")
            self.assertEqual(config.values["ovc_profile"], DEFAULT_OVC_PROFILE)
            for key, expected in old.items():
                self.assertEqual(config.values[key], expected, key)
            config.update({"socket_protocol": "v4"})
            reloaded = ProductConfig(path).values
            for key, expected in old.items():
                self.assertEqual(reloaded[key], expected, key)
            self.assertEqual(path.with_suffix(".json.bak").read_text(encoding="utf-8"), original)

    def test_saving_ovc_profile_does_not_change_electrical_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ProductConfig(Path(directory) / "settings.json")
            before = deepcopy(config.values)
            profile = default_ovc_profile()
            profile.update(hard_cap=60, strength_low=11, strength_medium=22,
                           strength_high=33, strength_death=44)
            config.update({"ovc_profile": profile, "socket_protocol": "v4"})
            after = ProductConfig(config.path).values
            self.assertEqual(after["ovc_profile"], profile)
            for key, value in before.items():
                if key not in {"socket_protocol", "ovc_profile"}:
                    self.assertEqual(after[key], value, key)
            self.assertNotIn("v4_device_slot", after)


if __name__ == "__main__":
    unittest.main()
