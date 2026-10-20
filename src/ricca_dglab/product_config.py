"""Persistent product settings for the standalone Ricca control center."""

from __future__ import annotations

import json
from copy import deepcopy
import hashlib
import math
import os
from pathlib import Path
import re
from typing import Any
from .scene_catalog import COLLECTED_SCENE_IDS
from .story_queue import default_story_queues, sanitize_story_queues


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
    "struggle": {"label": "持续捕获 · 直至挣脱", "enabled": True, "tier": "medium", "wave": "tap", "channel": "B", "behavior": "capture_hold"},
    "player_down": {"label": "死亡惩罚", "enabled": True, "tier": "death", "wave": "death_penalty", "channel": "AB"},
    "defeat_interaction": {"label": "场景剧情 · 循环 Pulse", "enabled": True, "tier": "medium", "wave": "official_tide", "channel": "AB", "behavior": "scene_hold", "playback": "wave"},
}

EVENT_DURATIONS = {
    "damage_light": 1.0, "damage_medium": 2.0, "damage_heavy": 2.5,
    "hit_small": 1.5, "hit_normal": 1.5, "heavy_land": 1.5,
    "wall_bounce": 1.5, "armor_break": 2.0,
    "boss_catch": 2.0, "player_down": 3.0,
    "struggle": None, "defeat_interaction": None,
}
CHANNEL_MODES = {"hp", "action", "both", "none", "audio", "off", "action_audio"}
STORY_MODES = {"fixed", "queue", "audio", "fixed_audio", "queue_audio", "off"}


def story_mode(policy: dict) -> str:
    """Resolve legacy coupled settings without overwriting explicit story choices."""
    if policy.get("story_mode") in STORY_MODES:
        return policy["story_mode"]
    playback = policy["rules"]["defeat_interaction"].get("playback")
    base = "queue" if playback == "queue" else "fixed"
    return base + "_audio" if policy.get("mode") == "action_audio" else base
for _key, _rule in DEFAULT_EVENT_RULES.items():
    _rule.update({"duration": EVENT_DURATIONS[_key], "custom_strength": None,
                  "max_duration": {"player_down": 10.0, "armor_break": 5.0}.get(_key, 3.0)})


def merge_legacy_rules(rules: dict) -> dict:
    """Canonical explicit settings win; obsolete aliases only fill missing rules."""
    merged = dict(rules)
    for old, new in (("defeat_scene_enter", "player_down"), ("capture_start", "struggle")):
        if not isinstance(merged.get(new), dict) and isinstance(merged.get(old), dict):
            merged[new] = merged[old]
        merged.pop(old, None)
    return merged


def default_channel_policies(rules: dict | None = None) -> dict[str, dict]:
    result = {
        channel: {
            "mode": mode,
            "damage_light_max": 3.0,
            "damage_medium_max": 6.0,
            "rules": deepcopy(rules if rules is not None else DEFAULT_EVENT_RULES),
        }
        for channel, mode in (("A", "both" if rules is None else "hp"), ("B", "action_audio" if rules is None else "action"))
    }
    if rules is None:
        result["A"]["rules"]["struggle"]["wave"] = "official_bouncy"
        for key in ("player_down",):
            result["A"]["rules"][key]["wave"] = "death_ramp"
        result["A"]["rules"]["defeat_interaction"]["tier"] = "low"
        result["B"]["rules"]["defeat_interaction"]["playback"] = "queue"
        b_durations = {"damage_light": 1.0, "damage_medium": 1.0, "damage_heavy": 1.5,
                       "hit_small": 0.5, "hit_normal": 1.0, "heavy_land": 1.0,
                       "wall_bounce": 1.0, "armor_break": 1.5, "boss_catch": 2.0}
        for key, duration in b_durations.items():
            result["B"]["rules"][key]["duration"] = duration
    return result


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
        if default.get("behavior") == "scene_hold":
            result["playback"] = "queue" if raw.get("playback") == "queue" else "wave"
        if (default.get("behavior") == "capture_hold"
                and raw.get("behavior") != "capture_hold" and raw.get("custom_strength") is None):
            result["tier"] = default["tier"]  # Migrate the former short-event preset to medium.
    else:
        result["duration"] = max(0.1, min(default.get("max_duration", 3.0), _number(raw.get("duration"), result["duration"])))
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
        if incoming.get("story_mode") in STORY_MODES:
            policy["story_mode"] = incoming["story_mode"]
        policy["damage_light_max"] = max(0.01, min(1000000, _number(incoming.get("damage_light_max"), 3)))
        policy["damage_medium_max"] = max(policy["damage_light_max"] + 0.01, min(1000001, _number(incoming.get("damage_medium_max"), 6)))
        rules = incoming.get("rules")
        if isinstance(rules, dict):
            rules = merge_legacy_rules(rules)
            for key, default in policy["rules"].items():
                policy["rules"][key] = sanitize_rule(rules.get(key), default)
        if "story_mode" in policy:
            policy["rules"]["defeat_interaction"]["playback"] = (
                "queue" if policy["story_mode"] in {"queue", "queue_audio"} else "wave")
    return result

DEFAULT_SETTINGS: dict[str, Any] = {
    "language": "zh",
    "format": "RiccaDGLabSettings/2",
    "strength_low": 5,
    "strength_medium": 15,
    "strength_high": 25,
    "strength_death": 25,
    "hard_cap": 30,
    "onboarding_completed": False,
    "game_hud_enabled": True,
    "game_executable_path": "",
    "scene_catalog": list(COLLECTED_SCENE_IDS),
    "story_queues": default_story_queues(),
    "audio_empathy_enabled": False,
    "audio_device_id": "",
    "audio_sensitivity": 55,
    "audio_gate": 12,
    "audio_gain": 1.0,
    "audio_queue_minimum": 0,
    "emergency_hotkey": "Ctrl+Alt+F10",
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
    catalog = raw.get("scene_catalog", result["scene_catalog"])
    if isinstance(catalog, list):
        result["scene_catalog"] = list(dict.fromkeys(
            item for item in catalog if isinstance(item, str)
            and re.fullmatch(r"Scene(?:3D|ANV)_[A-Za-z0-9_-]+", item)
        ))[:512]
    low = max(0, min(100, int(raw.get("strength_low", result["strength_low"]))))
    medium = max(low, min(100, int(raw.get("strength_medium", result["strength_medium"]))))
    high = max(medium, min(100, int(raw.get("strength_high", result["strength_high"]))))
    death = max(high, min(100, int(raw.get("strength_death", result["strength_death"]))))
    cap = max(0, min(100, int(raw.get("hard_cap", result["hard_cap"]))))
    result.update({
        "language": raw.get("language") if isinstance(raw.get("language"), str) and raw.get("language") in {"zh", "en", "ja"} else "zh",
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
        "audio_gain": round(max(0.0, min(10.0, _number(raw.get("audio_gain"), 1.0))), 1),
        "audio_queue_minimum": round(max(0.0, min(100.0, _number(raw.get("audio_queue_minimum"), 0)))),
        "emergency_hotkey": str(raw.get("emergency_hotkey") or "Ctrl+Alt+F10"),
        "audio_channel": (
            str(raw.get("audio_channel", "B")).upper()
            if str(raw.get("audio_channel", "B")).upper() in {"A", "B", "AB"}
            else "B"
        ),
        "audio_story_only": bool(raw.get("audio_story_only", True)),
    })
    incoming_rules = raw.get("event_rules")
    if isinstance(incoming_rules, dict):
        incoming_rules = merge_legacy_rules(incoming_rules)
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
        raw.get("channel_policies"), result["event_rules"] if isinstance(raw.get("event_rules"), dict) else None
    )
    result["story_queues"] = sanitize_story_queues(raw.get("story_queues"))
    return result


class ProductConfig:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings_path()
        self.values = _deep_defaults()
        self.migration_info: dict[str, Any] = {}
        self._migration_originals: dict[Path, str] = {}
        self.load()

    def load(self) -> None:
        self.migration_info = {}
        self._migration_originals = {}
        for candidate in (self.path, self.path.with_suffix(".json.bak")):
            try:
                original = candidate.read_text(encoding="utf-8")
                raw = json.loads(original)
                if not isinstance(raw, dict):
                    continue
                legacy = raw.get("format") in {None, "RiccaDGLabSettings/1"}
                merged = deepcopy(raw)
                if legacy and candidate == self.path:
                    backup = self.path.with_suffix(".json.bak")
                    try:
                        backup_text = backup.read_text(encoding="utf-8")
                        prior = json.loads(backup_text)
                        if not isinstance(prior, dict) or prior.get("format") != DEFAULT_SETTINGS["format"]:
                            raise ValueError("No current-format backup")
                        _sanitize(prior)  # Do not trust an invalid backup as completion evidence.
                        merged = {**deepcopy(prior), **merged}
                        if isinstance(prior.get("event_rules"), dict) and isinstance(raw.get("event_rules"), dict):
                            rules = deepcopy(prior["event_rules"])
                            for key, rule in raw["event_rules"].items():
                                rules[key] = ({**rules.get(key, {}), **rule}
                                              if isinstance(rule, dict) and isinstance(rules.get(key, {}), dict)
                                              else deepcopy(rule))
                            merged["event_rules"] = rules
                        if "onboarding_completed" not in raw:
                            cap = raw.get("hard_cap")
                            if type(cap) not in {int, float} or not math.isfinite(cap) or not 0 <= cap <= 100:
                                # A backup may prove a tutorial was completed, but
                                # must not invent a missing primary device limit.
                                merged["onboarding_completed"] = False
                                merged["hard_cap"] = 0
                        # Primary values always win. Recover newer per-channel fields
                        # without replacing explicitly configured legacy waveforms.
                        if "channel_policies" not in raw:
                            policies = merged.get("channel_policies")
                            if isinstance(policies, dict):
                                for policy in policies.values():
                                    if isinstance(policy, dict):
                                        rules = policy.setdefault("rules", {})
                                        for key, rule in (raw.get("event_rules") or {}).items():
                                            if isinstance(rule, dict) and isinstance(rules, dict):
                                                rules[key] = {**rules.get(key, {}), **rule}
                        self._migration_originals[backup] = backup_text
                    except (OSError, ValueError, TypeError, OverflowError):
                        pass
                self.values = _sanitize(merged)
                if legacy:
                    self._migration_originals[candidate] = original
                    self.migration_info = {
                        "from_format": raw.get("format", "legacy-unversioned"),
                        "to_format": DEFAULT_SETTINGS["format"],
                        "backup_fields_recovered": len(self._migration_originals) > 1,
                        "onboarding_recovered": "onboarding_completed" not in raw
                            and self.values["onboarding_completed"],
                        "requires_onboarding": not self.values["onboarding_completed"],
                    }
                return
            except (OSError, ValueError, TypeError, OverflowError):
                continue
        self.values = _deep_defaults()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for source, original in self._migration_originals.items():
            if source.read_text(encoding="utf-8") != original:
                raise OSError("配置在迁移期间已被其他进程修改，请重启后重新加载")
        # Save exact pre-migration files once; normal .bak rotation must not
        # destroy the only existing record of the user's newer settings.
        for source, text in self._migration_originals.items():
            preserved = source.with_name(source.name + ".pre-migration")
            if preserved.exists() and preserved.read_text(encoding="utf-8") != text:
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
                preserved = source.with_name(source.name + ".pre-migration-" + digest)
            try:
                with preserved.open("x", encoding="utf-8") as stream:
                    stream.write(text)
            except FileExistsError:
                if preserved.read_text(encoding="utf-8") != text:
                    raise OSError("原配置归档发生冲突，已保留原文件并取消保存")
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
        self._migration_originals = {}

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
