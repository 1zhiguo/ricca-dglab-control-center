from __future__ import annotations

import math
import time
from typing import Any

from .models import RuntimeMode, SafetyDecision


SUPPORTED_GAMEASSEMBLY_SHA256 = (
    "5D815721F6B45251137DC8AB78446FAA3A79CFC3BC0520FC4D8EB8C872BDB52B"
)
STALE_AFTER_SECONDS = 0.50
VALID_REBIND_SAMPLES = 6


def game_is_paused(state: dict[str, Any]) -> bool:
    return bool(state.get("is_paused")
                or (state.get("game_ui") or {}).get("is_user_pause")
                or (state.get("story") or {}).get("act_screen_paused"))


def is_story_scene(state: dict[str, Any]) -> bool:
    """ATD 3D stories must carry an actual ADV asset, not just stale text."""
    scene = state.get("scene")
    return scene == "adv" or (
        scene == "atd"
        and str((state.get("story") or {}).get("asset_name", "")).startswith("ADV/")
    )


class SafetyGovernor:
    """Turn raw snapshots into an explicit, fail-closed runtime mode."""

    def __init__(self) -> None:
        self.last_success = 0.0
        self.last_player_address = ""
        self.valid_player_samples = 0

    def observe(self, state: dict[str, Any], now: float | None = None) -> SafetyDecision:
        now = time.monotonic() if now is None else now
        if not state.get("connected") or state.get("status") != "ok":
            return SafetyDecision(RuntimeMode.DISCONNECTED, False, False, "game-disconnected")

        self.last_success = now
        if state.get("build_supported") is False:
            self.valid_player_samples = 0
            return SafetyDecision(
                RuntimeMode.UNSUPPORTED_BUILD, False, False, "game-build-not-supported"
            )
        scene = str(state.get("scene", "unknown"))
        stage = state.get("stage") or {}
        if bool(stage.get("is_game_over")):
            return SafetyDecision(RuntimeMode.GAME_OVER, False, False, "game-over")
        if game_is_paused(state):
            return SafetyDecision(RuntimeMode.PAUSED, False, False, "game-paused")
        if (stage.get("scene_change_playing") or stage.get("all_resource_loaded") is False):
            return SafetyDecision(RuntimeMode.LOADING, False, False, "scene-loading")
        if is_story_scene(state):
            return SafetyDecision(RuntimeMode.STORY, False, True, "story")
        if scene != "gameplay":
            self.valid_player_samples = 0
            return SafetyDecision(RuntimeMode.OTHER_SCENE, False, False, f"scene-{scene}")
        current_hp = state.get("current_hp")
        if (isinstance(current_hp, (int, float))
                and math.isfinite(float(current_hp))
                and float(current_hp) <= 0.0001):
            return SafetyDecision(RuntimeMode.PLAYER_DOWN, False, False, "player-hp-zero")
        player_address = str(state.get("player_address", ""))
        maximum_hp = state.get("max_hp")
        valid_hp = (
            isinstance(current_hp, (int, float))
            and isinstance(maximum_hp, (int, float))
            and math.isfinite(float(current_hp))
            and math.isfinite(float(maximum_hp))
            and 0 <= float(current_hp) <= float(maximum_hp) * 1.1
            and 0 < float(maximum_hp) <= 10_000_000
        )
        if not player_address or player_address == "0x0" or not valid_hp:
            self.valid_player_samples = 0
            self.last_player_address = player_address
            return SafetyDecision(RuntimeMode.LOADING, False, False, "player-invalid")

        if player_address != self.last_player_address:
            self.last_player_address = player_address
            self.valid_player_samples = 1
        else:
            self.valid_player_samples += 1
        if self.valid_player_samples < VALID_REBIND_SAMPLES:
            return SafetyDecision(RuntimeMode.REBINDING, False, False, "player-rebinding")
        return SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")

    def stale(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return self.last_success <= 0 or now - self.last_success >= STALE_AFTER_SECONDS
