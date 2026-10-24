"""Independent Opossum vibration settings and official Socket waveform data.

The amplitude sequences below are from dungeonlab-open/dglab-kit,
src/waveform/ovc.ts (GPL-3.0). They are NOT electrical Coyote presets.
Socket frames retain the official eight-byte format; hardware-specific
translation is performed by DG-LAB 4 App, not by this profile module.
"""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any

from .story_queue import sanitize_steps


def _frames(amplitudes: tuple[int, ...]) -> tuple[str, ...]:
    return tuple("0A0A0A0A" + f"{amplitude:02X}" * 4 for amplitude in amplitudes)


# Exact official raw amplitude sequences, represented compactly without
# changing their 100 ms frame order, frequency bytes or amplitude bytes.
_WAVES = {
    "ovc_pinpoint": ("精准打击", "Pinpoint", "#97c98b", (100, 100, 0)),
    "ovc_soothe": ("舒脉", "Soothe", "#84c6bc", (
        100, 0, 100, 0, 100, 0, 100, 0, 25, 50, 75, 100, 100, 100, 75, 50, 25, 0)),
    "ovc_trapezoid": ("梯形波动", "Trapezoid", "#c4ad7e", (
        0, 20, 40, 60, 80, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
        80, 60, 40, 20, 0)),
    "ovc_beat": ("脉搏", "Beat", "#bb94c6", (
        0, 33, 66, 100, 0, 100, 0, 0) * 3),
    "ovc_surf_wave": ("踏浪起伏", "Surf Wave", "#80b2d1", (
        55, 70, 80, 90, 95, 100, 100, 100, 95, 90, 80, 70, 55)),
}

OVC_WAVEFORMS = {key: _frames(wave[3]) for key, wave in _WAVES.items()}
_JAPANESE_NAMES = {
    "ovc_pinpoint": "ピンポイント", "ovc_soothe": "リラックス",
    "ovc_trapezoid": "台形ウェーブ", "ovc_beat": "ビート",
    "ovc_surf_wave": "サーフウェーブ",
}


def ovc_frames_for(name: str, custom_catalog=()) -> tuple[str, ...]:
    """Unknown/electrical keys fail closed rather than selecting another wave."""
    return OVC_WAVEFORMS.get(str(name), ())


def ovc_waveform_catalog(custom_catalog=()) -> list[dict[str, Any]]:
    return [{
        "key": key,
        "name": "官方负鼠·" + cn,
        "name_en": en,
        "name_ja": _JAPANESE_NAMES[key],
        "description": "负鼠专用振动包络 · DG-LAB 官方",
        "source": "DG-LAB 官方 · OVC",
        "color": color,
        "points": list(amplitudes),
        "frequency": 10,
        "group": "official",
    } for key, (cn, en, color, amplitudes) in _WAVES.items()]


def _default_rules() -> dict[str, dict[str, Any]]:
    # Labels and durations are Ricca event policy, independent of official
    # waveform authors. No existing electrical user policy is read or copied.
    definitions = (
        ("damage_light", "轻微伤害", "low", "ovc_pinpoint", "A", 1.0),
        ("damage_medium", "普通受击", "medium", "ovc_beat", "A", 2.0),
        ("damage_heavy", "重度伤害", "high", "ovc_soothe", "A", 2.5),
        ("hit_small", "轻微硬直", "low", "ovc_pinpoint", "B", 0.5),
        ("hit_normal", "普通受击动作", "medium", "ovc_beat", "B", 1.0),
        ("heavy_land", "重击倒地", "high", "ovc_soothe", "B", 1.5),
        ("wall_bounce", "撞墙反弹", "high", "ovc_pinpoint", "B", 1.0),
        ("armor_break", "护甲破碎", "high", "ovc_soothe", "B", 2.0),
        ("boss_catch", "Boss 捕获", "medium", "ovc_surf_wave", "B", 2.0),
        ("struggle", "持续捕获 · 直至挣脱", "medium", "ovc_surf_wave", "B", None),
        ("player_down", "死亡惩罚", "death", "ovc_trapezoid", "AB", 3.0),
        ("defeat_interaction", "场景剧情 · 循环 Pulse", "low", "ovc_surf_wave", "AB", None),
    )
    result = {key: {
        "label": label, "enabled": key != "boss_catch", "tier": tier,
        "wave": wave, "channel": channel, "duration": duration,
        "custom_strength": None,
        "max_duration": {"player_down": 10.0, "armor_break": 5.0}.get(key, 3.0),
    } for key, label, tier, wave, channel, duration in definitions}
    result["struggle"]["behavior"] = "capture_hold"
    result["defeat_interaction"].update(behavior="scene_hold", playback="wave")
    return result


def default_ovc_profile() -> dict[str, Any]:
    rules = _default_rules()
    steps = [{"wave": wave, "duration": 5.0, "tier": "low", "custom_strength": None}
             for wave in ("ovc_soothe", "ovc_trapezoid", "ovc_beat", "ovc_surf_wave", "ovc_pinpoint")]
    policies = {channel: {
        "mode": mode, "story_mode": "queue", "damage_light_max": 3.0,
        "damage_medium_max": 6.0, "rules": deepcopy(rules),
    } for channel, mode in (("A", "both"), ("B", "action"))}
    for policy in policies.values():
        policy["rules"]["defeat_interaction"]["playback"] = "queue"
    return {
        "strength_low": 5, "strength_medium": 10, "strength_high": 15,
        "strength_death": 20, "hard_cap": 20,
        "audio_gain": 1.0, "audio_queue_minimum": 0,
        "event_rules": rules, "channel_policies": policies,
        "story_queues": {channel: deepcopy(steps) for channel in ("A", "B")},
    }


DEFAULT_OVC_PROFILE = default_ovc_profile()


def _number(value: Any, fallback: float) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else fallback
    except (ValueError, TypeError, OverflowError):
        return fallback


def _strength(value: Any, fallback: int) -> int:
    return round(max(0, min(200, _number(value, fallback))))


def _rule(raw: object, default: dict) -> dict:
    result = deepcopy(default)
    if not isinstance(raw, dict):
        return result
    result["enabled"] = raw.get("enabled", default["enabled"]) is True
    if isinstance(raw.get("tier"), str) and raw["tier"] in {"low", "medium", "high", "death"}:
        result["tier"] = raw["tier"]
    if isinstance(raw.get("channel"), str) and raw["channel"] in {"A", "B", "AB"}:
        result["channel"] = raw["channel"]
    if isinstance(raw.get("wave"), str) and raw["wave"] in OVC_WAVEFORMS:
        result["wave"] = raw["wave"]
    custom = raw.get("custom_strength")
    result["custom_strength"] = None if custom is None else _strength(custom, 0)
    if default.get("behavior") in {"capture_hold", "scene_hold"}:
        result["duration"] = None
        if default["behavior"] == "scene_hold":
            result["playback"] = "queue" if raw.get("playback") == "queue" else "wave"
    else:
        result["duration"] = round(max(0.1, min(default["max_duration"],
            _number(raw.get("duration"), default["duration"]))), 2)
    return result


def sanitize_ovc_profile(raw: object) -> dict[str, Any]:
    """Sanitize only the OVC subtree; electrical settings are never consulted."""
    result = default_ovc_profile()
    if not isinstance(raw, dict):
        return result
    cap = _strength(raw.get("hard_cap"), result["hard_cap"])
    result["hard_cap"] = cap
    for name in ("strength_low", "strength_medium", "strength_high", "strength_death"):
        result[name] = min(cap, _strength(raw.get(name), result[name]))
    result["audio_gain"] = round(max(0.0, min(10.0, _number(raw.get("audio_gain"), 1.0))), 1)
    result["audio_queue_minimum"] = _strength(raw.get("audio_queue_minimum"), 0)
    raw_rules = raw.get("event_rules")
    if isinstance(raw_rules, dict):
        for key, default in result["event_rules"].items():
            result["event_rules"][key] = _rule(raw_rules.get(key), default)
    policies = raw.get("channel_policies")
    for channel, policy in result["channel_policies"].items():
        incoming = policies.get(channel) if isinstance(policies, dict) else None
        if isinstance(incoming, dict):
            if isinstance(incoming.get("mode"), str) and incoming["mode"] in {"hp", "action", "both", "none", "audio", "off", "action_audio"}:
                policy["mode"] = incoming["mode"]
            if isinstance(incoming.get("story_mode"), str) and incoming["story_mode"] in {"fixed", "queue", "audio", "fixed_audio", "queue_audio", "off"}:
                policy["story_mode"] = incoming["story_mode"]
            policy["damage_light_max"] = max(0.01, min(1000000, _number(incoming.get("damage_light_max"), 3.0)))
            policy["damage_medium_max"] = max(policy["damage_light_max"] + 0.01, min(1000001,
                _number(incoming.get("damage_medium_max"), 6.0)))
            rules = incoming.get("rules")
            if isinstance(rules, dict):
                for key, default in policy["rules"].items():
                    policy["rules"][key] = _rule(rules.get(key), default)
            policy["rules"]["defeat_interaction"]["playback"] = (
                "queue" if policy["story_mode"] in {"queue", "queue_audio"} else "wave")
    queues = raw.get("story_queues")
    if isinstance(queues, dict):
        for channel in ("A", "B"):
            if channel in queues:
                result["story_queues"][channel] = [
                    step for step in sanitize_steps(queues[channel], max_strength=200)
                    if step["wave"] == "idle" or step["wave"] in OVC_WAVEFORMS]
    return result


# Short aliases let consumers use the same dependency-injected interface as
# waveforms.py without importing an electrical fallback catalogue.
frames_for = ovc_frames_for
waveform_catalog = ovc_waveform_catalog
