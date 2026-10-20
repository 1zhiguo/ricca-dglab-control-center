"""Local, read-only dashboard for Holy Knight Ricca telemetry.

The server binds to localhost, samples the existing memory probe and exposes a
small JSON API to the bundled dashboard. It never writes to the game process or
to a DGLab device.
"""

from __future__ import annotations

import argparse
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from typing import Any
from urllib.parse import urlparse
import webbrowser

from ricca_hp_smoke_test import ProbeError, read_state


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "dashboard"
POLL_INTERVAL = 0.10
DAMAGE_WINDOW = 0.30

ACTION_LABELS = {
    "stand_damage": "受击",
    "stand_damage_small": "轻击硬直",
    "damage": "空中受击",
    "damage_drilling": "连续受击",
    "air_wall_blowOff": "撞墙反弹",
    "stand_landing_blowOff": "重击倒地",
    "stand_landing_blowOff_back": "背向倒地",
    "stand_guard_start": "开始防御",
    "stand_guard_hit": "防御命中",
}


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


class TelemetryMonitor:
    def __init__(self, interval: float = POLL_INTERVAL):
        self.interval = interval
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.state: dict[str, Any] = {
            "status": "waiting",
            "connected": False,
            "message": "等待 HolyKnightRicca.exe",
        }
        self.events: deque[dict[str, Any]] = deque(maxlen=240)
        self.history: deque[dict[str, Any]] = deque(maxlen=360)
        self.previous: dict[str, Any] | None = None
        self.pending_damage: dict[str, Any] | None = None
        self.sequence = 0
        self.event_sequence = 0
        self.sample_count = 0
        self.last_latency_ms = 0.0
        self.last_success_at: str | None = None
        self.last_error = ""
        self.started_at = time.time()
        self.last_sample_clock: float | None = None
        self.measured_hz = 0.0

    def start(self) -> None:
        self.thread = threading.Thread(
            target=self._run, name="ricca-memory-monitor", daemon=True
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def _emit(
        self,
        kind: str,
        title: str,
        detail: str = "",
        severity: str = "info",
        data: dict[str, Any] | None = None,
    ) -> None:
        self.event_sequence += 1
        self.events.appendleft(
            {
                "id": self.event_sequence,
                "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                "kind": kind,
                "title": title,
                "detail": detail,
                "severity": severity,
                "data": data or {},
            }
        )

    def _flush_damage(self, now: float) -> None:
        pending = self.pending_damage
        if not pending or now - pending["last"] < DAMAGE_WINDOW:
            return
        maximum = pending["max_hp"]
        ratio = pending["total"] / maximum if maximum > 0 else 0.0
        self._emit(
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
        )
        self.pending_damage = None

    def _process(self, current: dict[str, Any], now: float) -> None:
        previous = self.previous
        if previous is None:
            self._emit("attach", "已连接游戏", f"PID {current.get('process_id', '—')}", "success")
        else:
            if current.get("scene") != previous.get("scene"):
                self._emit(
                    "scene",
                    "场景控制器切换",
                    f"{previous.get('scene', '—')} → {current.get('scene', '—')}",
                    "accent",
                )

            if current.get("player_address") != previous.get("player_address"):
                self._emit(
                    "rebind",
                    "玩家对象重新绑定",
                    f"{previous.get('player_address', '—')} → {current.get('player_address', '—')}",
                    "warning",
                )

            if current.get("is_paused") != previous.get("is_paused"):
                paused = bool(current.get("is_paused"))
                self._emit(
                    "pause",
                    "游戏已暂停" if paused else "游戏已恢复",
                    f"pause mask {current.get('pause_mask', 0)}",
                    "warning" if paused else "success",
                )

            current_hp = _number(current.get("current_hp"))
            previous_hp = _number(previous.get("current_hp"))
            maximum = _number(current.get("max_hp")) or 0.0
            if current_hp is not None and previous_hp is not None:
                delta = current_hp - previous_hp
                if delta < -0.0001:
                    amount = -delta
                    if self.pending_damage and now - self.pending_damage["last"] <= DAMAGE_WINDOW:
                        self.pending_damage["total"] += amount
                        self.pending_damage["after"] = current_hp
                        self.pending_damage["last"] = now
                    else:
                        if self.pending_damage:
                            self.pending_damage["last"] = now - DAMAGE_WINDOW
                            self._flush_damage(now)
                        self.pending_damage = {
                            "started": now,
                            "last": now,
                            "total": amount,
                            "before": previous_hp,
                            "after": current_hp,
                            "max_hp": maximum,
                        }
                elif delta > 0.0001:
                    self._emit(
                        "heal",
                        f"生命恢复 +{delta:.3g} HP",
                        f"{previous_hp:.3g} → {current_hp:.3g}",
                        "success",
                    )

            trigger = current.get("action_trigger_name")
            previous_trigger = previous.get("action_trigger_name")
            trigger_edge = (
                trigger != previous_trigger
                or current.get("action_trigger_enabled")
                != previous.get("action_trigger_enabled")
            )
            if trigger_edge and trigger in ACTION_LABELS:
                self._emit(
                    "action",
                    ACTION_LABELS[str(trigger)],
                    f"{trigger} · {current.get('action_trigger_hash', '—')}",
                    "accent" if "guard" not in str(trigger) else "success",
                )

            direction = _number(current.get("direction_time_scale"))
            previous_direction = _number(previous.get("direction_time_scale"))
            if (
                direction is not None
                and previous_direction is not None
                and direction < 0.2 <= previous_direction
            ):
                self._emit(
                    "hit_stop",
                    "检测到打击停顿",
                    f"direction time scale {direction:.3g}",
                    "warning",
                )

            story = current.get("story") or {}
            previous_story = previous.get("story") or {}
            story_signature = (
                story.get("line_index"),
                story.get("speaker"),
                story.get("stripped_message") or story.get("message"),
            )
            previous_story_signature = (
                previous_story.get("line_index"),
                previous_story.get("speaker"),
                previous_story.get("stripped_message") or previous_story.get("message"),
            )
            if story_signature != previous_story_signature and any(story_signature):
                message = story_signature[2] or ""
                if len(message) > 82:
                    message = message[:79] + "…"
                self._emit(
                    "story",
                    f"剧情行 {story.get('line_index', '—')} · {story.get('speaker') or '旁白'}",
                    message,
                    "story",
                )

        self._flush_damage(now)
        self.previous = current

    def _run(self) -> None:
        while not self.stop_event.is_set():
            loop_started = time.monotonic()
            try:
                state = read_state()
                finished = time.monotonic()
                state["connected"] = True
                state["sampled_at"] = datetime.now().astimezone().isoformat(
                    timespec="milliseconds"
                )
                self.last_latency_ms = (finished - loop_started) * 1000
                if self.last_sample_clock is not None:
                    elapsed = finished - self.last_sample_clock
                    if elapsed > 0:
                        instant_hz = 1.0 / elapsed
                        self.measured_hz = (
                            instant_hz
                            if self.measured_hz == 0
                            else self.measured_hz * 0.85 + instant_hz * 0.15
                        )
                self.last_sample_clock = finished
                self.sample_count += 1
                self.last_success_at = state["sampled_at"]
                self.last_error = ""
                with self.lock:
                    self.sequence += 1
                    self._process(state, finished)
                    self.state = state
                    self.history.append(
                        {
                            "t": round(time.time() * 1000),
                            "hp": state.get("current_hp"),
                            "max_hp": state.get("max_hp"),
                            "boss_hp": state.get("boss_current_hp"),
                            "boss_max_hp": state.get("boss_max_hp"),
                            "direction_time_scale": state.get("direction_time_scale"),
                        }
                    )
            except (ProbeError, OSError, ValueError) as error:
                message = str(error)
                with self.lock:
                    was_connected = bool(self.state.get("connected"))
                    self.sequence += 1
                    self.state = {
                        "status": "waiting",
                        "connected": False,
                        "message": message,
                        "sampled_at": datetime.now().astimezone().isoformat(
                            timespec="milliseconds"
                        ),
                    }
                    self.last_error = message
                    self._flush_damage(time.monotonic())
                    if was_connected:
                        self._emit("detach", "游戏连接已断开", message, "danger")
                    self.previous = None
            spent = time.monotonic() - loop_started
            self.stop_event.wait(max(0.01, self.interval - spent))

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "sequence": self.sequence,
                "state": self.state,
                "events": list(self.events),
                "history": list(self.history),
                "meta": {
                    "read_only": True,
                    "sample_count": self.sample_count,
                    "poll_hz": round(self.measured_hz, 2),
                    "read_latency_ms": round(self.last_latency_ms, 2),
                    "last_success_at": self.last_success_at,
                    "last_error": self.last_error,
                    "uptime_seconds": round(time.time() - self.started_at),
                    "damage_window_ms": round(DAMAGE_WINDOW * 1000),
                },
            }


class DashboardHandler(BaseHTTPRequestHandler):
    monitor: TelemetryMonitor

    def log_message(self, format: str, *args: object) -> None:
        return

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'",
        )
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        path = urlparse(self.path).path
        if path == "/api/snapshot":
            payload = json.dumps(
                self.monitor.snapshot(), ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            self._headers(200, "application/json; charset=utf-8", len(payload))
            self.wfile.write(payload)
            return

        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
        }
        item = files.get(path)
        if not item:
            payload = b"Not found"
            self._headers(404, "text/plain; charset=utf-8", len(payload))
            self.wfile.write(payload)
            return
        filename, content_type = item
        try:
            payload = (WEB_ROOT / filename).read_bytes()
        except OSError:
            payload = b"Dashboard asset missing"
            self._headers(500, "text/plain; charset=utf-8", len(payload))
            self.wfile.write(payload)
            return
        self._headers(200, content_type, len(payload))
        self.wfile.write(payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--interval", type=float, default=POLL_INTERVAL)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("For safety this dashboard only binds to localhost")
    if args.interval < 0.05:
        raise SystemExit("--interval must be at least 0.05 seconds")

    monitor = TelemetryMonitor(args.interval)
    DashboardHandler.monitor = monitor
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    monitor.start()
    url = f"http://{args.host}:{args.port}/"
    print(f"Ricca Memory Dashboard: {url}", flush=True)
    print("READ-ONLY: game memory and DGLab output are not modified", flush=True)
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        monitor.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
