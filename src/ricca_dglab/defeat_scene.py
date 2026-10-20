"""Defeat-to-CG evidence tracking and bounded, per-channel CG output.

No game writes, audio capture, device connection, or persisted output permission.
Opening a gallery/attaching inside a CG cannot manufacture a defeat transition.
"""
from __future__ import annotations

import math
import re

from .models import OutputPreview


def scene_root(asset: object) -> str:
    match = re.fullmatch(r"ADV/(Scene3D_[A-Za-z0-9_-]+)/[^/]+\.csv", str(asset or ""))
    return match.group(1) if match else ""


class DeathPenalty:
    """A bounded cue from a witnessed HP edge, independent of ordinary pauses."""

    def __init__(self):
        self.cancel()

    def cancel(self):
        self.pid = None
        self.started = 0.0
        self.rules = {}
        self.sequence = 0

    def trigger(self, state, policies, *, now, sequence):
        self.pid = state.get("process_id")
        self.started, self.sequence = now, sequence
        self.rules = {channel: dict(policy["rules"]["player_down"])
                      for channel, policy in policies.items() if policy["mode"] != "off"}

    def preview(self, state, strengths, cap, *, now):
        if (not self.pid or state.get("process_id") != self.pid
                or state.get("status") != "ok" or not state.get("connected", True)
                or state.get("build_supported") is not True):
            return OutputPreview(reason="death-blocked")
        values = []
        for channel in ("A", "B"):
            rule = self.rules.get(channel)
            strength, wave = 0.0, "idle"
            if rule and rule["enabled"] and 0 <= now - self.started < rule["duration"]:
                strength = min(cap, max(0, rule["custom_strength"] if rule["custom_strength"] is not None
                                        else strengths[rule["tier"]]))
                wave = rule["wave"] if strength > 0 else "idle"
            values.extend((float(strength), wave))
        return OutputPreview(*values, "death-priority")

    def token(self, channel):
        return f"death:{self.pid}:{self.sequence}:{self.started}:{channel}"


class DefeatSceneSession:
    def __init__(self):
        self.sequence = 0
        self.reset()

    def reset(self):
        self.pid = None
        self.pending_root = ""
        self.pending_until = 0.0
        self.witnessed_death = False
        self.root = ""
        self.phase = "idle"
        self.entry_pending = False
        self.penalty_cancelled = False
        self.penalty_started = None
        self.penalty_suspended_at = None
        self.updated = 0.0
        self.confirm_count = 0
        self.cut = ""

    def cancel_pulses(self):
        # Hard stops/config changes never queue a deferred punishment.
        self.penalty_cancelled = True
        self.entry_pending = False
        self.penalty_started = None
        self.penalty_suspended_at = None

    def suspend_penalty(self, now: float):
        """Automatic scene pauses freeze remaining time, never consume it."""
        if self.penalty_started is not None and self.penalty_suspended_at is None:
            self.penalty_suspended_at = now

    def interrupt(self, now: float):
        # A transient scene read failure blocks output, not the witnessed death.
        self.suspend_penalty(now)
        self.confirm_count = 0

    def record_death(self, state: dict, now: float):
        # Called only for EventDetector's validated same-actor positive -> zero
        # edge. This is stronger evidence than the optional candidate string.
        self.witnessed_death = True
        self.pending_until = now + 90

    def observe(self, state: dict, *, now: float, allow_story: bool, paused: bool):
        changes = []
        pid = state.get("process_id")
        if state.get("status") != "ok" and state.get("connected", True):
            self.interrupt(now)
            return changes
        if (state.get("status") != "ok" or not state.get("connected", True)
                or state.get("build_supported") is not True or not pid):
            self.reset()
            return changes
        if self.pid != pid:
            self.reset()
            self.pid = pid
        self.updated = now
        stage = state.get("stage") or {}
        if stage.get("is_game_over"):
            self.reset()
            return changes
        hp = state.get("current_hp")
        if state.get("scene") == "gameplay":
            if self.root:
                changes.append(("defeat_scene_end", "败北场景结束", self.root))
                self.reset()
                self.pid = pid
                self.updated = now
            if isinstance(hp, (int, float)) and math.isfinite(hp):
                if hp <= 0.0001 and state.get("player_address"):
                    hint = str(state.get("defeat_scene_hint") or "")
                    # This field is only a candidate until a matching live ATD
                    # asset arrives. It is not an active-CG flag by itself.
                    if re.fullmatch(r"Scene3D_[A-Za-z0-9_-]+", hint):
                        self.pending_root = hint
                        self.pending_until = now + 90
                elif hp > 0.0001:
                    self.pending_root = ""
                    self.witnessed_death = False
                    self.penalty_cancelled = False
            self.phase = "waiting" if self.pending_root or self.witnessed_death else "idle"
            return changes
        root = scene_root((state.get("story") or {}).get("asset_name"))
        if state.get("scene") != "atd" or not root:
            # Allow bounded loading gaps, but never output during the gap.
            if stage.get("scene_change_playing") or stage.get("all_resource_loaded") is False:
                self.suspend_penalty(now)
                self.confirm_count = 0
                self.phase = "loading"
            else:
                self.reset()
            return changes
        if self.root and self.root != root:
            self.reset()
            return changes
        if not self.root:
            matched = root == self.pending_root or (not self.pending_root and self.witnessed_death)
            if not matched or now > self.pending_until:
                self.phase = "unconfirmed"
                self.pending_root = ""
                return changes
            self.root = root
            self.pending_root = ""
            self.entry_pending = not self.penalty_cancelled
            self.sequence += 1
            changes.append(("defeat_scene_enter", "进入败北场景", root))
        atd = state.get("atd") or {}
        speed = atd.get("animation_speed")
        known = (atd.get("ui_start_atd") is True
                 and type(atd.get("playing_adv_state")) is int
                 and atd["playing_adv_state"] in {0, 1, 2}
                 and type(atd.get("cut_index")) is int and atd["cut_index"] >= 0
                 and bool(atd.get("cut_name"))
                 and isinstance(speed, (int, float)) and math.isfinite(speed) and speed >= 0)
        old = self.phase
        self.cut = str(atd.get("cut_name") or "")
        self.phase = ("interaction" if atd["playing_adv_state"] == 0 and speed > 0
                      else "dialogue" if atd["playing_adv_state"] in {1, 2}
                      else "stopped") if known else "unknown"
        if self.phase != old:
            changes.append(("defeat_phase", "败北场景阶段变化", self.phase + " · " + self.cut))
        if paused:
            self.cancel_pulses()
        if allow_story and known and not paused:
            self.confirm_count += 1
        else:
            self.confirm_count = 0
            self.suspend_penalty(now)
        if self.confirm_count >= 3 and self.penalty_suspended_at is not None:
            self.penalty_started += max(0.0, now - self.penalty_suspended_at)
            self.penalty_suspended_at = None
        if not paused and allow_story and self.entry_pending and known and self.confirm_count >= 3:
            self.entry_pending = False
            self.penalty_started = now
        return changes

    def preview(self, policies: dict, strengths: dict, cap: int, *, now: float, allow: bool,
                allow_loop: bool = True) -> OutputPreview:
        if (not allow or not self.root or self.confirm_count < 3
                or self.penalty_suspended_at is not None or not 0 <= now - self.updated < 0.5):
            return OutputPreview(reason="defeat-scene-blocked")
        values = []
        penalty = False
        for channel in ("A", "B"):
            policy = policies[channel]
            best, wave = 0.0, "idle"
            if policy["mode"] != "off" and self.phase not in {"unknown", "loading", "unconfirmed"}:
                rules = policy["rules"]
                for key, active in (
                    ("defeat_scene_enter", self.penalty_started is not None and
                     0 <= now - self.penalty_started < rules["defeat_scene_enter"]["duration"]),
                    ("defeat_interaction", self.phase == "interaction" and allow_loop),
                ):
                    rule = rules[key]
                    if active and rule["enabled"]:
                        strength = min(cap, max(0, rule["custom_strength"] if rule["custom_strength"] is not None else strengths[rule["tier"]]))
                        if strength > best:
                            best, wave = float(strength), rule["wave"]
                        if key == "defeat_scene_enter" and strength > 0:
                            penalty = True
                            break  # Death outranks other feedback, not just its numeric strength.
            values.extend((best, wave))
        return OutputPreview(*values, "defeat-penalty" if penalty else "defeat-interaction")

    def token(self, channel: str) -> str:
        return f"defeat:{self.pid}:{self.root}:{self.sequence}:{channel}"
