from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeMode(str, Enum):
    DISCONNECTED = "disconnected"
    UNSUPPORTED_BUILD = "unsupported-build"
    LOADING = "loading"
    REBINDING = "rebinding"
    GAMEPLAY_READY = "gameplay-ready"
    PAUSED = "paused"
    PLAYER_DOWN = "player-down"
    STORY = "story"
    OTHER_SCENE = "other-scene"
    GAME_OVER = "game-over"
    READ_ERROR = "read-error"


@dataclass(frozen=True)
class GameEvent:
    sequence: int
    monotonic_seconds: float
    wall_time: str
    kind: str
    title: str
    detail: str = ""
    severity: str = "info"
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.sequence,
            "time": self.wall_time,
            "kind": self.kind,
            "title": self.title,
            "detail": self.detail,
            "severity": self.severity,
            "data": dict(self.data),
        }


@dataclass(frozen=True)
class SafetyDecision:
    mode: RuntimeMode
    allow_gameplay_output: bool
    allow_story_output: bool
    reason: str


@dataclass(frozen=True)
class OutputPreview:
    strength_a: float = 0.0
    wave_a: str = "idle"
    strength_b: float = 0.0
    wave_b: str = "idle"
    reason: str = "safe-idle"
