"""Persistent product settings for the standalone Ricca control center."""

from __future__ import annotations

import json
from copy import deepcopy
import math
import os
from pathlib import Path
import re
from typing import Any


DEFAULT_EVENT_RULES: dict[str, dict[str, Any]] = {
    "damage_light": {"label": "轻微伤害", "enabled": True, "tier": "low", "wave": "official_breath", "channel": "A"},
    "damage_medium": {"label": "普通受击", "enabled": True, "tier": "medium", "wave": "impact", "channel": "A"},
    "damage_heavy": {"label": "重度伤害", "enabled": True, "tier": "high", "wave": "heavy_land", "channel": "A"},
    "hit_small": {"label": "轻微硬直", "enabled": True, "tier": "low", "wave": "tap", "channel": "B"},
    "hit_normal": {"label": "普通受击动作", "enabled": True, "tier": "medium", "wave": "impact", "channel": "B"},
    "heavy_land": {"label": "重击倒地", "enabled": True, "tier": "high", "wave": "heavy_land", "channel": "B"},
    "wall_bounce": {"label": "撞墙反弹", "enabled": True, "tier": "high", "wave": "wall", "channel": "B"},
    "armor_break": {"label": "护甲破碎", "enabled": True, "tier": "high", "wave": "armor_break", "channel": "B"},
    "boss_catch": {"label": "Boss 捕获", "enabled": False, "tier": "medium", "wave": "official_tide", "channel": "B"},
    "capture_start": {"label": "通用捕获开始", "enabled": True, "tier": "low", "wave": "official_tide", "channel": "B"},
    "struggle": {"label": "挣扎中 · 持续至挣脱", "enabled": True, "tier": "medium", "wave": "tap", "channel": "B", "behavior": "capture_hold"},
    "player_down": {"label": "死亡惩罚", "enabled": True, "tier": "death", "wave": "death_penalty", "channel": "AB"},
    "defeat_scene_enter": {"label": "败北场景 · 入场惩罚", "enabled": True, "tier": "death", "wave": "death_penalty", "channel": "AB"},
    "defeat_interaction": {"label": "败北互动 · 循环 Pulse", "enabled": True, "tier": "medium", "wave": "official_tide", "channel": "AB", "behavior": "scene_hold"},
}

EVENT_DURATIONS = {
    "damage_light": 0.8, "damage_medium": 1.1, "damage_heavy": 1.4,
    "hit_small": 0.55, "hit_normal": 0.8, "heavy_land": 1.2,
    "wall_bounce": 1.2, "armor_break": 1.4,
    "boss_catch": 1.8, "player_down": 2.8,
    "capture_start": 1.0, "struggle": None,
    "defeat_scene_enter": 2.8, "defeat_interaction": None,
}
CHANNEL_MODES = {"hp", "action", "both", "audio", "off"}
for _key, _rule in DEFAULT_EVENT_RULES.items():
    _rule.update({"duration": EVENT_DURATIONS[_key], "custom_strength": None})


def default_channel_policies(rules: dict | None = None) -> dict[str, dict]:
    return {
        channel: {
            "mode": mode,
            "damage_light_max": 3.0,
            "damage_medium_max": 6.0,
            "rules": deepcopy(rules if rules is not None else DEFAULT_EVENT_RULES),
        }
        for channel, mode in (("A", "hp"), ("B", "action"))
    }


def _number(value: Any, fallback: float) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else fallback
    except (ValueError, TypeError):
        return fallback


def sanitize_rule(raw: object, default: dict) -> dict:
    result = dict(default)
    if not isinstance(raw, dict):
        return result
    result["enabled"] = bool(raw.get("enabled", result["enabled"]))
    if raw.get("tier") in {"low", "medium", "high", "death"}:
        result["tier"] = raw["tier"]
    result["wave"] = str(raw.get("wave") or result["wave"])
    if default.get("behavior") in {"capture_hold", "scene_hold"}:
        result["duration"] = None  # Legacy durations cannot override state lifetime.
        if raw.get("behavior") != "capture_hold" and raw.get("custom_strength") is None:
            result["tier"] = default["tier"]  # Migrate the former short-event preset to medium.
    else:
        result["duration"] = max(0.1, min(3.0, _number(raw.get("duration"), result["duration"])))
    custom = raw.get("custom_strength")
    result["custom_strength"] = None if custom is None else max(0, min(100, round(_number(custom, 0))))
    return result


def sanitize_channel_policies(raw: object, legacy_rules: dict | None = None) -> dict[str, dict]:
    result = default_channel_policies(legacy_rules)
    if not isinstance(raw, dict):
        return result
    for channel, policy in result.items():
        incoming = raw.get(channel)
        if not isinstance(incoming, dict):
            continue
        if incoming.get("mode") in CHANNEL_MODES:
            policy["mode"] = incoming["mode"]
        policy["damage_light_max"] = max(0.01, min(1000000, _number(incoming.get("damage_light_max"), 3)))
        policy["damage_medium_max"] = max(policy["damage_light_max"] + 0.01, min(1000001, _number(incoming.get("damage_medium_max"), 6)))
        rules = incoming.get("rules")
        if isinstance(rules, dict):
            # Preserve the user's old death waveform/strength/duration when
            # introducing the separately named, real scene-entry punishment.
            if "defeat_scene_enter" not in rules and isinstance(rules.get("player_down"), dict):
                rules = {**rules, "defeat_scene_enter": rules["player_down"]}
            for key, default in policy["rules"].items():
                policy["rules"][key] = sanitize_rule(rules.get(key), default)
    return result

DEFAULT_SETTINGS: dict[str, Any] = {
    "format": "RiccaDGLabSettings/2",
    "strength_low": 5,
    "strength_medium": 15,
    "strength_high": 25,
    "strength_death": 25,
    "hard_cap": 30,
    "onboarding_completed": False,
    "game_hud_enabled": True,
    "game_executable_path": "",
    "audio_empathy_enabled": False,
    "audio_device_id": "",
    "audio_sensitivity": 55,
    "audio_gate": 12,
    "audio_channel": "B",
    "audio_story_only": True,
    "event_rules": DEFAULT_EVENT_RULES,
    "channel_policies": default_channel_policies(),
}


def app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    return Path(base) / "Ricca-x-DGlab" if base else Path.home() / ".ricca-x-dglab"


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def waveform_library_dir() -> Path:
    return app_data_dir() / "waveforms"


def _deep_defaults() -> dict[str, Any]:
    return deepcopy(DEFAULT_SETTINGS)


def _sanitize(raw: object) -> dict[str, Any]:
    result = _deep_defaults()
    if not isinstance(raw, dict):
        return result
    low = max(0, min(100, int(raw.get("strength_low", result["strength_low"]))))
    medium = max(low, min(100, int(raw.get("strength_medium", result["strength_medium"]))))
    high = max(medium, min(100, int(raw.get("strength_high", result["strength_high"]))))
    death = max(high, min(100, int(raw.get("strength_death", result["strength_death"]))))
    cap = max(0, min(100, int(raw.get("hard_cap", result["hard_cap"]))))
    result.update({
        "strength_low": min(low, cap),
        "strength_medium": min(medium, cap),
        "strength_high": min(high, cap),
        "strength_death": min(death, cap),
        "hard_cap": cap,
        "onboarding_completed": raw.get("onboarding_completed") is True,
        "game_hud_enabled": bool(raw.get("game_hud_enabled", True)),
        "game_executable_path": str(raw.get("game_executable_path", "")).strip(),
        "audio_empathy_enabled": bool(raw.get(
            "audio_empathy_enabled", raw.get("story_audio_enabled", False)
        )),
        "audio_device_id": str(raw.get("audio_device_id", "")).strip(),
        "audio_sensitivity": max(1, min(100, int(raw.get(
            "audio_sensitivity", raw.get("story_audio_sensitivity", 55)
        )))),
        "audio_gate": max(0, min(95, int(raw.get("audio_gate", 12)))),
        "audio_channel": (
            str(raw.get("audio_channel", "B")).upper()
            if str(raw.get("audio_channel", "B")).upper() in {"A", "B", "AB"}
            else "B"
        ),
        "audio_story_only": bool(raw.get("audio_story_only", True)),
    })
    incoming_rules = raw.get("event_rules")
    if isinstance(incoming_rules, dict):
        if "defeat_scene_enter" not in incoming_rules and isinstance(incoming_rules.get("player_down"), dict):
            incoming_rules = {**incoming_rules, "defeat_scene_enter": incoming_rules["player_down"]}
        for key, default in DEFAULT_EVENT_RULES.items():
            incoming = incoming_rules.get(key)
            if not isinstance(incoming, dict):
                continue
            merged = sanitize_rule(incoming, default)
            if incoming.get("channel") in {"A", "B", "AB"}:
                merged["channel"] = incoming["channel"]
            wave = str(incoming.get("wave", default["wave"])).strip()
            merged["wave"] = wave or default["wave"]
            result["event_rules"][key] = merged
    result["channel_policies"] = sanitize_channel_policies(
        raw.get("channel_policies"), result["event_rules"]
    )
    return result


class ProductConfig:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()
        self.values = _deep_defaults()
        self.load()

    def load(self) -> None:
        for candidate in (self.path, self.path.with_suffix(".json.bak")):
            try:
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    continue
                self.values = _sanitize(raw)
                return
            except (OSError, ValueError, TypeError, OverflowError):
                continue
        self.values = _deep_defaults()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Keep a last-known-good copy; never replace it with a corrupt primary.
        try:
            previous = self.path.read_text(encoding="utf-8")
            raw = json.loads(previous)
            if not isinstance(raw, dict):
                raise ValueError("Invalid settings")
            _sanitize(raw)
        except (OSError, ValueError, TypeError, OverflowError):
            previous = None
        if previous is not None:
            backup = self.path.with_suffix(".json.bak")
            backup_temp = self.path.with_suffix(".json.bak.tmp")
            backup_temp.write_text(previous, encoding="utf-8")
            backup_temp.replace(backup)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.values, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)

    def update(self, values: dict[str, Any]) -> None:
        previous = self.values
        merged = {**self.values, **values}
        self.values = _sanitize(merged)
        try:
            self.save()
        except OSError:
            self.values = previous
            raise


def _safe_stem(name: str) -> str:
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", name.strip()).strip("-_")
    return (stem or "custom-wave")[:64]


def save_custom_waveform(name: str, points: list[int], frequency: int) -> Path:
    clean_name = str(name).strip()[:64] or "自定义波形"
    clean_points = [max(0, min(100, int(value))) for value in points]
    if len(clean_points) != 16:
        raise ValueError("自定义波形必须包含 16 个控制点")
    clean_frequency = max(10, min(240, int(frequency)))
    directory = waveform_library_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{_safe_stem(clean_name)}.json"
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps({
        "format": "RiccaDGLabWaveform/1",
        "name": clean_name,
        "points": clean_points,
        "frequency": clean_frequency,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def read_custom_waveforms() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    directory = waveform_library_dir()
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            points = [max(0, min(100, int(value))) for value in raw.get("points", [])]
            frequency = max(10, min(240, int(raw.get("frequency", 80))))
            if len(points) != 16:
                continue
            result.append({
                "key": f"custom:{path.stem}",
                "name": str(raw.get("name") or path.stem),
                "description": "用户自定义 16 点包络",
                "source": "我的波形库",
                "color": "#40e0d0",
                "points": points,
                "frequency": frequency,
                "group": "custom",
                "file": str(path),
            })
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return result
