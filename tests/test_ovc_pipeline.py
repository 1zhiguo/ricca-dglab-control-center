"""Pure OVC strategy tests: no Qt, files, networking or device operations."""
from copy import deepcopy
import unittest

from ricca_dglab.mapping import RiccaMappingEngine
from ricca_dglab.models import GameEvent, RuntimeMode, SafetyDecision
from ricca_dglab.ovc import default_ovc_profile
from ricca_dglab.ovc_pipeline import OvcOutputPipeline


READY = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
STORY = SafetyDecision(RuntimeMode.STORY, False, True, "story")
PAUSED = SafetyDecision(RuntimeMode.PAUSED, False, False, "game-paused")
DOWN = SafetyDecision(RuntimeMode.PLAYER_DOWN, False, False, "player-hp-zero")
ROOT = "SceneANV_Test"


def state(**updates):
    result = {"status": "ok", "connected": True, "build_supported": True, "process_id": 42,
              "scene": "gameplay", "player_address": "0x123", "current_hp": 30.0,
              "max_hp": 31.0, "stage": {"all_resource_loaded": True}, "is_paused": False}
    result.update(updates)
    return result


def story(**updates):
    return state(scene="anv", story={"asset_name": f"ADV/{ROOT}/test.csv"}, **updates)


def event(sequence, now, kind="damage", **data):
    return GameEvent(sequence, now, "now", kind, "test", data=data)


class OvcPipelineTests(unittest.TestCase):
    def test_200_level_events_survive_mapping_and_reconfigure(self):
        profile = default_ovc_profile()
        profile.update(hard_cap=200, strength_low=150, strength_medium=160,
                       strength_high=180, strength_death=200)
        profile["channel_policies"]["A"]["rules"]["damage_light"]["custom_strength"] = 190
        self.pipeline = OvcOutputPipeline(profile)
        for sequence, now in ((1, 10), (2, 20)):
            self.observe(events=[event(sequence, now, amount=2)], now=now)
            self.assertEqual(self.render(now=now).strength_a, 190)
            self.assertEqual(self.pipeline.mapping.hard_cap, 200)
            profile["audio_gain"] = 2
            profile["strength_medium"] = 170
            self.pipeline.configure(profile)

    def setUp(self):
        self.profile = default_ovc_profile()
        self.pipeline = OvcOutputPipeline(self.profile)

    def observe(self, snapshot=None, events=(), now=10, decision=READY, **kw):
        self.pipeline.observe(snapshot or state(), events, decision, now=now,
                              registered_scenes=[ROOT], **kw)

    def render(self, now=10, **kw):
        return self.pipeline.render(now=now, allow_output=kw.pop("allow_output", True), **kw)

    def confirm_story(self, now=10, snapshot=None):
        for offset in (0, .1, .2):
            self.observe(snapshot or story(), now=now + offset, decision=STORY)

    def test_damage_and_action_are_independent_from_electrical_mapper(self):
        electrical = RiccaMappingEngine(hard_cap=90, strengths={"low": 30})
        electrical.observe_life(state())
        hit = event(1, 10, amount=2)
        electrical.accept([hit])
        self.observe(events=[hit])
        result = self.render()
        self.assertEqual(result.strength_a, 5)
        self.assertEqual(result.wave_a, "ovc_pinpoint")
        self.assertEqual(electrical.preview(READY, 10).strength_a, 30)
        self.assertEqual(result.frames_a[0][:8], "0A0A0A0A")
        self.assertEqual(result.strength_b, 0)
        self.assertTrue(result.allowed)
        self.assertFalse(result.paused)

    def test_capture_holds_until_escape_without_timer(self):
        caught = state(capture={"info_address": "0x1000", "current_break_off_count": 1,
                                "break_off_count_max": 12, "break_off_acceptance": True})
        self.observe(caught)
        self.assertEqual(self.render().strength_b, 10)
        self.observe(caught, now=13)
        self.assertEqual(self.render(13).strength_b, 10)
        escaped = deepcopy(caught)
        escaped["capture"]["info_address"] = "0x0"
        self.observe(escaped, [event(1, 13.1, "capture_end")], now=13.1)
        self.assertEqual(self.render(13.1).strength_b, 0)
        self.assertEqual(self.render(13.7).strength_a, 0)

    def test_stronger_event_replaces_weaker_without_mutating_input(self):
        snapshot = state()
        first = event(1, 10, amount=1)
        self.observe(snapshot, [first])
        self.assertEqual(self.render().strength_a, 5)
        second = event(2, 10.1, amount=10)
        original = deepcopy(second.as_dict())
        self.observe(snapshot, [second], now=10.1)
        self.assertEqual(self.render(10.1).strength_a, 15)
        self.assertEqual(second.as_dict(), original)
        self.assertNotEqual(self.render(10.1).wave_key_a, self.render(10.1).wave_key_b)

    def test_deferred_hp_event_uses_own_profile(self):
        self.observe()
        self.pipeline.accept_events([event(1, 10.1, amount=4)], allow_output=True)
        result = self.render(10.1)
        self.assertEqual(result.strength_a, 10)
        self.assertEqual(result.wave_a, "ovc_beat")

    def test_death_outranks_ordinary_pause_not_emergency(self):
        self.observe()
        self.observe(state(current_hp=0, is_paused=True), [event(1, 10.1, "player_down")],
                     now=10.1, decision=PAUSED, user_paused=True)
        result = self.render(10.1, user_paused=True)
        self.assertEqual(result.priority_kind, "death")
        self.assertEqual((result.strength_a, result.strength_b), (20, 20))
        self.assertFalse(result.paused)
        result = self.render(10.2, emergency_stop=True)
        self.assertFalse(result.allowed)
        self.assertEqual((result.strength_a, result.strength_b), (0, 0))
        self.observe(state(current_hp=0), now=10.3, decision=DOWN)
        self.assertEqual(self.render(10.3).strength_a, 0)

    def test_no_death_is_queued_while_device_disabled_and_no_duplicate_retrigger(self):
        death = event(1, 10, "player_down")
        self.observe(state(current_hp=0), [death], decision=DOWN, allow_output=False)
        self.assertEqual(self.render().strength_a, 0)
        self.observe(state(current_hp=0), [death], now=10.1, decision=DOWN)
        self.assertEqual(self.render(10.1).strength_a, 0)

    def test_death_not_manufactured_by_entering_gallery(self):
        self.confirm_story()
        result = self.render(10.2)
        self.assertEqual(result.priority_kind, "story-loop")
        self.assertEqual(result.strength_a, 5)
        self.assertEqual(self.pipeline.death.sequence, 0)

    def test_five_wave_queue_cycles_and_pause_freezes_clock(self):
        self.confirm_story()
        self.assertEqual(self.render(10.2).wave_a, "ovc_soothe")
        for index in range(1, 23):
            now = 10.2 + index * .25
            self.observe(story(), now=now, decision=STORY)
            self.render(now)
        self.assertEqual(self.render(now).wave_a, "ovc_trapezoid")
        elapsed = self.pipeline.queue.elapsed["A"]
        self.observe(story(), now=now + .1, decision=STORY, user_paused=True)
        result = self.render(now + .1, user_paused=True)
        self.assertEqual(result.strength_a, 0)
        self.assertEqual(self.pipeline.queue.elapsed["A"], elapsed)
        self.observe(story(), now=now + .2, decision=STORY)
        self.render(now + .2)
        self.assertEqual(self.pipeline.queue.elapsed["A"], elapsed)

    def test_audio_queue_uses_vibration_gain_and_floor_and_silence_keeps_time(self):
        self.profile["channel_policies"]["A"]["story_mode"] = "queue_audio"
        self.profile.update(audio_gain=2, audio_queue_minimum=3)
        self.pipeline.configure(self.profile)
        self.observe(story(), decision=STORY)
        result = self.render(audio_enabled=True, audio_fresh=True, audio_factor=.5)
        self.assertEqual(result.strength_a, 5)
        self.observe(story(), now=10.2, decision=STORY)
        result = self.render(10.2, audio_enabled=True, audio_fresh=True, audio_factor=0,
                             audio_above_gate=False)
        self.assertEqual(result.strength_a, 3)
        self.assertAlmostEqual(self.pipeline.queue.elapsed["A"], .2)
        self.assertEqual(self.render(10.2, audio_enabled=True, audio_fresh=False,
                                     audio_factor=1).strength_a, 0)

    def test_audio_never_drives_combat_and_stale_or_disabled_audio_has_no_floor(self):
        self.profile["channel_policies"]["A"]["story_mode"] = "queue_audio"
        self.profile["audio_queue_minimum"] = 8
        self.pipeline.configure(self.profile)
        self.observe()
        self.assertEqual(self.render(audio_enabled=True, audio_fresh=True, audio_factor=1).strength_a, 0)
        self.observe(story(), now=10.1, decision=STORY)
        for enabled, fresh in ((False, True), (True, False), (False, False)):
            self.assertEqual(self.render(10.1, audio_enabled=enabled, audio_fresh=fresh,
                                        audio_factor=1).strength_a, 0)

    def test_real_time_audio_frames_are_vibration_format(self):
        self.profile["channel_policies"]["A"]["story_mode"] = "audio"
        self.pipeline.configure(self.profile)
        self.observe(story(), decision=STORY)
        result = self.render(audio_enabled=True, audio_fresh=True, audio_factor=.5, audio_points=[30]*16)
        self.assertEqual(result.strength_a, 2.5)
        self.assertEqual(result.wave_a, "audio-reactive")
        self.assertEqual(result.frames_a[0], "0A0A0A0A1E1E1E1E")
        self.assertEqual(self.render(audio_enabled=True, audio_fresh=True,
                                     audio_factor=.5, audio_points=[]).strength_a, 0)

    def test_fixed_audio_and_fixed_modes_are_independent_per_channel(self):
        self.profile["channel_policies"]["A"]["story_mode"] = "fixed_audio"
        self.profile["channel_policies"]["B"]["story_mode"] = "fixed"
        self.pipeline.configure(self.profile)
        self.confirm_story()
        result = self.render(10.2, audio_enabled=True, audio_fresh=True, audio_factor=.4)
        self.assertEqual((result.strength_a, result.strength_b), (2, 5))
        self.assertEqual((result.wave_a, result.wave_b), ("ovc_surf_wave", "ovc_surf_wave"))

    def test_registered_dialogue_controller_pause_still_loops_but_user_menu_stops(self):
        snapshot = story(is_paused=True)
        for now in (10, 10.1, 10.2):
            self.observe(snapshot, now=now, decision=PAUSED)
        self.assertGreater(self.render(10.2).strength_a, 0)
        snapshot["game_ui"] = {"is_user_pause": True}
        self.observe(snapshot, now=10.3, decision=PAUSED)
        self.assertEqual(self.render(10.3).strength_a, 0)

    def test_unknown_scene_exit_loading_and_stale_reads_fail_closed(self):
        self.confirm_story()
        self.assertGreater(self.render(10.2).strength_a, 0)
        self.assertEqual(self.render(10.8).strength_a, 0)
        for snapshot in (state(scene="other"), story(stage={"scene_change_playing": True}),
                         story(status="error"), story(build_supported=False)):
            self.observe(snapshot, now=11, decision=STORY)
            self.assertEqual(self.render(11).strength_a, 0)

    def test_disabled_queue_rule_and_rest_produce_no_vibration(self):
        self.profile["story_queues"]["A"] = [
            {"wave": "idle", "duration": 5, "tier": "low", "custom_strength": 10}]
        self.profile["channel_policies"]["B"]["rules"]["defeat_interaction"]["enabled"] = False
        self.pipeline.configure(self.profile)
        self.confirm_story()
        result = self.render(10.2)
        self.assertEqual((result.strength_a, result.strength_b), (0, 0))
        self.assertEqual(result.frames_a, ())

    def test_configuration_hard_cap_and_clear_are_route_local(self):
        original = deepcopy(self.profile)
        self.observe(events=[event(1, 10, amount=10)])
        self.assertGreater(self.render().strength_a, 0)
        self.profile["hard_cap"] = 4
        self.pipeline.configure(self.profile)
        self.assertEqual(self.render().strength_a, 0)
        self.observe(events=[event(2, 10.1, amount=10)], now=10.1)
        self.assertLessEqual(self.render(10.1).strength_a, 4)
        self.pipeline.stop()
        self.assertFalse(self.render(10.1).allowed)
        self.assertEqual(default_ovc_profile(), original)

    def test_armor_multiplier_is_once_and_resets_on_respawn(self):
        self.observe(events=[event(1, 10, "armor_break", last_break_time=10)])
        self.assertEqual(self.pipeline.mapping.sensitivity_multiplier, 1.2)
        self.observe(events=[event(2, 10.1, "armor_break", last_break_time=10.1)], now=10.1)
        self.assertEqual(self.pipeline.mapping.sensitivity_multiplier, 1.2)
        self.observe(state(current_hp=0), now=10.2, decision=DOWN)
        self.observe(state(current_hp=31), now=10.3)
        self.assertEqual(self.pipeline.mapping.sensitivity_multiplier, 1)

    def test_summary_does_not_expose_raw_waveform_payloads(self):
        self.observe(events=[event(1, 10, amount=2)])
        summary = self.render().as_dict()
        self.assertNotIn("frames_a", summary)
        self.assertEqual(summary["wave_a"], "ovc_pinpoint")

    def test_audio_parameter_save_preserves_queue_clock_and_pending_events(self):
        self.profile["channel_policies"]["A"]["story_mode"] = "queue_audio"
        self.pipeline.configure(self.profile)
        self.observe(story(), decision=STORY)
        self.render(audio_enabled=True, audio_fresh=True, audio_factor=.5)
        self.observe(story(), now=10.2, decision=STORY)
        first = self.render(10.2, audio_enabled=True, audio_fresh=True, audio_factor=.5)
        elapsed = self.pipeline.queue.elapsed["A"]
        token = first.wave_key_a
        self.profile.update(audio_gain=2, audio_queue_minimum=3)
        self.pipeline.configure(self.profile)
        changed = self.render(10.2, audio_enabled=True, audio_fresh=True, audio_factor=.5)
        self.assertEqual(changed.wave_key_a, token)
        self.assertEqual(self.pipeline.queue.elapsed["A"], elapsed)
        self.assertEqual((first.strength_a, changed.strength_a), (2.5, 5))


if __name__ == "__main__":
    unittest.main()
