from __future__ import annotations

from datetime import datetime
import math
import time
from typing import Any

from .models import GameEvent
from .capture import capture_state
from .safety import game_is_paused


DAMAGE_WINDOW_SECONDS = 0.30
ACTION_LABELS = {
    "stand_damage": "普通受击",
    "stand_damage_small": "轻微硬直",
    "damage": "空中受击",
    "damage_drilling": "连续受击",
    "air_wall_blowOff": "撞墙反弹",
    "stand_landing_blowOff": "重击倒地",
    "stand_landing_blowOff_back": "背向倒地",
    "stand_guard_start": "开始防御",
    "stand_guard_hit": "格挡命中",
}

# Player/Boss action pairs observed at the same gameplay instant.  Requiring
# both sides prevents a generic Unknown/StandAction hash from being promoted
# to a catch event on its own.
BOSS_CATCH_SIGNATURES = {
    (362220413, 662097121): "Boss 捕获",
}
PLAYER_DOWN_ACTION_HASH = 2141194317


class EventDetector:
    def __init__(self) -> None:
        self.previous: dict[str, Any] | None = None
        self.pending_damage: dict[str, Any] | None = None
        self.sequence = 0

    def _event(
        self,
        kind: str,
        title: str,
        detail: str = "",
        severity: str = "info",
        data: dict[str, Any] | None = None,
        now: float | None = None,
    ) -> GameEvent:
        self.sequence += 1
        return GameEvent(
            self.sequence,
            time.monotonic() if now is None else now,
            datetime.now().astimezone().isoformat(timespec="milliseconds"),
            kind,
            title,
            detail,
            severity,
            data or {},
        )

    def _flush_damage(self, now: float, *, force: bool = False) -> list[GameEvent]:
        pending = self.pending_damage
        if not pending:
            return []
        if not force and now - pending["last"] < DAMAGE_WINDOW_SECONDS:
            return []
        maximum = pending["max_hp"]
        ratio = pending["total"] / maximum if maximum > 0 else 0.0
        self.pending_damage = None
        return [
            self._event(
                "damage",
                f"累计受伤 −{pending['total']:.3g} HP",
                f"{pending['before']:.3g} → {pending['after']:.3g} · 最大生命 {ratio * 100:.1f}%",
                "danger",
                {
                    "amount": pending["total"],
                    "ratio": ratio,
                    "before": pending["before"],
                    "after": pending["after"],
                    "window_ms": round((pending["last"] - pending["started"]) * 1000),
                },
                now,
            )
        ]

    def tick(self, now: float | None = None) -> list[GameEvent]:
        return self._flush_damage(time.monotonic() if now is None else now)

    def reset(self, now: float | None = None) -> list[GameEvent]:
        now = time.monotonic() if now is None else now
        events = self._flush_damage(now, force=True)
        self.previous = None
        return events

    def ingest(self, current: dict[str, Any], now: float | None = None) -> list[GameEvent]:
        now = time.monotonic() if now is None else now
        events: list[GameEvent] = []
        previous = self.previous
        if previous is None:
            events.append(self._event("attach", "已连接游戏", f"PID {current.get('process_id', '—')}", "success", now=now))
            self.previous = current
            return events

        scene_changed = current.get("scene") != previous.get("scene")
        player_rebound = current.get("player_address") != previous.get("player_address")
        combat_valid = (
            current.get("scene") == "gameplay"
            and not game_is_paused(current)
            and not scene_changed and not player_rebound
        )
        if not combat_valid:
            self.pending_damage = None
        if scene_changed:
            events.append(self._event("scene", "场景控制器切换", f"{previous.get('scene', '—')} → {current.get('scene', '—')}", "accent", now=now))
        if player_rebound:
            current_armor = current.get("armor") or {}
            previous_armor = previous.get("armor") or {}
            events.append(self._event(
                "rebind",
                "玩家对象重新绑定",
                f"{previous.get('player_address', '—')} → {current.get('player_address', '—')}",
                "warning",
                {
                    "player_before": previous.get("player_address"),
                    "player_after": current.get("player_address"),
                    "armor_level_before": previous_armor.get("current_level"),
                    "armor_level_after": current_armor.get("current_level"),
                },
                now,
            ))
            # HP values from two different CharacterActor objects must never be
            # interpreted as one damage edge.
            self.pending_damage = None
        if game_is_paused(current) != game_is_paused(previous):
            paused = game_is_paused(current)
            events.append(self._event("pause", "游戏已暂停" if paused else "游戏已恢复", f"pause mask {current.get('pause_mask', 0)}", "warning" if paused else "success", now=now))

        current_hp = current.get("current_hp")
        capture = capture_state(current)
        old_capture = capture_state(previous)
        same_actor = not scene_changed and not player_rebound
        was_paused = game_is_paused(previous)
        if same_actor and old_capture.known and old_capture.active:
            if not capture.known or not capture.active or capture.address != old_capture.address:
                events.append(self._event(
                    "capture_end", "捕获结束" if capture.known else "捕获读取失效",
                    "停止捕获与挣扎 Pulse", "success" if capture.known else "warning", now=now))
        # Do not replay capture/struggle on attach, resume or read recovery.
        # Count increases describe progress, not exact individual keypresses.
        if combat_valid and not was_paused and old_capture.known and capture.known:
            if capture.active and (not old_capture.active or capture.address != old_capture.address):
                events.append(self._event("capture_start", "通用捕获", "检测到捕获对象", "warning",
                                          {"capture_address": capture.address}, now))
            elif (capture.active and old_capture.active and capture.address == old_capture.address
                  and capture.can_struggle and old_capture.can_struggle
                  and capture.maximum == old_capture.maximum
                  and capture.count - old_capture.count > 0.05):
                events.append(self._event("struggle", "挣扎进度增加",
                    f"{old_capture.count:.2f} → {capture.count:.2f} / {capture.maximum:.2f}", "accent",
                    {"capture_address": capture.address, "count": capture.count,
                     "maximum": capture.maximum, "delta": capture.count - old_capture.count}, now))
        previous_hp = previous.get("current_hp")
        maximum = current.get("max_hp")
        if (combat_valid and
                all(isinstance(item, (int, float)) for item in (current_hp, previous_hp, maximum))):
            delta = float(current_hp) - float(previous_hp)
            if delta < -0.0001:
                amount = -delta
                if self.pending_damage and now - self.pending_damage["last"] <= DAMAGE_WINDOW_SECONDS:
                    self.pending_damage["total"] += amount
                    self.pending_damage["after"] = float(current_hp)
                    self.pending_damage["last"] = now
                else:
                    events.extend(self._flush_damage(now, force=True))
                    self.pending_damage = {
                        "started": now,
                        "last": now,
                        "total": amount,
                        "before": float(previous_hp),
                        "after": float(current_hp),
                        "max_hp": float(maximum),
                    }
            elif delta > 0.0001:
                events.append(self._event("heal", f"生命恢复 +{delta:.3g} HP", f"{float(previous_hp):.3g} → {float(current_hp):.3g}", "success", now=now))

        # Death actions differ between normal defeat, capture and special CGs.
        # Use a validated positive -> zero HP edge on the same player instead;
        # attaching at zero or changing actor/scene must not replay a death.
        down_now = (
            current.get("scene") == "gameplay"
            and current.get("status") == "ok"
            and current.get("build_supported") is not False
            and current.get("connected", True)
            and current.get("player_address") not in {None, "", "0x0"}
            and type(current_hp) in {int, float} and math.isfinite(current_hp)
            and 0 <= current_hp <= 0.0001
            and type(maximum) in {int, float} and math.isfinite(maximum)
            and 0 < maximum <= 10_000_000
            and type(previous_hp) in {int, float} and math.isfinite(previous_hp)
            and previous_hp > 0.0001
        )
        if down_now and not scene_changed and not player_rebound:
            events.extend(self._flush_damage(now, force=True))
            events.append(self._event(
                "player_down",
                "玩家倒下",
                f"HP {float(previous_hp):.3g} → 0 · action {current.get('action_trigger_hash', '—')}",
                "danger",
                {
                    "action": "player_down",
                    "hp": current_hp,
                    "max_hp": maximum,
                    "action_hash": current.get("action_trigger_hash"),
                    "death_evidence": "hp-zero-edge",
                    "character_state": current.get("character_state_name"),
                    "action_time": current.get("action_time"),
                },
                now,
            ))

        trigger = current.get("action_trigger_name")
        current_action_time = current.get("action_time")
        previous_action_time = previous.get("action_time")
        action_restarted = (
            isinstance(current_action_time, (int, float))
            and isinstance(previous_action_time, (int, float))
            and float(current_action_time) + 0.08 < float(previous_action_time)
        )
        trigger_edge = (
            trigger != previous.get("action_trigger_name")
            or current.get("action_trigger_hash") != previous.get("action_trigger_hash")
            or current.get("action_trigger_enabled") != previous.get("action_trigger_enabled")
            or action_restarted
        )
        current_boss = current.get("boss") or {}
        previous_boss = previous.get("boss") or {}
        catch_signature = (
            current.get("action_trigger_hash"),
            current_boss.get("action_trigger_hash"),
        )
        catch_edge = trigger_edge or (
            current_boss.get("action_trigger_hash")
            != previous_boss.get("action_trigger_hash")
        )
        if combat_valid and catch_edge and catch_signature in BOSS_CATCH_SIGNATURES:
            story = current.get("story") or {}
            events.append(self._event(
                "boss_catch",
                BOSS_CATCH_SIGNATURES[catch_signature],
                (
                    f"player {catch_signature[0]} · boss {catch_signature[1]} · "
                    f"{story.get('speaker') or '无提示'}"
                ),
                "danger",
                {
                    "action": "boss_catch",
                    "player_action_hash": catch_signature[0],
                    "boss_action_hash": catch_signature[1],
                    "player_action_time": current_action_time,
                    "boss_action_time": current_boss.get("action_time"),
                    "story_asset": story.get("asset_name"),
                    "story_message": story.get("stripped_message") or story.get("message"),
                },
                now,
            ))
        elif combat_valid and trigger_edge and trigger in ACTION_LABELS:
            events.append(self._event("action", ACTION_LABELS[str(trigger)], f"{trigger} · {current.get('action_trigger_hash', '—')}", "accent", {"action": trigger}, now))

        current_armor = current.get("armor") or {}
        previous_armor = previous.get("armor") or {}
        current_break_time = current_armor.get("last_break_time")
        previous_break_time = previous_armor.get("last_break_time")
        break_edge = (
            not scene_changed
            and not player_rebound
            and isinstance(current_break_time, (int, float))
            and isinstance(previous_break_time, (int, float))
            and float(current_break_time) > float(previous_break_time) + 0.0001
        )
        if break_edge:
            level_before = previous_armor.get("current_level")
            level_after = current_armor.get("current_level")
            events.append(
                self._event(
                    "armor_break",
                    "护甲破碎",
                    (
                        f"等级 {level_before} → {level_after} · "
                        f"护甲 {float(current_armor.get('current_hp', 0)):.3g}/"
                        f"{float(current_armor.get('max_hp', 0)):.3g}"
                    ),
                    "danger",
                    {
                        "level_before": level_before,
                        "level_after": level_after,
                        "armor_hp": current_armor.get("current_hp"),
                        "armor_max_hp": current_armor.get("max_hp"),
                        "last_break_time": current_break_time,
                        "action": "armor_break",
                    },
                    now,
                )
            )

        direction = current.get("direction_time_scale")
        previous_direction = previous.get("direction_time_scale")
        if isinstance(direction, (int, float)) and isinstance(previous_direction, (int, float)) and float(direction) < 0.2 <= float(previous_direction):
            events.append(self._event("hit_stop", "检测到打击停顿", f"direction time scale {float(direction):.3g}", "warning", now=now))

        story = current.get("story") or {}
        previous_story = previous.get("story") or {}
        signature = (story.get("line_index"), story.get("speaker"), story.get("stripped_message") or story.get("message"))
        old_signature = (previous_story.get("line_index"), previous_story.get("speaker"), previous_story.get("stripped_message") or previous_story.get("message"))
        if signature != old_signature and any(signature):
            message = str(signature[2] or "")
            events.append(self._event("story", f"剧情行 {story.get('line_index', '—')} · {story.get('speaker') or '旁白'}", message[:100], "story", now=now))

        events.extend(self._flush_damage(now))
        self.previous = current
        return events
