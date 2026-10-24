"""Bounded scene playlists and a pause-aware clock; no device operations."""
from copy import deepcopy
import math

MAX_STEPS = 16


def default_story_queues():
    # Shared low-tier bases; the selected channel's story mode decides whether
    # audio modulates them. Existing saved queues are never replaced on load.
    steps = [{"wave": wave, "duration": 5.0, "tier": "low", "custom_strength": None}
             for wave in ("official_breath", "official_tide", "official_gradual",
                          "official_bouncy", "official_ripple")]
    return {channel: deepcopy(steps) for channel in ("A", "B")}


def number(value, fallback):
    try:
        result = float(value)
        return result if math.isfinite(result) else fallback
    except (TypeError, ValueError, OverflowError):
        return fallback


def sanitize_steps(raw, *, max_strength=100):
    if not isinstance(raw, list):
        return []
    result = []
    for step in raw[:MAX_STEPS]:
        if not isinstance(step, dict):
            continue
        wave = str(step.get("wave") or "").strip()[:128]
        if not wave or wave in {"story-queue", "audio-reactive"}:
            continue
        tier = step.get("tier")
        custom = step.get("custom_strength")
        result.append({"wave": wave,
                       "duration": round(max(0.5, min(30.0, number(step.get("duration"), 5))), 2),
                       "tier": tier if isinstance(tier, str) and tier in {"low", "medium", "high", "death"} else "low",
                       "custom_strength": None if custom is None else round(max(0, min(max_strength, number(custom, 0))))})
    return result


def sanitize_story_queues(raw):
    result = default_story_queues()
    if isinstance(raw, dict):
        for channel in result:
            if channel in raw:
                result[channel] = sanitize_steps(raw[channel])
    return result


class StoryQueuePlayer:
    def __init__(self):
        self.key = None
        self.channel_keys = {"A": None, "B": None}
        self.revision = {"A": 0, "B": 0}
        self.elapsed = {"A": 0.0, "B": 0.0}
        self.last = {"A": None, "B": None}

    def reset(self, channel=None):
        for name in ((channel,) if channel else ("A", "B")):
            self.elapsed[name], self.last[name] = 0.0, None
            self.revision[name] += 1

    def tick(self, key, now, active_channels):
        self.key = key
        for channel in ("A", "B"):
            channel_key = key.get(channel) if isinstance(key, dict) else key
            if channel_key != self.channel_keys[channel]:
                self.reset(channel)
                self.channel_keys[channel] = channel_key
            previous = self.last[channel]
            if channel_key and channel in active_channels:
                # Never catch up across stale reads, a paused UI or a blocked device.
                if previous is not None and 0 <= now - previous < 0.5:
                    self.elapsed[channel] += now - previous
                self.last[channel] = now
            else:
                self.last[channel] = None

    def select(self, channel, steps, strengths, cap):
        if not steps:
            return None
        total = sum(step["duration"] for step in steps)
        if total <= 0:
            return None
        elapsed = self.elapsed[channel]
        cycle = int(elapsed // total)
        position = elapsed % total
        for index, step in enumerate(steps):
            if position < step["duration"] or index == len(steps) - 1:
                raw = step["custom_strength"]
                strength = strengths.get(step["tier"], 0) if raw is None else raw
                return {"index": index + 1, "count": len(steps), "cycle": cycle,
                        "wave": step["wave"], "strength": min(cap, max(0, strength)),
                        "remaining": round(max(0.0, step["duration"] - position), 1),
                        "duration": step["duration"],
                        "token": f"queue:{channel}:{self.revision[channel]}:{cycle}:{index}"}
            position -= step["duration"]
        return None
