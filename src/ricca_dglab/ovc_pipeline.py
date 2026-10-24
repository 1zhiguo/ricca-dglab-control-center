"""Independent, transport-free Opossum vibration event pipeline.

The electrical backend owns its own mapper, queue clock and death cue. This
module consumes the same validated game events without changing any of them,
and produces a second bounded output plan. It never talks to a device, opens
audio, reads user settings, or imports Qt.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
from typing import Iterable

from .defeat_scene import DeathPenalty, DefeatSceneSession, scene_root
from .mapping import RiccaMappingEngine
from .models import GameEvent, RuntimeMode, SafetyDecision
from .ovc import frames_for, sanitize_ovc_profile
from .product_config import story_mode
from .safety import game_is_paused, is_story_scene
from .story_queue import StoryQueuePlayer, sanitize_steps


def _number(value, default=0.0):
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError, OverflowError):
        return default


@dataclass(frozen=True)
class OvcOutputPlan:
    strength_a: float = 0.0
    wave_a: str = "idle"
    strength_b: float = 0.0
    wave_b: str = "idle"
    frames_a: tuple[str, ...] = ()
    frames_b: tuple[str, ...] = ()
    wave_key_a: str = "idle"
    wave_key_b: str = "idle"
    hard_cap: int = 0
    allowed: bool = False
    paused: bool = True
    priority_kind: str = ""
    reason: str = "starting"
    queue_status: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        """Small UI/audit summary; never copies raw waveform frame payloads."""
        return {name: deepcopy(getattr(self, name)) for name in (
            "strength_a", "wave_a", "strength_b", "wave_b", "hard_cap",
            "allowed", "paused", "priority_kind", "reason", "queue_status")}


class OvcOutputPipeline:
    def __init__(self, profile=None):
        self.profile = sanitize_ovc_profile(profile)
        self.mapping = RiccaMappingEngine(
            hard_cap=self.hard_cap, strengths=self.strengths,
            event_rules=self.profile["event_rules"],
            channel_policies=self.profile["channel_policies"], max_strength=200)
        # OVC has its own validated rules; the electrical sanitizer caps at 100.
        self.mapping.channel_policies = deepcopy(self.policies)
        self.defeat = DefeatSceneSession()
        self.death = DeathPenalty()
        self.queue = StoryQueuePlayer()
        self.state: dict = {}
        self.decision = SafetyDecision(RuntimeMode.DISCONNECTED, False, False, "starting")
        self.updated = 0.0
        self.observed = False
        self.queue_status = {}
        self._death_seen = set()

    @property
    def hard_cap(self) -> int:
        return self.profile["hard_cap"]

    @property
    def strengths(self) -> dict[str, int]:
        return {name: self.profile["strength_" + name]
                for name in ("low", "medium", "high", "death")}

    @property
    def policies(self) -> dict:
        return self.profile["channel_policies"]

    def configure(self, profile) -> None:
        """Apply vibration settings; audio scalar changes preserve playback."""
        clean = sanitize_ovc_profile(profile)
        runtime_fields = {key: value for key, value in self.profile.items()
                          if key not in {"audio_gain", "audio_queue_minimum"}}
        incoming_fields = {key: value for key, value in clean.items()
                           if key not in {"audio_gain", "audio_queue_minimum"}}
        self.profile = clean
        if runtime_fields == incoming_fields:
            # These parameters scale the current audio-modulated segment. They
            # must not restart a playlist or erase an unrelated battle cue.
            return
        self.mapping.configure(hard_cap=self.hard_cap, strengths=self.strengths,
                               event_rules=self.profile["event_rules"],
                               channel_policies=self.policies)
        self.mapping.channel_policies = deepcopy(self.policies)
        self.clear_pulses()

    def configure_story_channel(self, profile: dict, channel: str) -> None:
        """Apply one story switch without cancelling another channel or death."""
        clean = sanitize_ovc_profile(profile)
        self.profile["channel_policies"][channel] = deepcopy(clean["channel_policies"][channel])
        self.mapping.channel_policies = deepcopy(self.policies)
        self.queue.reset(channel)

    def clear_pulses(self) -> None:
        self.mapping.clear_pulses()
        self.death.cancel()
        self.defeat.cancel_pulses()
        self.queue.reset()
        self.queue_status = {}

    def stop(self) -> None:
        """Stop this output independently; a fresh observation is required."""
        self.clear_pulses()
        self.observed = False

    def _valid_state(self) -> bool:
        return bool(self.state.get("status") == "ok"
                    and self.state.get("connected", True)
                    and self.state.get("build_supported") is True
                    and self.state.get("process_id"))

    def _story_allowed(self) -> bool:
        stage = self.state.get("stage") or {}
        return bool(self._valid_state() and is_story_scene(self.state)
                    and not stage.get("is_game_over")
                    and not stage.get("scene_change_playing")
                    and stage.get("all_resource_loaded") is not False)

    def observe(self, state: dict, events: Iterable[GameEvent], decision: SafetyDecision,
                *, now: float, registered_scenes=(), blocked_scenes=(),
                allow_output=True, user_paused=False, emergency_stop=False,
                story_allowed=None) -> None:
        self.state, self.decision = deepcopy(state), decision
        self.updated, self.observed = float(now), True
        if self.mapping.observe_life(state):
            self.death.cancel()
        story = self._story_allowed() and story_allowed is not False
        self.defeat.observe(state, now=now, allow_story=story,
                            paused=bool(emergency_stop),
                            registered_scenes=registered_scenes,
                            blocked_scenes=blocked_scenes)
        ordinary = bool(allow_output and not emergency_stop and not user_paused
                        and not game_is_paused(state) and decision.allow_gameplay_output)
        self.mapping.reconcile_capture(state, allow_output=ordinary, now=now)
        self.accept_events(events, allow_output=bool(allow_output and not emergency_stop),
                           ordinary_output=ordinary)
        if emergency_stop or not self._valid_state():
            self.clear_pulses()

    def accept_events(self, events: Iterable[GameEvent], *, allow_output=True,
                      ordinary_output=None) -> None:
        """Also accepts deferred HP events from the shared detector's tick."""
        materialized = tuple(events)
        if ordinary_output is None:
            ordinary_output = bool(allow_output and self.decision.allow_gameplay_output
                                   and not game_is_paused(self.state))
        ordinary_events = []
        for event in materialized:
            if event.kind != "player_down":
                ordinary_events.append(event)
                continue
            self.mapping.clear_pulses()
            token = (self.state.get("process_id"), event.sequence, event.monotonic_seconds)
            if token in self._death_seen:
                continue
            self._death_seen.add(token)
            if len(self._death_seen) > 256:
                self._death_seen = {token}
            self.defeat.record_death(self.state, event.monotonic_seconds)
            if allow_output and self._valid_state() and self.hard_cap > 0:
                self.death.trigger(self.state, self.policies,
                                   now=event.monotonic_seconds, sequence=event.sequence)
        # Dedicated death ownership prevents a disabled route from retaining a
        # mapping-engine death cue and replaying it when it connects later.
        self.mapping.accept(ordinary_events, allow_output=bool(ordinary_output))

    def render(self, *, now: float, allow_output: bool, user_paused=False,
               emergency_stop=False, telemetry_fresh=True, audio_enabled=False,
               audio_fresh=False, audio_factor=0.0, audio_points=(),
               audio_above_gate=True, story_allowed=None) -> OvcOutputPlan:
        fresh = bool(telemetry_fresh and self.observed and 0 <= now - self.updated < 0.5)
        eligible = bool(allow_output and not emergency_stop and fresh
                        and self._valid_state() and self.hard_cap > 0)
        if not eligible:
            self.mapping.clear_pulses()
            self.death.cancel()
            self.defeat.interrupt(now)
            self.queue.tick({ch: self.queue.channel_keys[ch] for ch in ("A", "B")}, now, set())
            self.queue_status = {ch: {**status, "playing": False}
                                 for ch, status in self.queue_status.items()}
            reason = ("emergency-stop" if emergency_stop else "telemetry-stale" if not fresh
                      else "invalid-state" if not self._valid_state() else "output-disabled")
            return OvcOutputPlan(hard_cap=self.hard_cap, reason=reason,
                                 queue_status=deepcopy(self.queue_status))

        ordinary_paused = bool(user_paused or game_is_paused(self.state))
        decision = (SafetyDecision(RuntimeMode.PAUSED, False, False, "output-paused")
                    if ordinary_paused else self.decision)
        preview = self.mapping.preview(decision, now)
        outputs = {"A": [preview.strength_a, preview.wave_a, self.mapping.pulse_token("A")],
                   "B": [preview.strength_b, preview.wave_b, self.mapping.pulse_token("B")]}
        story = self._story_allowed() and story_allowed is not False
        loop_allowed = not (user_paused or (self.state.get("game_ui") or {}).get("is_user_pause"))
        cg = self.defeat.preview(self.policies, self.strengths, self.hard_cap, now=now,
                                 allow=story, allow_loop=loop_allowed)
        death = self.death.preview(self.state, self.strengths, self.hard_cap, now=now)
        dying = death.strength_a > 0 or death.strength_b > 0
        session = self.defeat
        queue_ready = bool(story and loop_allowed and not dying and session.root
                           and session.confirm_count >= 3 and 0 <= now - session.updated < .5
                           and session.phase in {"dialogue", "interaction", "stopped"})
        asset = str((self.state.get("story") or {}).get("asset_name") or "")
        audio_ready = bool(story and loop_allowed and not dying and audio_enabled
                           and audio_fresh and asset.startswith("ADV/"))
        factor = min(1.0, max(0.0, _number(audio_factor))) if audio_ready and audio_above_gate else 0.0
        audio_channels = {ch for ch, policy in self.policies.items()
                          if story_mode(policy) in {"audio", "fixed_audio", "queue_audio"}}
        queue_channels = {ch for ch, policy in self.policies.items()
                          if policy["mode"] != "off" and policy["rules"]["defeat_interaction"]["enabled"]
                          and (story_mode(policy) == "queue" or ch in audio_channels)}
        active_channels = {ch for ch in queue_channels if audio_ready and ch in audio_channels}
        active_channels |= {ch for ch in queue_channels if ch not in audio_channels and queue_ready}
        scene_key = (session.pid, session.root, session.sequence) if session.root else None
        audio_key = (self.state.get("process_id"), "audio-story", scene_root(asset) or asset) if story else None
        self.queue.tick({ch: audio_key if ch in audio_channels else scene_key for ch in ("A", "B")},
                        now, active_channels)
        queue_active = {}
        queue_status = {}
        for ch in ("A", "B"):
            rule = self.policies[ch]["rules"]["defeat_interaction"]
            plan = self.profile["story_queues"][ch]
            mode = story_mode(self.policies[ch])
            if ch in audio_channels and mode != "queue_audio":
                plan = sanitize_steps([{**rule, "duration": 30}])
            selected = self.queue.select(ch, plan, self.strengths, self.hard_cap)
            active = ch in active_channels and selected is not None
            if selected:
                selected = dict(selected)
                selected["audio_modulated"] = ch in audio_channels
                if ch in audio_channels:
                    if mode == "audio":
                        selected["wave"] = "audio-reactive"
                    base = selected["strength"]
                    gain = self.profile["audio_gain"]
                    floor = (min(self.hard_cap, self.profile["audio_queue_minimum"])
                             if active and audio_ready and gain > 0 and mode == "queue_audio"
                             and base > 0 and selected["wave"] != "idle" else 0)
                    selected.update(base_strength=base, audio_factor=factor, audio_gain=gain,
                                    minimum_strength=floor,
                                    strength=min(self.hard_cap, max(floor, base * factor * gain)))
                missing = selected["wave"] not in {"idle", "audio-reactive"} and not frames_for(selected["wave"])
                if missing or selected["wave"] == "idle":
                    selected["strength"] = 0
                selected.update(playing=active, enabled=ch in queue_channels, missing_wave=bool(missing))
            queue_status[ch] = {**(selected or {"count": 0, "playing": False, "enabled": ch in queue_channels}),
                                "configured": rule.get("playback") == "queue"}
            if active:
                queue_active[ch] = selected
        self.queue_status = queue_status
        priority = False
        for ch, strength, wave in (("A", cg.strength_a, cg.wave_a), ("B", cg.strength_b, cg.wave_b)):
            if ch in queue_active:
                item = queue_active[ch]
                outputs[ch] = [item["strength"], item["wave"], self.defeat.token(ch) + item["token"]]
                priority = True
            elif strength > 0 and strength >= outputs[ch][0]:
                outputs[ch] = [strength, wave, self.defeat.token(ch)]
                priority = True
        for ch, strength, wave in (("A", death.strength_a, death.wave_a), ("B", death.strength_b, death.wave_b)):
            if strength > 0:
                outputs[ch] = [strength, wave, self.death.token(ch)]
                priority = True
        allowed = bool(priority or (not ordinary_paused and
                       (self.decision.allow_gameplay_output or self.decision.allow_story_output)))
        priority_kind = ("death" if dying else "story-audio" if any(ch in queue_active for ch in audio_channels)
                         else "story-loop") if priority else ""
        clean_points = tuple(max(0, min(100, round(_number(value)))) for value in audio_points)
        audio_frames = (tuple("0A0A0A0A" + f"{value:02X}" * 4 for value in clean_points)
                        if len(clean_points) == 16 and audio_ready else ())
        values = {}
        for ch in ("A", "B"):
            strength, wave, token = outputs[ch]
            strength = min(self.hard_cap, max(0.0, strength * self.mapping.sensitivity_multiplier)) if allowed else 0.0
            frames = audio_frames if wave == "audio-reactive" else frames_for(wave)
            if not frames:
                strength = 0.0
            values[ch] = (float(strength), wave if strength > 0 else "idle",
                          frames if strength > 0 else (), wave + ":" + token)
        a, b = values["A"], values["B"]
        return OvcOutputPlan(a[0], a[1], b[0], b[1], a[2], b[2], a[3], b[3],
                             self.hard_cap, allowed, not allowed, priority_kind,
                             "priority-" + priority_kind if priority else decision.reason,
                             deepcopy(queue_status))
