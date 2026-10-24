from __future__ import annotations

import math
import time
from typing import Any, Iterable

from .models import GameEvent, OutputPreview, RuntimeMode, SafetyDecision
from .product_config import DEFAULT_EVENT_RULES, sanitize_channel_policies
from .capture import capture_state
from .safety import is_story_scene


ACTION_EVENT_KEYS = {
    "stand_damage_small": "hit_small",
    "stand_damage": "hit_normal",
    "damage": "hit_normal",
    "damage_drilling": "hit_normal",
    "air_wall_blowOff": "wall_bounce",
    "stand_landing_blowOff": "heavy_land",
    "stand_landing_blowOff_back": "heavy_land",
}

SENSITIVITY_STAGE_MULTIPLIERS = (1.0, 1.2)


class RiccaMappingEngine:
    """Convert validated Ricca events into bounded A/B output previews."""

    def __init__(
        self,
        *,
        hard_cap: int = 30,
        strengths: dict[str, int] | None = None,
        event_rules: dict[str, dict[str, Any]] | None = None,
        channel_policies: dict | None = None,
        max_strength: int = 100,
    ) -> None:
        self.max_strength = max_strength
        self.hard_cap = max(0, min(self.max_strength, int(hard_cap)))
        self.strengths = {"low": 5, "medium": 15, "high": 25, "death": 25}
        if strengths:
            self.strengths.update({key: int(value) for key, value in strengths.items()
                                   if key in self.strengths})
        self.event_rules = {key: dict(value) for key, value in DEFAULT_EVENT_RULES.items()}
        if event_rules:
            for key, value in event_rules.items():
                if key in self.event_rules and isinstance(value, dict):
                    self.event_rules[key].update(value)
        self.channel_policies = sanitize_channel_policies(channel_policies, self.event_rules)
        self._active: dict[str, dict] = {}
        self._held: dict[str, dict] = {}
        self._selected: dict[str, dict] = {}
        self._seen: set[tuple] = set()
        self.sensitivity_stage = 0
        self._sensitivity_initialized = False
        self._last_armor_break_token: tuple[str, float | int] | None = None
        self._life_pid = None
        self._life_player = ""
        self._life_armor = -1
        self._life_dead = False
        self._awaiting_game_entry = True

    def configure(
        self,
        *,
        hard_cap: int,
        strengths: dict[str, int],
        event_rules: dict[str, dict[str, Any]],
        channel_policies: dict | None = None,
    ) -> None:
        self.hard_cap = max(0, min(self.max_strength, int(hard_cap)))
        for key in self.strengths:
            if key in strengths:
                self.strengths[key] = max(0, min(self.hard_cap, int(strengths[key])))
        for key in self.event_rules:
            incoming = event_rules.get(key)
            if isinstance(incoming, dict):
                self.event_rules[key].update(incoming)
        self.channel_policies = sanitize_channel_policies(channel_policies, self.event_rules)
        self.clear_pulses()

    def clear_pulses(self) -> None:
        self._active.clear()
        self._held.clear()
        self._selected.clear()

    def pulse_token(self, channel: str) -> str:
        active = self._selected.get(channel) or self._active.get(channel)
        return str(active["token"]) if active else "idle"

    def stop_capture_pulses(self) -> None:
        self._held.clear()
        self._selected.clear()
        for channel, active in list(self._active.items()):
            if active["key"] in {"capture_start", "struggle"}:
                del self._active[channel]

    def reconcile_capture(self, state: dict, *, allow_output: bool = True, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        capture = capture_state(state)
        for channel, active in list(self._active.items()):
            if active["key"] in {"capture_start", "struggle"} and (
                    not capture.known or not capture.active
                    or active.get("capture_address") != capture.address
                    or (active["key"] == "struggle" and not capture.can_struggle)):
                del self._active[channel]
        self._held.clear()
        self._selected.clear()
        if (not allow_output or not capture.known or not capture.active
                or state.get("is_paused") or (state.get("game_ui") or {}).get("is_user_pause")):
            return
        # Hold for the whole capture, including intervals without keypresses
        # or a temporarily closed struggle-input window. Renewed only by valid
        # telemetry; loss of refresh expires the hold within 500 ms.
        for channel, policy in self.channel_policies.items():
            rule = policy["rules"]["struggle"]
            if policy["mode"] in {"action", "both", "action_audio"} and rule["enabled"]:
                self._held[channel] = {
                    "key": "struggle", "wave": rule["wave"],
                    "strength": self._strength(rule),
                    "updated": now, "token": f"capture:{capture.address}:{channel}",
                }

    @property
    def max_sensitivity_stage(self) -> int:
        return len(SENSITIVITY_STAGE_MULTIPLIERS) - 1

    @property
    def sensitivity_multiplier(self) -> float:
        return SENSITIVITY_STAGE_MULTIPLIERS[self.sensitivity_stage]

    def synchronize_sensitivity(self, armor_level: int) -> None:
        # A stored costume/armor tier is not a fresh break in this life.
        self._sensitivity_initialized = True

    def rebase_sensitivity(self, armor_level: int) -> None:
        self.sensitivity_stage = int(armor_level >= 0)
        self._sensitivity_initialized = True
        self._last_armor_break_token = None

    def reset_sensitivity(self) -> None:
        self.sensitivity_stage = 0
        self._sensitivity_initialized = True
        self._last_armor_break_token = None

    def observe_life(self, state: dict) -> bool:
        """Reset once on game entry/respawn, not on pauses or costume tiers."""
        if state.get("connected") is False:
            self._awaiting_game_entry = True
            return False
        if state.get("status") != "ok" or state.get("build_supported") is not True:
            return False
        scene, stage = state.get("scene"), state.get("stage") or {}
        if scene != "gameplay":
            if (not is_story_scene(state) and not stage.get("scene_change_playing")
                    and stage.get("all_resource_loaded") is not False):
                self._awaiting_game_entry = True
            return False
        hp, maximum = state.get("current_hp"), state.get("max_hp")
        player = str(state.get("player_address") or "")
        if (player in {"", "0x0"} or type(hp) not in {int, float}
                or not math.isfinite(hp) or hp < 0):
            return False
        pid = state.get("process_id")
        armor = (state.get("armor") or {}).get("current_level")
        live = (hp > 0.0001 and type(maximum) in {int, float}
                and math.isfinite(maximum) and 0 < maximum <= 10_000_000
                and hp <= maximum * 1.1)
        new_session = (self._awaiting_game_entry
                       or (pid is not None and self._life_pid is not None and pid != self._life_pid))
        restored_rebind = (live and self._life_player and player != self._life_player
                          and self._life_armor >= 0 and type(armor) is int and armor < 0)
        reset = bool(new_session or (live and self._life_dead) or restored_rebind)
        if reset:
            self.reset_sensitivity()
            self.clear_pulses()
            self._life_dead = False
        if hp <= 0.0001:
            self._life_dead = True
        self._awaiting_game_entry = False
        if pid is not None:
            self._life_pid = pid
        self._life_player = player
        if type(armor) is int:
            self._life_armor = armor
        return reset

    @staticmethod
    def _feedback_key(event: GameEvent) -> str:
        if event.kind == "action":
            # Only confirmed damage actions can trigger output. Guard and
            # unknown actions remain diagnostic events, never punishments.
            return ACTION_EVENT_KEYS.get(str(event.data.get("action", "")), "")
        return {
            "armor_break": "armor_break",
            "boss_catch": "boss_catch",
            "player_down": "player_down",
        }.get(event.kind, "")

    def accept(self, events: Iterable[GameEvent], *, allow_output: bool = True) -> None:
        for event in events:
            token = (event.sequence, event.monotonic_seconds, event.kind)
            if token in self._seen:
                continue
            self._seen.add(token)
            if len(self._seen) > 2048:
                self._seen = {token}
            if event.kind in {"rebind", "scene", "pause", "player_down"}:
                self.clear_pulses()
            if event.kind == "capture_end":
                self.stop_capture_pulses()
                continue
            if event.kind == "armor_break":
                if self.sensitivity_stage:
                    continue  # One break feedback and one fixed boost per life.
                self._sensitivity_initialized = True
                break_time = event.data.get("last_break_time")
                token: tuple[str, float | int] = (
                    ("clock", float(break_time))
                    if isinstance(break_time, (int, float))
                    else ("event", event.sequence)
                )
                if token != self._last_armor_break_token:
                    self.sensitivity_stage = 1
                    self._last_armor_break_token = token
            key = self._feedback_key(event)
            if event.kind != "damage" and not key:
                continue
            if not allow_output and key != "player_down":
                continue
            for channel, policy in self.channel_policies.items():
                mode = policy["mode"]
                if mode in {"off", "audio"}:
                    continue
                if event.kind == "damage":
                    if mode not in {"hp", "both"}:
                        continue
                    key = self._damage_key(float(event.data.get("amount", 0)), policy)
                elif key != "player_down" and mode not in {"action", "both", "action_audio"}:
                    continue
                rule = policy["rules"].get(key, {})
                if not rule.get("enabled"):
                    continue
                strength = self._strength(rule)
                existing = self._active.get(channel)
                current_strength = self._remaining_strength(existing, event.monotonic_seconds)
                current_strength = max(current_strength, self._held_strength(channel, event.monotonic_seconds))
                if strength > 0 and strength >= current_strength:
                    self._active[channel] = {
                        "start": event.monotonic_seconds,
                        "duration": rule["duration"],
                        "strength": strength,
                        "wave": rule["wave"],
                        "key": key,
                        "token": f"{event.sequence}:{event.monotonic_seconds}:{key}",
                        "capture_address": event.data.get("capture_address"),
                    }
                    self._selected.pop(channel, None)

    def _damage_key(self, amount: float, policy: dict) -> str:
        if amount <= policy["damage_light_max"]:
            return "damage_light"
        if amount <= policy["damage_medium_max"]:
            return "damage_medium"
        return "damage_heavy"

    def _strength(self, rule: dict[str, Any]) -> float:
        tier = str(rule.get("tier", "low"))
        custom = rule.get("custom_strength")
        value = float(custom if custom is not None else self.strengths.get(tier, self.strengths["low"]))
        # Apply the life multiplier once in the backend, after HP/action/audio/
        # CG arbitration, so held and already-active pulses change consistently.
        return min(float(self.hard_cap), value)

    def preview(self, safety: SafetyDecision, now: float | None = None) -> OutputPreview:
        now = time.monotonic() if now is None else now
        if not safety.allow_gameplay_output and safety.mode != RuntimeMode.PLAYER_DOWN:
            self.clear_pulses()
            return OutputPreview(reason=safety.reason)
        outputs = []
        self._selected.clear()
        for channel in ("A", "B"):
            active = self._active.get(channel)
            strength = self._remaining_strength(active, now)
            if safety.mode == RuntimeMode.PLAYER_DOWN and active and active["key"] != "player_down":
                strength = 0
            if strength <= 0:
                self._active.pop(channel, None)
            held_strength = self._held_strength(channel, now) if safety.allow_gameplay_output else 0
            if held_strength > 0 and held_strength >= strength:
                active, strength = self._held[channel], held_strength
            if strength > 0 and active:
                self._selected[channel] = active
            outputs.extend((min(self.hard_cap, strength), active["wave"] if strength > 0 else "idle"))
        return OutputPreview(*outputs, "death-preview-only" if safety.mode == RuntimeMode.PLAYER_DOWN else "event-preview")

    def _held_strength(self, channel: str, now: float) -> float:
        held = self._held.get(channel)
        if held and 0 <= now - held["updated"] < 0.5:
            return held["strength"]
        return 0.0

    @staticmethod
    def _remaining_strength(active: dict | None, now: float) -> float:
        if not active:
            return 0.0
        age = now - active["start"]
        if age < 0 or age >= active["duration"]:
            return 0.0
        # Keep the death diagnostic at the configured strength; regular events
        # retain the existing linear release envelope.
        if active["key"] == "player_down":
            return active["strength"]
        return active["strength"] * max(0.0, 1 - age / active["duration"])
