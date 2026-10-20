"""Qt-facing application state and background telemetry workers."""

from __future__ import annotations

import base64
from collections import deque
import ctypes
from copy import deepcopy
from ctypes import wintypes
from datetime import datetime
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import queue
import re
import threading
import time
from typing import Any, Callable

import qrcode
from . import audit
from .localization import LANGUAGES, translate
from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication

from . import __version__
from .audio_pulse import (
    AudioCaptureWorker,
    AudioPulseMapper,
    audio_backend_available,
    enumerate_audio_devices,
)
from .dglab_bridge import DGLabBridge
from .events import EventDetector
from .capture import capture_state
from .defeat_scene import DefeatSceneSession, DeathPenalty, scene_root
from .network import port_listeners
from .mapping import RiccaMappingEngine
from .models import RuntimeMode, SafetyDecision
from .product_config import (
    DEFAULT_EVENT_RULES,
    default_channel_policies,
    ProductConfig,
    read_custom_waveforms,
    save_custom_waveform,
    settings_path,
    waveform_library_dir,
    sanitize_channel_policies,
)
from .safety import SafetyGovernor, SUPPORTED_GAMEASSEMBLY_SHA256, is_story_scene, game_is_paused
from .scene_library import SceneLibrary, valid_scene_id
from .scene_catalog import COLLECTED_SCENE_IDS
from .story_queue import StoryQueuePlayer, sanitize_steps, MAX_STEPS
from .product_config import story_mode
from .waveforms import custom_frames, frames_for, waveform_catalog


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _qr_data_url(value: str) -> str:
    if not value:
        return ""
    image = qrcode.make(value)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


class BuildVerifier:
    """Resolve the running executable and hash GameAssembly.dll once per PID."""

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    def __init__(self) -> None:
        self._cache: dict[int, tuple[bool, str, str]] = {}
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
        ]
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    def clear(self) -> None:
        self._cache.clear()

    def verify(self, process_id: int) -> tuple[bool, str, str]:
        if process_id in self._cache:
            return self._cache[process_id]
        handle = self._kernel32.OpenProcess(self.PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
        if not handle:
            result = (False, "", "无法解析游戏路径")
            self._cache[process_id] = result
            return result
        try:
            capacity = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(capacity.value)
            if not self._kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(capacity)):
                result = (False, "", "无法解析游戏路径")
                self._cache[process_id] = result
                return result
            assembly = Path(buffer.value).with_name("GameAssembly.dll")
            digest = hashlib.sha256()
            with assembly.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            sha256 = digest.hexdigest().upper()
            supported = sha256 == SUPPORTED_GAMEASSEMBLY_SHA256
            result = (supported, sha256, str(assembly))
            self._cache[process_id] = result
            return result
        except OSError as error:
            result = (False, "", f"版本校验失败：{error}")
            self._cache[process_id] = result
            return result
        finally:
            self._kernel32.CloseHandle(handle)


class TelemetryWorker(threading.Thread):
    def __init__(self, outbox: queue.Queue, reader: Callable[[], dict[str, Any]],
                 stop_event: threading.Event, interval: float = 0.075,
                 verify_build: bool = True) -> None:
        super().__init__(name="RiccaTelemetryReader", daemon=True)
        self.outbox = outbox
        self.reader = reader
        self.stop_event = stop_event
        self.interval = interval
        self.verifier = BuildVerifier() if verify_build else None

    def run(self) -> None:
        last_error = ""
        last_error_sent = 0.0
        while not self.stop_event.is_set():
            started = time.perf_counter()
            try:
                state = self.reader()
                process_id = _i(state.get("process_id"))
                if process_id and self.verifier is not None:
                    supported, sha256, source = self.verifier.verify(process_id)
                    state["build_supported"] = supported
                    state["gameassembly_sha256"] = sha256
                    state["gameassembly_path"] = source
                elapsed = (time.perf_counter() - started) * 1000.0
                self.outbox.put(("telemetry", {"state": state, "latency_ms": elapsed,
                                                "received_at": time.monotonic()}))
                last_error = ""
            except Exception as error:  # the probe exposes a user-readable error
                now = time.monotonic()
                message = str(error)
                if message != last_error or now - last_error_sent >= 1.0:
                    self.outbox.put(("telemetry_error", {"detail": message, "received_at": now}))
                    last_error, last_error_sent = message, now
            elapsed_seconds = time.perf_counter() - started
            self.stop_event.wait(max(0.01, self.interval - elapsed_seconds))


class DemoReader:
    """Deterministic native-UI demo; never talks to a game process."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self.frame = 0

    def __call__(self) -> dict[str, Any]:
        self.frame += 1
        elapsed = time.monotonic() - self.started
        hp = 840.0 if elapsed < 4.0 else 692.0
        action = "stand_damage" if 4.0 <= elapsed < 4.8 else "stand_idle"
        return {
            "status": "ok", "connected": True, "build_supported": True,
            "build": "Holy Knight Ricca English 1.4.1", "process_id": 23140,
            "scene": "gameplay", "controller_type": 1, "is_paused": False,
            "pause_mask": 0, "player_address": "0x1E76A884C00",
            "current_hp": hp, "max_hp": 1000.0, "hp_ratio": hp / 1000.0,
            "current_magic": 72.0, "max_magic": 100.0, "defence": 18.0,
            "character_state_name": "Ground", "action_trigger_name": action,
            "action_trigger_hash": 137828819, "action_trigger_enabled": True,
            "action_time": elapsed % 1.0, "direction_time_scale": 1.0,
            "master_time_scale": 1.0,
            "stage": {"system_name": "Chapter23", "current_scene_index": 3,
                      "all_resource_loaded": True, "scene_change_playing": False,
                      "is_game_over": False},
            "game_ui": {"is_user_pause": False},
            "boss_battling": True, "boss_count": 1,
            "boss": {"current_hp": 14720.0, "max_hp": 20000.0,
                     "hp_ratio": .736, "character_state_name": "Ground",
                     "action_trigger_name": "boss_attack", "action_trigger_hash": -9211},
            "story": {}, "telemetry_errors": [],
            "update_frame_count": self.frame, "fixed_update_frame_count": self.frame,
            "module_base": "0x7FF9C1200000", "act_class_address": "0x7FF9D2345678",
            "static_fields_address": "0x1E761000000",
        }


class AppBackend(QObject):
    languageChanged = Signal()
    changed = Signal()
    eventsChanged = Signal()
    rawJsonChanged = Signal()
    sceneLibraryChanged = Signal()
    toastRequested = Signal(str, str)

    def __init__(self, reader: Callable[[], dict[str, Any]], *, demo: bool = False,
                 start_bridge: bool = True) -> None:
        super().__init__()
        self._demo = demo
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._worker = TelemetryWorker(self._queue, reader, self._stop, verify_build=not demo)
        self._bridge = DGLabBridge(self._queue)
        self._safety = SafetyGovernor()
        self._detector = EventDetector()
        self._defeat_scene = DefeatSceneSession()
        self._death_penalty = DeathPenalty()
        self._stop_latched = False
        self._priority_output_active = False
        self._priority_kind = ""
        self._config = ProductConfig()
        self._scene_library = SceneLibrary(self._config.path.parent / "scenes.json")
        self._scene_capture_enabled = False
        self._last_scene_capture = None
        self._story_queue_player = StoryQueuePlayer()
        self._story_queue_status = {}
        self._story_queue_tokens = {"A": "", "B": ""}
        self._last_queue_audit = {}
        self._last_scene_asset = ""
        self._last_output_audit = None
        self._last_output_audit_at = 0.0
        audit.record("config.loaded", path=str(self._config.path),
                     scene_catalog_count=len(self._config.values["scene_catalog"]),
                     scene_catalog=self._config.values["scene_catalog"],
                     migration=getattr(self._config, "migration_info", {}),
                     hard_cap=self._config.values["hard_cap"],
                     strengths=self._strength_settings(),
                     onboarding_completed=self._config.values["onboarding_completed"])
        self._game_path_status = "自动检测 HolyKnightRicca.exe"
        self._hotkey_service = None
        self._hotkey_status = "全局快捷键未注册"
        self._game_path_hash = ""
        self._game_path_supported = False
        self._configure_probe_path()
        self._inspect_game_path()
        self._custom_waveforms = read_custom_waveforms()
        config = self._config.values
        self._mapping = RiccaMappingEngine(
            hard_cap=config["hard_cap"],
            strengths=self._strength_settings(),
            event_rules=config["event_rules"],
            channel_policies=config["channel_policies"],
        )
        self._state: dict[str, Any] = {}
        self._decision = SafetyDecision(RuntimeMode.DISCONNECTED, False, False, "starting")
        self._events: deque[dict[str, Any]] = deque(maxlen=160)
        self._raw_json = "{}"
        self._reader_error = ""
        self._last_received = 0.0
        self._sample_times: deque[float] = deque(maxlen=60)
        self._latency_ms = 0.0
        self._server_ready = False
        self._server_error = ""
        self._connection_diagnostics = ""
        self._start_bridge_enabled = start_bridge
        self._device_connected = False
        self._lan_ip = self._bridge.lan_ip
        self._lan_addresses = list(self._bridge.available_lan_ips) or ["127.0.0.1"]
        self._qr_url = ""
        self._qr_source = ""
        self._bridge_status = "正在启动 Socket 服务" if start_bridge else "演示模式"
        self._preview_a = 0.0
        self._preview_b = 0.0
        self._wave_a = "idle"
        self._wave_b = "idle"
        # Device eligibility is session-only; ordinary pause and critical stop
        # are distinct because a bounded death cue outranks ordinary pause.
        self._output_armed = False
        self._onboarding_active = False
        self._user_output_paused = False
        self._pause_active = False
        self._audio_resume_after = 0.0
        self._tested_channels: set[str] = set()
        self._manual_test_channel = ""
        self._audio_devices: list[dict[str, Any]] = enumerate_audio_devices()
        self._audio_worker: AudioCaptureWorker | None = None
        self._audio_stop = threading.Event()
        self._audio_mapper = AudioPulseMapper()
        self._audio_status = "音频共感已关闭"
        self._audio_level = 0.0
        self._audio_peak = 0.0
        self._audio_dbfs = -60.0
        self._audio_strength = 0.0
        self._audio_points = [0] * 16
        self._audio_last_sample = 0.0
        self._closed = False
        self._onboarding_error = ""
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._drain)
        self._timer.start()
        self._worker.start()
        if start_bridge:
            self._bridge.start()
        self._restart_audio_capture()

    def _get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def _strength_settings(self) -> dict[str, int]:
        values = self._config.values
        return {
            "low": _i(values.get("strength_low"), 5),
            "medium": _i(values.get("strength_medium"), 15),
            "high": _i(values.get("strength_high"), 25),
            "death": _i(values.get("strength_death"), 25),
        }

    def _refresh_mapping_config(self) -> None:
        values = self._config.values
        self._mapping.configure(
            hard_cap=_i(values.get("hard_cap"), 30),
            strengths=self._strength_settings(),
            event_rules=values.get("event_rules") or {},
            channel_policies=values.get("channel_policies"),
        )

    @Property("QVariantMap", notify=changed)
    def channelPolicies(self) -> dict:
        return self._config.values["channel_policies"]

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._config.values.get("language", "zh")

    @Property(str, notify=languageChanged)
    def uiFontFamily(self) -> str:
        return {"zh":"Microsoft YaHei UI", "en":"Segoe UI", "ja":"Yu Gothic UI"}[self.language]

    @Slot(str, str, result=str)
    def localize(self, source: str, language: str) -> str:
        return translate(source, language)

    @Slot(str, result=bool)
    def setLanguage(self, language: str) -> bool:
        if not isinstance(language, str) or language not in LANGUAGES:
            return False
        if language == self.language:
            return True
        try:
            self._config.update({"language": language})
        except OSError as error:
            self.toastRequested.emit("保存失败", str(error))
            return False
        # No mapping refresh/disarm, audio restart, or pulse timer changes.
        self.languageChanged.emit()
        self.toastRequested.emit("保存成功", "界面语言已保存")
        return True

    @Property("QVariantMap", notify=changed)
    def storyQueues(self) -> dict:
        return self._config.values["story_queues"]

    @Property("QVariantMap", notify=changed)
    def storyQueueStatus(self) -> dict:
        return self._story_queue_status

    @Slot(str, "QVariantList", bool, result=bool)
    def saveStoryQueue(self, channel: str, steps: list, use_queue: bool) -> bool:
        if channel not in {"A", "B"} or not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
            self.toastRequested.emit("保存失败", "队列须包含 1–16 段。")
            return False
        clean = sanitize_steps(steps)
        waves = {entry["key"] for entry in self._wave_catalog()} | {"idle"}
        if len(clean) != len(steps) or any(step["wave"] not in waves for step in clean):
            self.toastRequested.emit("保存失败", "队列包含无效或缺失的波形。")
            return False
        queues, policies = deepcopy(self.storyQueues), deepcopy(self.channelPolicies)
        queues[channel] = clean
        policies[channel]["rules"]["defeat_interaction"]["playback"] = "queue" if use_queue else "wave"
        if "story_mode" in policies[channel]:
            audio = story_mode(policies[channel]) in {"audio", "fixed_audio", "queue_audio"}
            policies[channel]["story_mode"] = ("queue" if use_queue else "fixed") + ("_audio" if audio else "")
        try:
            self._config.update({"story_queues": queues, "channel_policies": policies})
        except OSError as error:
            self.toastRequested.emit("保存失败", str(error))
            return False
        self._story_queue_player.reset(channel)
        self._story_queue_tokens[channel] = ""
        self._refresh_mapping_config()
        self.changed.emit()
        audit.record("story.queue_saved", channel=channel, count=len(clean), use_queue=use_queue)
        self.toastRequested.emit("保存成功", channel + " 队列已保存并应用；段落从头计时，强度上限与暂停状态不变。")
        return True

    @Property(str, notify=changed)
    def currentSceneId(self) -> str:
        if (not self.telemetryOnline or self._reader_error or self._state.get("status") != "ok"
                or self._state.get("build_supported") is not True
                or self._state.get("scene") not in {"adv", "atd", "anv"}):
            return ""
        return scene_root((self._state.get("story") or {}).get("asset_name"))

    @Property("QVariantList", notify=sceneLibraryChanged)
    def sceneLibrary(self) -> list:
        return self._scene_library.rows(self._config.values["scene_catalog"])

    @Property(int, notify=sceneLibraryChanged)
    def registeredSceneCount(self) -> int:
        return len(self._config.values["scene_catalog"])

    @Slot(result=bool)
    def registerCollectedScenes(self) -> bool:
        """Explicit in-process registration preserves the running user's profile."""
        catalog = sorted(set(self._config.values["scene_catalog"]) | set(COLLECTED_SCENE_IDS))
        try:
            self._config.update({"scene_catalog": catalog})
        except OSError as error:
            self.toastRequested.emit("登记失败", str(error))
            return False
        audit.record("scene.batch_registered", source="in-process-confirmation",
                     count=len(catalog), scene_catalog=catalog,
                     path=str(self._config.path))
        self.sceneLibraryChanged.emit()
        self.changed.emit()
        self.toastRequested.emit("保存成功", "34 个已收集场景已登记；白名单共 " + str(len(catalog))
                                 + " 个。当前场景将在有效采样后自动匹配；强度、波形和暂停状态保持不变。")
        return True

    @Property(str, constant=True)
    def sceneLibraryPath(self) -> str:
        return str(self._scene_library.path)

    @Property(bool, notify=sceneLibraryChanged)
    def sceneCaptureEnabled(self) -> bool:
        return self._scene_capture_enabled

    @Slot(bool)
    def setSceneCaptureEnabled(self, enabled: bool) -> None:
        self._scene_capture_enabled = bool(enabled)
        self._last_scene_capture = None
        self.sceneLibraryChanged.emit()
        self.toastRequested.emit("自动记录已开启" if enabled else "自动记录已关闭",
                                 "仅记录遇到的场景，不自动启用循环；此开关仅本次运行有效。")

    @Slot(result=bool)
    def recordCurrentScene(self) -> bool:
        if not self.currentSceneId:
            self.toastRequested.emit("无法记录", "请先进入有效剧情；选择框、主菜单或读取失效时不记录。")
            return False
        try:
            root = self._scene_library.record(self._state)
        except (OSError, ValueError) as error:
            self.toastRequested.emit("记录失败", str(error))
            return False
        self.sceneLibraryChanged.emit()
        audit.record("scene.recorded", scene_root=root, source="manual", output_enabled=root in self._config.values["scene_catalog"])
        self.toastRequested.emit("保存成功", root + " 已记录；不会因此自动启用输出。")
        return True

    @Slot(str, str, result=bool)
    def saveSceneNote(self, root: str, note: str) -> bool:
        try:
            self._scene_library.save_note(root, note)
        except (OSError, ValueError) as error:
            self.toastRequested.emit("保存失败", str(error))
            return False
        self.sceneLibraryChanged.emit()
        self.toastRequested.emit("保存成功", "场景备注已保存。")
        return True

    @Slot(str, bool, result=bool)
    def setSceneLoopEnabled(self, root: str, enabled: bool) -> bool:
        if not valid_scene_id(root) or root not in self._scene_library.entries:
            self.toastRequested.emit("无法启用", "请先记录并核对这个场景。")
            return False
        catalog = list(self._config.values["scene_catalog"])
        if enabled and root not in catalog:
            catalog.append(root)
        elif not enabled:
            catalog = [key for key in catalog if key != root]
        try:
            self._config.update({"scene_catalog": catalog})
        except OSError as error:
            self.toastRequested.emit("保存失败", str(error))
            return False
        if not enabled and self._defeat_scene.root == root:
            self._defeat_scene.reset()
        self.sceneLibraryChanged.emit()
        self.changed.emit()
        audit.record("scene.loop_setting", scene_root=root, enabled=enabled)
        self.toastRequested.emit("保存成功", root + (" 已启用循环，遵循当前通道策略与暂停状态。" if enabled else " 已停用循环。"))
        return True

    @Slot()
    def openSceneLibraryFolder(self) -> None:
        self._scene_library.path.parent.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._scene_library.path.parent)))

    @Property(bool, notify=changed)
    def gameHudEnabled(self) -> bool:
        return bool(self._config.values.get("game_hud_enabled", True))

    @Slot(bool, result=bool)
    def setGameHudEnabled(self, enabled: bool) -> bool:
        try:
            self._config.update({"game_hud_enabled": bool(enabled)})
        except OSError as error:
            self._append_system_event("HUD 设置保存失败", str(error), "danger")
            return False
        self.toastRequested.emit("保存成功", "HUD 设置已保存并应用。")
        self.changed.emit()
        return True

    @Slot(str, result=str)
    def channelModeName(self, channel: str) -> str:
        mode = self.channelPolicies.get(channel, {}).get("mode", "off")
        return {"hp": "HP 伤害", "action": "动作反馈", "both": "HP + 动作", "none": "不接收战斗事件", "audio": "剧情音频（旧包络）", "action_audio": "战斗动作 / 剧情音频队列", "off": "关闭"}.get(mode, "关闭")

    @Slot(str, "QVariantMap", result=bool)
    def saveChannelPolicy(self, channel: str, policy: dict) -> bool:
        if channel not in {"A", "B"}:
            return False
        incoming = {**self.channelPolicies, channel: policy}
        clean = sanitize_channel_policies(incoming)
        if ("story_mode" not in policy and clean[channel]["mode"] == "action_audio"
                and self.channelPolicies[channel]["mode"] != "action_audio"):
            clean[channel]["rules"]["defeat_interaction"]["playback"] = "queue"
        available = {item["key"] for item in self._wave_catalog()}
        if any(rule["wave"] not in available for rule in clean[channel]["rules"].values()):
            self._append_system_event("通道策略未保存", "策略中有已删除或不可用的波形", "danger")
            return False
        self._disarm_output(f"{channel} 通道策略已修改，清空旧事件后自动应用", log=True)
        try:
            self._config.update({"channel_policies": clean})
        except OSError as error:
            self._append_system_event("通道策略保存失败", str(error), "danger")
            return False
        self._refresh_mapping_config()
        self._append_system_event(f"{channel} 通道策略已保存", self.channelModeName(channel), "success")
        self.changed.emit()
        return True

    def _wave_catalog(self) -> list[dict[str, Any]]:
        # QML reads this through many bindings on every UI notification. Frame
        # decoding/frequency calculation is static until the custom library
        # changes; do not rebuild hundreds of frame values on the output loop.
        if (getattr(self, "_wave_catalog_cache", None) is None
                or self._custom_waveforms != self._wave_catalog_custom):
            self._wave_catalog_cache = waveform_catalog(self._custom_waveforms)
            self._wave_catalog_custom = deepcopy(self._custom_waveforms)
        return self._wave_catalog_cache

    def _configure_probe_path(self) -> None:
        """Keep the low-level reader on automatic or exact-path process matching."""
        if self._demo:
            return
        try:
            from ricca_hp_smoke_test import configure_preferred_executable
        except ImportError:
            return
        configure_preferred_executable(
            str(self._config.values.get("game_executable_path") or "")
        )

    def _inspect_game_path(self) -> None:
        """Validate a manually selected Unity executable without starting it."""
        selected = str(self._config.values.get("game_executable_path") or "")
        self._game_path_hash = ""
        self._game_path_supported = False
        if not selected:
            self._game_path_status = "自动检测 HolyKnightRicca.exe"
            return
        executable = Path(selected)
        if not executable.is_file():
            self._game_path_status = "所选游戏 EXE 不存在"
            return
        assembly = executable.with_name("GameAssembly.dll")
        if not assembly.is_file():
            self._game_path_status = "同目录未找到 GameAssembly.dll"
            return
        try:
            digest = hashlib.sha256()
            with assembly.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            self._game_path_hash = digest.hexdigest().upper()
            self._game_path_supported = (
                self._game_path_hash == SUPPORTED_GAMEASSEMBLY_SHA256
            )
            self._game_path_status = (
                "手动路径已验证 · 支持此版本"
                if self._game_path_supported
                else "手动路径已保存 · 游戏版本未适配"
            )
        except OSError as error:
            self._game_path_status = f"无法读取 GameAssembly.dll：{error}"

    @Property(str, constant=True)
    def version(self) -> str:
        return __version__

    @Property(bool, constant=True)
    def dryRun(self) -> bool:
        return False

    @Property(bool, notify=changed)
    def outputArmed(self) -> bool:
        return self._output_armed or self._priority_output_active

    @Property(str, notify=changed)
    def priorityOutputStatus(self) -> str:
        return self._priority_kind if self._priority_output_active else ""

    @Property(bool, notify=changed)
    def canRunDeviceTest(self) -> bool:
        return bool(self._device_connected and not self._manual_test_channel
                    and self.onboardingCompleted and self.hardCap > 0
                    and not self._user_output_paused and not game_is_paused(self._state))

    @Property(bool, notify=changed)
    def deviceTestsComplete(self) -> bool:
        return self._tested_channels == {"A", "B"}

    @Property(str, notify=changed)
    def testedChannels(self) -> str:
        if not self._tested_channels:
            return "尚未测试"
        return " / ".join(sorted(self._tested_channels)) + " 已通过"

    @Property(bool, notify=changed)
    def canArmOutput(self) -> bool:
        return bool(
            not self._demo
            and self.onboardingCompleted and self.hardCap > 0
            and not self._user_output_paused
            and self._device_connected
            and self.telemetryOnline
            and bool(self._get("build_supported"))
            and (self._decision.allow_gameplay_output or self._decision.allow_story_output)
            and not self._manual_test_channel
            and not self._onboarding_active
            and not self._reader_error
        )

    @Property(str, notify=changed)
    def outputStatus(self) -> str:
        if not self.onboardingCompleted or self._onboarding_active:
            return "请先完成新手教程并手动保存安全硬上限"
        if self.hardCap == 0:
            return "安全硬上限为 0 · 所有设备输出已禁用"
        if self._priority_output_active:
            return f"{self._priority_kind} · 优先输出 · 硬上限 {self.hardCap} · 紧急归零可立即停止"
        if self._user_output_paused:
            return "输出已手动暂停 · A/B 归零，恢复后按当前游戏状态运行"
        if self._device_connected and (not self.telemetryOnline or self._reader_error):
            return "等待有效游戏遥测 · A/B 归零"
        if self._output_armed:
            if game_is_paused(self._state):
                return "游戏已暂停 · A/B 归零，取消游戏暂停后自动恢复通道"
            if self._decision.allow_gameplay_output or self._decision.allow_story_output:
                return f"实时输出已启用 · 硬上限 {self.hardCap}"
            return "实时输出已启用 · 当前被安全门归零"
        if not self._device_connected:
            return "等待 DG-LAB 设备连接"
        if self._manual_test_channel:
            return f"正在测试 {self._manual_test_channel} 通道 · 强度 {min(5, self.hardCap)}"
        if not self.telemetryOnline:
            return "等待游戏遥测"
        if not bool(self._get("build_supported")):
            return "游戏版本未通过校验"
        if not (self._decision.allow_gameplay_output or self._decision.allow_story_output):
            return "等待 Gameplay 或 ADV 安全场景"
        return f"连接后自动输出 · 硬上限 {self.hardCap}"

    @Property(int, notify=changed)
    def lowStrength(self) -> int:
        return self._strength_settings()["low"]

    @Property(int, notify=changed)
    def mediumStrength(self) -> int:
        return self._strength_settings()["medium"]

    @Property(int, notify=changed)
    def highStrength(self) -> int:
        return self._strength_settings()["high"]

    @Property(int, notify=changed)
    def deathStrength(self) -> int:
        return self._strength_settings()["death"]

    @Property(int, notify=changed)
    def hardCap(self) -> int:
        return _i(self._config.values.get("hard_cap"), 30)

    @Property(bool, notify=changed)
    def onboardingCompleted(self) -> bool:
        return bool(self._config.values.get("onboarding_completed"))

    @Property(str, notify=changed)
    def onboardingError(self) -> str:
        return self._onboarding_error

    @Slot()
    def beginOnboarding(self) -> None:
        self._onboarding_error = ""
        self._onboarding_active = True
        self._disarm_output("新手教程已打开，完成后自动应用安全上限", log=True)
        self._bridge.emergency_stop()
        self._manual_test_channel = ""
        self.changed.emit()

    @Slot(str, result=bool)
    def completeOnboarding(self, text: str) -> bool:
        value = str(text).strip()
        if not re.fullmatch(r"[0-9]{1,3}", value) or not 0 <= int(value) <= 100:
            self._onboarding_error = "请手动输入 0–100 的整数安全硬上限。"
            self.changed.emit()
            return False
        cap = int(value)
        self._disarm_output("安全硬上限已修改，清空旧事件后自动应用", log=True)
        self._bridge.emergency_stop()
        self._manual_test_channel = ""
        self._tested_channels.clear()
        previous = deepcopy(self._config.values)
        try:
            self._config.update({"hard_cap": cap, "onboarding_completed": True})
        except OSError as error:
            self._config.values = previous
            self._onboarding_error = f"保存失败，未完成教程：{error}"
            self.changed.emit()
            return False
        self._onboarding_error = ""
        self._onboarding_active = False
        self._refresh_mapping_config()
        self._audio_strength = self._audio_last_sample = 0.0
        self._audio_mapper = AudioPulseMapper()
        self._preview_a = self._preview_b = 0.0
        self._wave_a = self._wave_b = "idle"
        self._append_system_event("新手教程已完成", f"安全硬上限 {cap} 已保存并应用；连接后按当前游戏状态自动输出", "success")
        self.changed.emit()
        return True

    @Property(bool, notify=changed)
    def audioEmpathyEnabled(self) -> bool:
        return bool(self._config.values.get("audio_empathy_enabled"))

    @Property(int, notify=changed)
    def audioSensitivity(self) -> int:
        return _i(self._config.values.get("audio_sensitivity"), 55)

    @Property(int, notify=changed)
    def audioGate(self) -> int:
        return _i(self._config.values.get("audio_gate"), 12)

    @Property(float, notify=changed)
    def audioGain(self) -> float:
        return float(self._config.values.get("audio_gain", 1.0))

    @Property(int, notify=changed)
    def audioQueueMinimum(self) -> int:
        return min(self.hardCap, int(self._config.values.get("audio_queue_minimum", 0)))

    @Slot(int, result=bool)
    def saveAudioQueueMinimum(self, value: int) -> bool:
        if not 0 <= value <= self.hardCap:
            return False
        try:
            self._config.update({"audio_queue_minimum": value})
        except OSError as error:
            self.toastRequested.emit("保存失败", str(error))
            return False
        self.changed.emit()
        self.toastRequested.emit("保存成功", "音频队列最低强度已保存")
        return True

    @Slot(float, result=bool)
    def saveAudioGain(self, gain: float) -> bool:
        if not math.isfinite(gain) or not 0 <= gain <= 10:
            return False
        try:
            self._config.update({"audio_gain": round(gain, 1)})
        except OSError as error:
            self.toastRequested.emit("保存失败", str(error))
            return False
        # Only scale audio-modulated output. Do not restart capture, rewind the
        # queue, change authorization, or raise the user's saved safety cap.
        self.changed.emit()
        self.toastRequested.emit("保存成功", "音频强度增益已保存")
        return True

    @Property(str, notify=changed)
    def audioChannel(self) -> str:
        return str(self._config.values.get("audio_channel") or "B")

    @Property(bool, notify=changed)
    def audioStoryOnly(self) -> bool:
        return bool(self._config.values.get("audio_story_only", True))

    @Property(str, notify=changed)
    def audioDeviceId(self) -> str:
        configured = str(self._config.values.get("audio_device_id") or "")
        if any(item["id"] == configured for item in self._audio_devices):
            return configured
        return str(self._audio_devices[0]["id"]) if self._audio_devices else ""

    @Property("QVariantList", notify=changed)
    def audioDevices(self) -> list[dict[str, Any]]:
        return list(self._audio_devices)

    @Property(bool, notify=changed)
    def audioBackendAvailable(self) -> bool:
        return audio_backend_available()

    @Property(str, notify=changed)
    def audioCaptureStatus(self) -> str:
        return self._audio_status

    @Property(float, notify=changed)
    def audioLevel(self) -> float:
        return self._audio_level

    @Property(float, notify=changed)
    def audioPeak(self) -> float:
        return self._audio_peak

    @Property(float, notify=changed)
    def audioDbfs(self) -> float:
        return self._audio_dbfs

    @Property(float, notify=changed)
    def audioPulseStrength(self) -> float:
        hybrid = [ch for ch, policy in self.channelPolicies.items()
                  if story_mode(policy) in {"audio", "fixed_audio", "queue_audio"}]
        if hybrid and not any(p["mode"] == "audio" and "story_mode" not in p for p in self.channelPolicies.values()):
            return max((self._preview_a if ch == "A" else self._preview_b
                        for ch in hybrid if self._story_queue_status.get(ch, {}).get("playing")), default=0.0)
        if not hybrid and not any(p["mode"] == "audio" and "story_mode" not in p for p in self.channelPolicies.values()):
            return 0.0
        return (min(self.hardCap, self._audio_strength * self.audioGain * self._mapping.sensitivity_multiplier)
                if self._audio_output_allowed() else 0.0)

    @Property(bool, notify=changed)
    def audioPulseActive(self) -> bool:
        return self.audioPulseStrength > 0.0

    @Property("QVariantList", notify=changed)
    def audioPulsePoints(self) -> list[int]:
        if any(story_mode(policy) == "audio" or (policy["mode"] == "audio" and "story_mode" not in policy)
               for policy in self.channelPolicies.values()):
            return list(self._audio_points)
        for channel, policy in self.channelPolicies.items():
            if story_mode(policy) in {"fixed_audio", "queue_audio"}:
                key = self._story_queue_status.get(channel, {}).get("wave", "idle")
                return list(next((entry["points"] for entry in self._wave_catalog() if entry["key"] == key), []))
        return list(self._audio_points)

    @Property(str, notify=changed)
    def audioSceneStatus(self) -> str:
        if not self.audioEmpathyEnabled:
            return "总开关关闭"
        if not is_story_scene(self._state):
            return "战斗 / 菜单不响应音频 · 等待 ADV / ATD / ANV 剧情"
        names = {"audio": "实时音频", "fixed_audio": "固定＋音频", "queue_audio": "循环＋音频"}
        channels = [channel + " · " + names[story_mode(policy)]
                    for channel, policy in self.channelPolicies.items()
                    if policy["mode"] != "off" and story_mode(policy) in names]
        return "剧情音频 → " + " / ".join(channels) if channels else "请在通道的剧情 / 鉴赏策略选择音频模式"

    @Property(bool, notify=changed)
    def storySceneActive(self) -> bool:
        return is_story_scene(self._state)

    @Property(str, constant=True)
    def settingsPath(self) -> str:
        return str(settings_path())

    @Property(str, notify=changed)
    def gameExecutablePath(self) -> str:
        return str(self._config.values.get("game_executable_path") or "")

    @Property(bool, notify=changed)
    def manualGamePathConfigured(self) -> bool:
        return bool(self.gameExecutablePath)

    @Property(str, notify=changed)
    def gamePathStatus(self) -> str:
        return self._game_path_status

    @Property(str, notify=changed)
    def gameAssemblyHash(self) -> str:
        return self._game_path_hash

    @Property(bool, notify=changed)
    def gamePathSupported(self) -> bool:
        return self._game_path_supported

    @Property(str, notify=changed)
    def detectedGameAssemblyPath(self) -> str:
        return str(self._get("gameassembly_path") or "")

    @Property(str, constant=True)
    def waveformLibraryPath(self) -> str:
        return str(waveform_library_dir())

    @Property("QVariantList", notify=changed)
    def waveformCatalog(self) -> list[dict[str, Any]]:
        return self._wave_catalog()

    @Property("QVariantList", notify=changed)
    def eventMappings(self) -> list[dict[str, Any]]:
        wave_names = {item["key"]: item["name"] for item in self._wave_catalog()}
        result = []
        for key, rule in (self._config.values.get("event_rules") or {}).items():
            item = dict(rule)
            item.update({"key": key, "waveName": wave_names.get(rule.get("wave"), rule.get("wave", "—"))})
            result.append(item)
        return result

    @Property(bool, notify=changed)
    def telemetryOnline(self) -> bool:
        return bool(self._last_received and time.monotonic() - self._last_received < 0.5)

    @Property(str, notify=changed)
    def telemetryStatus(self) -> str:
        if self.telemetryOnline:
            return "游戏遥测在线"
        if self._reader_error:
            return "等待 Ricca 进程"
        return "正在连接游戏"

    @Property(bool, notify=changed)
    def serverReady(self) -> bool:
        return self._server_ready

    @Property(bool, notify=changed)
    def deviceConnected(self) -> bool:
        return self._device_connected

    @Property(str, notify=changed)
    def bridgeStatus(self) -> str:
        return self._bridge_status

    @Property(str, notify=changed)
    def serverError(self) -> str:
        return self._server_error

    @Property(str, notify=changed)
    def connectionDiagnostics(self) -> str:
        return self._connection_diagnostics

    @Property("QVariantList", notify=changed)
    def lanInterfaces(self) -> list[dict]:
        names = {item["address"]: item for item in self._bridge.available_lan_interfaces}
        return [names.get(address, {"address": address, "label": f"系统地址 · {address}"})
                for address in self._lan_addresses]

    @Property(str, notify=changed)
    def lanAddress(self) -> str:
        return self._lan_ip

    @Property("QVariantList", notify=changed)
    def lanAddresses(self) -> list[str]:
        return self._lan_addresses

    @Property(str, notify=changed)
    def qrSource(self) -> str:
        return self._qr_source

    @Property(str, notify=changed)
    def qrUrl(self) -> str:
        return self._qr_url

    @Property(str, notify=changed)
    def safetyMode(self) -> str:
        return self._decision.mode.value

    @Property(str, notify=changed)
    def safetyReason(self) -> str:
        return self._decision.reason

    @Property(bool, notify=changed)
    def outputPaused(self) -> bool:
        if self._priority_output_active:
            return False
        return not (
            self._output_armed
            and self.hardCap > 0
            and not self._user_output_paused
            and not self._pause_active
            and not self._reader_error
            and self._device_connected and self.telemetryOnline
            and (self._decision.allow_gameplay_output or self._decision.allow_story_output)
        )

    @Property(bool, notify=changed)
    def userOutputPaused(self) -> bool:
        return self._user_output_paused

    @Slot()
    def toggleOutputPause(self) -> None:
        self._user_output_paused = not self._user_output_paused
        if not self._user_output_paused:
            self._bridge.clear_global_emergency_stop()
            self._stop_latched = False
        elif self._priority_kind != "死亡惩罚":
            self._priority_output_active = False
        self._sync_output_pause()
        self._append_system_event("输出已暂停" if self._user_output_paused else "输出暂停已解除",
                                  "普通输出遵循暂停；死亡惩罚优先于普通暂停，紧急归零可停止全部输出", "warning")
        self.changed.emit()

    def _sync_output_pause(self) -> None:
        paused = self._user_output_paused or game_is_paused(self._state)
        self._bridge.set_paused(self._stop_latched or (paused and not self._priority_output_active))
        if paused == self._pause_active:
            return
        self._pause_active = paused
        self._mapping.clear_pulses()
        self._detector.pending_damage = None
        self._preview_a = self._preview_b = 0.0
        self._wave_a = self._wave_b = "idle"
        self._audio_strength = 0.0
        self._audio_last_sample = 0.0
        self._audio_resume_after = time.monotonic()
        self._audio_mapper = AudioPulseMapper()
        if paused and self._manual_test_channel:
            self._tested_channels.discard(self._manual_test_channel)
            self._manual_test_channel = ""

    @Property(str, notify=changed)
    def gameScene(self) -> str:
        return str(self._get("scene", "—"))

    @Property(str, notify=changed)
    def defeatSceneStatus(self) -> str:
        scene = self._defeat_scene
        if not self.telemetryOnline or self._reader_error:
            return "败北 CG · 等待遥测"
        phase = {"idle": "未进入", "waiting": "HP 归零 · 等待场景确认", "loading": "加载中",
                 "dialogue": "剧情段", "interaction": "互动循环", "stopped": "动画停止",
                 "unknown": "互动状态不可用", "unconfirmed": "未记录本次败北 · 不输出"}.get(scene.phase, scene.phase)
        if scene.catalogued:
            return "场景循环 · " + scene.root + (" · 输出已暂停" if self._user_output_paused else " · 剧情 / 回想")
        return "败北 CG · " + phase + (" · " + scene.cut if scene.root else "")

    @Property(bool, notify=changed)
    def canConfirmCurrentDefeatScene(self) -> bool:
        state, atd = self._state, self._state.get("atd") or {}
        root = scene_root((state.get("story") or {}).get("asset_name"))
        speed = atd.get("animation_speed")
        return bool(not self._demo and self._device_connected and self.telemetryOnline
                    and self.onboardingCompleted and self.hardCap > 0 and not self._onboarding_active
                    and not self._reader_error and self._defeat_story_allowed()
                    and state.get("scene") == "atd" and state.get("process_id")
                    and not self._defeat_scene.root and root and root == state.get("defeat_scene_hint")
                    and atd.get("ui_start_atd") is True and type(atd.get("playing_adv_state")) is int
                    and atd["playing_adv_state"] == 0 and type(atd.get("cut_index")) is int
                    and atd["cut_index"] >= 0 and atd.get("cut_name")
                    and type(speed) in {float, int} and math.isfinite(speed) and speed > 0)

    @Slot(result=bool)
    def confirmCurrentDefeatScene(self) -> bool:
        # This opt-in is for restarting inside a known defeat, never automatic
        # gallery detection. It deliberately cannot replay an unwitnessed death.
        if not self.canConfirmCurrentDefeatScene:
            return False
        now = time.monotonic()
        session = self._defeat_scene
        session.reset()
        session.pid = self._state["process_id"]
        session.pending_root = scene_root(self._state["story"]["asset_name"])
        session.pending_until = now + 10
        session.cancel_pulses()
        session.observe(self._state, now=now, allow_story=True, paused=False)
        self._append_system_event("已确认当前败北互动", "三次有效采样后接管循环；不补发未记录的死亡惩罚", "warning")
        self.changed.emit()
        return True

    @Property(str, notify=changed)
    def stageName(self) -> str:
        return str((self._get("stage", {}) or {}).get("system_name") or "—")

    @Property(int, notify=changed)
    def processId(self) -> int:
        return _i(self._get("process_id"))

    @Property(float, notify=changed)
    def currentHp(self) -> float:
        return _f(self._get("current_hp"))

    @Property(float, notify=changed)
    def maxHp(self) -> float:
        return _f(self._get("max_hp"))

    @Property(float, notify=changed)
    def hpRatio(self) -> float:
        maximum = self.maxHp
        return max(0.0, min(1.0, self.currentHp / maximum if maximum else 0.0))

    @Property(float, notify=changed)
    def currentMp(self) -> float:
        return _f(self._get("current_magic"))

    @Property(float, notify=changed)
    def maxMp(self) -> float:
        return _f(self._get("max_magic"))

    @Property(str, notify=changed)
    def playerState(self) -> str:
        return str(self._get("character_state_name", "—"))

    @Property(int, notify=changed)
    def armorLevel(self) -> int:
        return _i((self._get("armor", {}) or {}).get("current_level"), -1)

    @Property(int, notify=changed)
    def armorLevelCount(self) -> int:
        return _i((self._get("armor", {}) or {}).get("level_count"))

    @Property(float, notify=changed)
    def armorHp(self) -> float:
        return _f((self._get("armor", {}) or {}).get("current_hp"))

    @Property(float, notify=changed)
    def armorMaxHp(self) -> float:
        return _f((self._get("armor", {}) or {}).get("max_hp"))

    @Property(float, notify=changed)
    def armorLastBreakTime(self) -> float:
        return _f((self._get("armor", {}) or {}).get("last_break_time"), -99999.0)

    @Property(int, notify=changed)
    def sensitivityStage(self) -> int:
        return self._mapping.sensitivity_stage

    @Property(int, notify=changed)
    def sensitivityMaxStage(self) -> int:
        return self._mapping.max_sensitivity_stage

    @Property(float, notify=changed)
    def sensitivityMultiplier(self) -> float:
        return self._mapping.sensitivity_multiplier

    @Property(str, notify=changed)
    def actionName(self) -> str:
        return str(self._get("action_trigger_name", "—"))

    @Property(str, notify=changed)
    def actionHash(self) -> str:
        return str(self._get("action_trigger_hash", "—"))

    @Property("QVariantMap", notify=changed)
    def captureStatus(self) -> dict:
        capture = capture_state(self._state) if self.telemetryOnline and not self._reader_error else capture_state({})
        return {
            "known": capture.known, "active": capture.active,
            "canStruggle": capture.can_struggle,
            "label": ("可挣扎" if capture.can_struggle else "受困中") if capture.active
                     else "未受困" if capture.known else "不可用",
            "count": capture.count if capture.active else 0.0,
            "maximum": capture.maximum if capture.active else 0.0,
            "progress": capture.progress,
        }

    @Property(bool, notify=changed)
    def bossActive(self) -> bool:
        return bool(self._get("boss_battling"))

    @Property(float, notify=changed)
    def bossHp(self) -> float:
        return _f((self._get("boss", {}) or {}).get("current_hp"))

    @Property(float, notify=changed)
    def bossMaxHp(self) -> float:
        return _f((self._get("boss", {}) or {}).get("max_hp"))

    @Property(float, notify=changed)
    def bossHpRatio(self) -> float:
        return max(0.0, min(1.0, self.bossHp / self.bossMaxHp if self.bossMaxHp else 0.0))

    @Property(str, notify=changed)
    def bossState(self) -> str:
        return str((self._get("boss", {}) or {}).get("character_state_name", "—"))

    @Property(str, notify=changed)
    def bossAction(self) -> str:
        return str((self._get("boss", {}) or {}).get("action_trigger_name", "—"))

    @Property(str, notify=changed)
    def storySpeaker(self) -> str:
        return str((self._get("story", {}) or {}).get("speaker") or "旁白")

    @Property(bool, notify=changed)
    def hasStorySpeaker(self) -> bool:
        return bool((self._get("story", {}) or {}).get("speaker"))

    @Property(str, notify=changed)
    def storyText(self) -> str:
        story = self._get("story", {}) or {}
        return str(story.get("stripped_message") or story.get("message") or "当前不在剧情对话中")

    @Property(bool, notify=changed)
    def hasStoryMessage(self) -> bool:
        story = self._get("story", {}) or {}
        return bool(story.get("stripped_message") or story.get("message"))

    @Property(int, notify=changed)
    def storyLine(self) -> int:
        return _i((self._get("story", {}) or {}).get("line_index"), -1)

    @Property(float, notify=changed)
    def pollHz(self) -> float:
        if len(self._sample_times) < 2:
            return 0.0
        span = self._sample_times[-1] - self._sample_times[0]
        return (len(self._sample_times) - 1) / span if span > 0 else 0.0

    @Property(float, notify=changed)
    def latencyMs(self) -> float:
        return self._latency_ms

    @Property(str, notify=changed)
    def readerError(self) -> str:
        return self._reader_error

    @Property(float, notify=changed)
    def previewA(self) -> float:
        return self._preview_a

    @Property(float, notify=changed)
    def previewB(self) -> float:
        return self._preview_b

    @Property(str, notify=changed)
    def waveA(self) -> str:
        return self._wave_a

    @Property(str, notify=changed)
    def waveB(self) -> str:
        return self._wave_b

    @Property("QVariantList", notify=changed)
    def waveAPoints(self) -> list[int]:
        if self._wave_a == "audio-reactive":
            return list(self._audio_points)
        for item in self._wave_catalog():
            if item.get("key") == self._wave_a:
                return list(item.get("points") or [])
        return [0, 0, 0, 0]

    @Property("QVariantList", notify=changed)
    def waveBPoints(self) -> list[int]:
        if self._wave_b == "audio-reactive":
            return list(self._audio_points)
        for item in self._wave_catalog():
            if item.get("key") == self._wave_b:
                return list(item.get("points") or [])
        return [0, 0, 0, 0]

    @Property("QVariantList", notify=eventsChanged)
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    @Property(str, notify=rawJsonChanged)
    def rawJson(self) -> str:
        return self._raw_json

    @Slot(str)
    def selectLanAddress(self, address: str) -> None:
        if address == self._lan_ip:
            return
        if self._bridge.set_lan_ip(address):
            self._disarm_output("连接地址已切换，请核对并重新扫码", log=True)
            self._bridge.emergency_stop()
            self._manual_test_channel = ""
            self._lan_ip = address
            self.changed.emit()

    @Slot()
    def refreshLanAddresses(self) -> None:
        self._bridge.refresh_lan_ips()
        self._lan_addresses = list(self._bridge.available_lan_ips) or ["127.0.0.1"]
        if self._lan_ip not in self._lan_addresses:
            self.selectLanAddress(self._lan_addresses[0])
        self.changed.emit()

    @Slot()
    def diagnoseConnection(self) -> None:
        self.refreshLanAddresses()
        port = self._bridge.port
        lines = [f"Ricca × DG-LAB {__version__}",
                 f"Socket：{'就绪' if self._server_ready else '未就绪'} · TCP {port}",
                 f"连接地址：{self._lan_ip}:{port}",
                 f"二维码：{'可用' if self._qr_source else '不可用'} · 手机：{'已连接' if self._device_connected else '未绑定'}"]
        log_status = audit.status()
        lines.extend([f"运行日志：{log_status['path'] or '未启用（模拟/测试模式）'}",
                      f"日志会话：{log_status['session']} · 丢弃 {log_status['dropped']} · 错误 {log_status['error'] or '无'}",
                      f"配置：{self._config.path} · 教程完成 {self.onboardingCompleted} · 硬上限 {self.hardCap}"])
        if self._server_error:
            lines.append("服务错误：" + self._server_error)
        try:
            listeners = port_listeners(port)
            lines.extend(f"端口监听：{item['name']} · PID {item['pid']} · " + ("本窗口" if item["ours"] else "其他进程")
                         for item in listeners)
            if not listeners:
                lines.append("未发现 IPv4 监听进程；本机服务尚未可用。")
        except OSError as error:
            lines.append(f"无法读取端口占用信息：{error}")
        lines.append("可用 IPv4 网卡：")
        lines.extend("• " + item["label"] for item in self.lanInterfaces)
        lines.extend([
            "", "排查建议：",
            "1. 端口被其他 Ricca 窗口占用：先退出旧窗口，再点“重试 Socket”；不要重复启动。",
            "2. 选择手机同一局域网的 Wi-Fi / 以太网 IPv4；VPN / 虚拟网卡地址可能无法从手机访问。",
            "3. 切换地址后重新扫码，手机选择 DG-LAB 3.0 的 Socket 模式。127.0.0.1 只能在本机使用。",
            f"4. 检查 Windows 防火墙是否允许本程序在专用网络入站 TCP {port}；此处不会自动改规则或关闭防火墙。",
            "5. 检查 VPN 的局域网访问/分流设置、Wi-Fi 访客隔离；本机监听正常不代表手机一定可达。",
        ])
        self._connection_diagnostics = "\n".join(lines)
        self.changed.emit()

    @Slot()
    def copyConnectionDiagnostics(self) -> None:
        if self._connection_diagnostics:
            QGuiApplication.clipboard().setText(self._connection_diagnostics)

    @Slot(result=bool)
    def restartSocket(self) -> bool:
        if self._demo or not self._start_bridge_enabled:
            return False
        self.emergencyStop()
        self._bridge.stop()
        self._server_ready = self._device_connected = False
        self._server_error = self._qr_url = self._qr_source = ""
        self._bridge.server_ready = self._bridge.connected = False
        self._bridge.controller_id = self._bridge.target_id = ""
        self._bridge_status = "正在重新启动 Socket…"
        self._bridge.start()
        self.changed.emit()
        return True

    @Slot()
    def emergencyStop(self) -> None:
        # A connection or settings refresh must never undo an emergency stop.
        self._stop_latched = True
        self._priority_output_active = False
        self._priority_kind = ""
        self._death_penalty.cancel()
        self._user_output_paused = True
        self._sync_output_pause()
        self._output_armed = False
        self._manual_test_channel = ""
        self._tested_channels.clear()
        self._bridge.emergency_stop()
        self._mapping.clear_pulses()
        self._defeat_scene.cancel_pulses()
        self._bridge_status = "紧急停止：A/B 已归零并清空队列"
        self._append_system_event("紧急归零", "自动输出已撤销，A/B 队列已清空", "danger")
        self.changed.emit()

    @Property(str, notify=changed)
    def emergencyHotkey(self) -> str:
        return self._config.values.get("emergency_hotkey", "Ctrl+Alt+F10")

    @Property(str, notify=changed)
    def hotkeyStatus(self) -> str:
        return self._hotkey_status

    def attachHotkey(self, service) -> None:
        self._hotkey_service = service
        service.triggered.connect(self.emergencyStop)
        try:
            ok, detail = service.configure(self.emergencyHotkey)
        except ValueError as error:
            ok, detail = False, str(error)
        self._hotkey_status = "全局急停快捷键已注册" if ok else detail
        if not ok:
            self.emergencyStop()
            QTimer.singleShot(600, lambda: self.toastRequested.emit("全局急停键不可用", detail))
        self.changed.emit()

    @Slot(str, result=bool)
    def saveEmergencyHotkey(self, chord: str) -> bool:
        from .hotkey import parse_hotkey
        try:
            normalized, _, _ = parse_hotkey(chord)
        except ValueError as error:
            self.toastRequested.emit("保存失败",str(error))
            return False
        if self._hotkey_service is None:
            self.toastRequested.emit("保存失败","全局快捷键未注册")
            return False
        self.emergencyStop()
        old = self.emergencyHotkey
        ok, detail = self._hotkey_service.configure(normalized)
        if not ok:
            self.toastRequested.emit("保存失败",detail)
            return False
        try:
            self._config.update({"emergency_hotkey":normalized})
        except OSError as error:
            restored, reason = self._hotkey_service.configure(old)
            self._hotkey_status = "全局急停快捷键已注册" if restored else reason
            self.changed.emit()
            self.toastRequested.emit("保存失败",str(error))
            return False
        self._hotkey_status = "全局急停快捷键已注册"
        self.changed.emit()
        self.toastRequested.emit("保存成功","急停快捷键已保存，输出保持暂停，请手动恢复")
        return True

    @Slot()
    def clearEvents(self) -> None:
        self._events.clear()
        self.eventsChanged.emit()

    @Slot(str, result=bool)
    def setGameExecutablePath(self, value: str) -> bool:
        source = QUrl(value)
        raw_path = source.toLocalFile() if source.isLocalFile() else value
        executable = Path(raw_path).expanduser()
        try:
            executable = executable.resolve(strict=True)
        except (OSError, RuntimeError):
            self._append_system_event("游戏路径未保存", "所选 EXE 不存在", "danger")
            return False
        if not executable.is_file() or executable.suffix.casefold() != ".exe":
            self._append_system_event("游戏路径未保存", "请选择游戏的 .exe 文件", "danger")
            return False
        if not executable.with_name("GameAssembly.dll").is_file():
            self._append_system_event(
                "游戏路径未保存",
                "所选 EXE 同目录没有 GameAssembly.dll",
                "danger",
            )
            return False
        try:
            self._config.update({"game_executable_path": str(executable)})
        except OSError as error:
            self._append_system_event("游戏路径保存失败", str(error), "danger")
            return False
        self._configure_probe_path()
        self._inspect_game_path()
        self._disarm_output("游戏路径已修改，等待有效遥测", log=True)
        self.toastRequested.emit("保存成功", "游戏路径已保存；" + self._game_path_status)
        if self._worker.verifier is not None:
            self._worker.verifier.clear()
        self._reader_error = ""
        self._append_system_event(
            "已启用游戏路径回退",
            self._game_path_status,
            "success" if self._game_path_supported else "warning",
        )
        self.changed.emit()
        return True

    @Slot(result=bool)
    def resetGameExecutablePath(self) -> bool:
        try:
            self._config.update({"game_executable_path": ""})
        except OSError as error:
            self._append_system_event("恢复自动检测失败", str(error), "danger")
            return False
        self._configure_probe_path()
        self._inspect_game_path()
        self._disarm_output("已恢复自动检测，等待有效遥测", log=True)
        if self._worker.verifier is not None:
            self._worker.verifier.clear()
        self._reader_error = ""
        self._append_system_event(
            "已恢复自动检测",
            "将按进程名查找 HolyKnightRicca.exe",
            "success",
        )
        self.changed.emit()
        return True

    @Slot(int, int, int, int, int, result=bool)
    def saveIntensitySettings(self, low: int, medium: int, high: int,
                              death: int, hard_cap: int) -> bool:
        values = tuple(int(item) for item in (low, medium, high, death, hard_cap))
        if not (0 <= values[0] <= values[1] <= values[2] <= values[3]
                <= values[4] <= 100):
            self._append_system_event(
                "强度设置未保存",
                "必须满足 0 ≤ 低 ≤ 中 ≤ 高 ≤ 死亡 ≤ 硬上限 ≤ 100",
                "danger",
            )
            return False
        previous = deepcopy(self._config.values)
        try:
            self._config.update({
                "strength_low": low,
                "strength_medium": medium,
                "strength_high": high,
                "strength_death": death,
                "hard_cap": hard_cap,
            })
        except OSError as error:
            self._config.values = previous
            self._append_system_event("设置保存失败", str(error), "danger")
            return False
        self._refresh_mapping_config()
        self._disarm_output("强度或安全上限已修改，清空旧事件后自动应用", log=True)
        self._bridge.emergency_stop()
        self._manual_test_channel = ""
        self._audio_strength = self._audio_last_sample = 0.0
        self._preview_a = self._preview_b = 0.0
        self._wave_a = self._wave_b = "idle"
        self._append_system_event(
            "强度档位已保存",
            f"低 {low} · 中 {medium} · 高 {high} · 死亡 {death} · 上限 {hard_cap}",
            "success",
        )
        self.changed.emit()
        return True

    @Slot(result=bool)
    def refreshAudioDevices(self) -> bool:
        self._audio_devices = enumerate_audio_devices()
        self._restart_audio_capture()
        self.changed.emit()
        return bool(self._audio_devices)

    @Slot(bool, str, int, int, str, bool, result=bool)
    def saveAudioEmpathySettings(self, enabled: bool, device_id: str,
                                 sensitivity: int, gate: int, channel: str,
                                 story_only: bool) -> bool:
        selected = str(device_id).strip()
        if enabled and not audio_backend_available():
            self._append_system_event("音频共感设置未保存", "音频组件不可用，请运行安装 / 修复运行环境后重试", "danger")
            return False
        available = {item["id"] for item in self._audio_devices}
        if enabled and (not selected or selected not in available):
            self._append_system_event("音频共感设置未保存", "请选择可用的音频输入或系统回环设备", "danger")
            return False
        clean_channel = str(channel).upper()
        if clean_channel not in {"A", "B", "AB"}:
            return False
        try:
            self._config.update({
                "audio_empathy_enabled": bool(enabled),
                "audio_device_id": selected,
                "audio_sensitivity": max(1, min(100, int(sensitivity))),
                "audio_gate": max(0, min(95, int(gate))),
                "audio_channel": clean_channel,
                "audio_story_only": bool(story_only),
            })
        except OSError as error:
            self._append_system_event("音频共感设置失败", str(error), "danger")
            return False
        self._disarm_output("音频共感设置已修改，清空旧事件后自动应用", log=True)
        self._restart_audio_capture()
        self.toastRequested.emit("保存成功", "音频共感设置已保存并应用；连接后按游戏状态自动输出，保留手动暂停状态。")
        self._append_system_event(
            "音频共感已启用" if enabled else "音频共感已关闭",
            self._audio_status,
            "warning" if enabled else "info",
        )
        self.changed.emit()
        return True

    @Slot(str, bool, str, str, result=bool)
    def setEventMapping(self, key: str, enabled: bool, tier: str, wave: str) -> bool:
        rules = {name: dict(value) for name, value in
                 (self._config.values.get("event_rules") or {}).items()}
        if key not in rules or tier not in {"low", "medium", "high", "death"}:
            return False
        available = {item["key"] for item in self._wave_catalog()}
        if wave not in available:
            return False
        rules[key].update({"enabled": bool(enabled), "tier": tier, "wave": wave})
        policies = sanitize_channel_policies(self.channelPolicies)
        for policy in policies.values():
            policy["rules"][key].update({"enabled": bool(enabled), "tier": tier, "wave": wave, "custom_strength": None})
        try:
            self._config.update({"event_rules": rules, "channel_policies": policies})
        except OSError as error:
            self._append_system_event("事件映射保存失败", str(error), "danger")
            return False
        self._refresh_mapping_config()
        self._disarm_output("事件映射已修改，清空旧事件后自动应用", log=True)
        self.toastRequested.emit("保存成功", "事件强度与波形已保存并应用。")
        self.changed.emit()
        return True

    @Slot(str, result=bool)
    def applyWaveformToAllEvents(self, wave: str) -> bool:
        available = {item["key"] for item in self._wave_catalog()}
        if wave not in available:
            return False
        rules = {name: dict(value) for name, value in
                 (self._config.values.get("event_rules") or {}).items()}
        for rule in rules.values():
            rule["wave"] = wave
        policies = sanitize_channel_policies(self.channelPolicies)
        for policy in policies.values():
            for rule in policy["rules"].values():
                rule["wave"] = wave
        try:
            self._config.update({"event_rules": rules, "channel_policies": policies})
        except OSError as error:
            self._append_system_event("固定波形保存失败", str(error), "danger")
            return False
        self._refresh_mapping_config()
        self._disarm_output("固定波形策略已修改，清空旧事件后自动应用", log=True)
        self._append_system_event("固定波形已应用", self.waveformName(wave), "success")
        self.changed.emit()
        return True

    @Slot(result=bool)
    def resetEventMappings(self) -> bool:
        rules = {key: dict(value) for key, value in DEFAULT_EVENT_RULES.items()}
        try:
            self._config.update({"event_rules": rules, "channel_policies": default_channel_policies()})
        except OSError as error:
            self._append_system_event("恢复默认映射失败", str(error), "danger")
            return False
        self._refresh_mapping_config()
        self._disarm_output("事件映射已恢复默认，清空旧事件后自动应用", log=True)
        self._append_system_event("事件映射已恢复默认", "Boss 捕获保持关闭", "success")
        self.changed.emit()
        return True

    @Slot(str, result=str)
    def waveformName(self, key: str) -> str:
        if key == "audio-reactive":
            return "音频实时包络"
        for item in self._wave_catalog():
            if item.get("key") == key:
                return str(item.get("name") or key)
        return key

    @Slot(str, "QVariantList", int, result=bool)
    def saveCustomWaveform(self, name: str, points: list, frequency: int) -> bool:
        try:
            target = save_custom_waveform(name, list(points), frequency)
        except (OSError, ValueError, TypeError) as error:
            self._append_system_event("自定义波形保存失败", str(error), "danger")
            return False
        self._custom_waveforms = read_custom_waveforms()
        self._append_system_event("自定义波形已保存", target.name, "success")
        self.changed.emit()
        return True

    @Slot(str, result="QVariantList")
    def waveformPoints(self, key: str) -> list[int]:
        for item in self._wave_catalog():
            if item.get("key") == key:
                return list(item.get("points") or [])
        return []

    @Slot(result=bool)
    def openWaveformLibraryFolder(self) -> bool:
        directory = waveform_library_dir()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            self._append_system_event("打开波形目录失败", str(error), "danger")
            return False
        return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))))

    @Slot()
    def resetSensitivity(self) -> None:
        previous = self._mapping.sensitivity_stage
        self._mapping.reset_sensitivity()
        self._append_system_event(
            "敏感度已重置",
            f"Stage {previous} → 0 · 倍率 ×1.00",
            "warning" if previous else "info",
        )
        self.changed.emit()

    @Slot(str, result=bool)
    def runDeviceTest(self, channel: str) -> bool:
        clean_channel = str(channel).upper()
        if clean_channel not in {"A", "B"} or not self.canRunDeviceTest:
            return False
        self._output_armed = False
        self._bridge.set_auto_enabled(False)
        ok = self._bridge.manual_test(
            min(5, self.hardCap),
            frames_for("tap"),
            hard_cap=min(10, self.hardCap),
            channel=clean_channel,
        )
        if not ok:
            self._bridge_status = f"{clean_channel} 通道测试未启动 · 请检查设备连接"
            self.changed.emit()
            return False
        self._manual_test_channel = clean_channel
        self._bridge_status = f"{clean_channel} 通道低强度测试准备中"
        self.changed.emit()
        return True

    @Slot(result=bool)
    def armOutput(self) -> bool:
        if not self.canArmOutput:
            self._bridge_status = "输出等待中 · 请完成连接、安全硬上限和游戏状态检查"
            self.changed.emit()
            return False
        self._output_armed = True
        self._bridge_status = f"实时输出已启用 · 所有命令受硬上限 {self.hardCap} 约束"
        self._append_system_event(
            "实时输出已启用",
            f"本次会话有效 · 硬上限 {self.hardCap} · 败北 CG 入场及互动按通道规则输出",
            "warning",
        )
        self.changed.emit()
        return True

    @Slot()
    def disarmOutput(self) -> None:
        self._user_output_paused = True
        self._sync_output_pause()
        self._disarm_output("用户关闭实时输出", log=True)

    def _sync_auto_output(self) -> bool:
        """Connection is sufficient; scene/read gates still govern every frame."""
        armed = bool(not self._demo and self._device_connected
                     and self.onboardingCompleted and self.hardCap > 0
                     and not self._onboarding_active
                     and not self._stop_latched
                     and not self._user_output_paused
                     and not self._manual_test_channel)
        changed = armed != self._output_armed
        self._output_armed = armed
        return changed

    @Slot()
    def requestUnlock(self) -> None:
        self._bridge_status = self.outputStatus
        self.changed.emit()

    def _disarm_output(self, reason: str, *, log: bool = False, preserve_defeat: bool = False) -> None:
        was_armed = self._output_armed
        self._output_armed = False
        self._bridge.set_auto_enabled(False)
        self._mapping.clear_pulses()
        if not preserve_defeat:
            self._defeat_scene.cancel_pulses()
            self._death_penalty.cancel()
        self._priority_output_active = False
        if was_armed:
            self._bridge_status = f"输出已关闭 · {reason}"
            if log:
                self._append_system_event("实时输出已关闭", reason, "warning")

    def _audio_output_allowed(self) -> bool:
        if self._pause_active or not self.audioEmpathyEnabled or time.monotonic() - self._audio_last_sample > 0.35:
            return False
        return self._decision.allow_story_output

    def _defeat_story_allowed(self) -> bool:
        state, stage = self._state, self._state.get("stage") or {}
        return bool(not self._stop_latched and state.get("status") == "ok"
                    and state.get("connected", True) and state.get("build_supported") is True
                    and is_story_scene(state) and not stage.get("is_game_over")
                    and not stage.get("scene_change_playing")
                    and stage.get("all_resource_loaded") is not False)

    def _stop_audio_capture(self) -> None:
        self._audio_stop.set()
        worker = self._audio_worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=0.7)
        self._audio_worker = None

    def _restart_audio_capture(self) -> None:
        self._stop_audio_capture()
        self._audio_stop = threading.Event()
        self._audio_mapper = AudioPulseMapper()
        self._audio_strength = 0.0
        self._audio_last_sample = 0.0
        if not self.audioEmpathyEnabled:
            self._audio_status = "音频共感已关闭"
            return
        if not audio_backend_available():
            self._audio_status = "音频模块不可用 · 请安装 requirements-native.txt"
            return
        device_id = self.audioDeviceId
        if not device_id:
            self._audio_status = "没有检测到录音或系统回环设备"
            return
        self._audio_status = "正在打开音频设备…"
        self._audio_worker = AudioCaptureWorker(self._queue, device_id, self._audio_stop)
        self._audio_worker.start()

    def _apply_audio_sample(self, payload: dict[str, Any]) -> None:
        hybrid_story = (any(story_mode(p) in {"audio", "fixed_audio", "queue_audio"}
                            and p["mode"] != "off" for p in self.channelPolicies.values())
                        and self._defeat_story_allowed() and not self._user_output_paused
                        and not (self._state.get("game_ui") or {}).get("is_user_pause"))
        if ((self._pause_active and not hybrid_story)
                or _f(payload.get("received_at"), time.monotonic()) <= self._audio_resume_after):
            return
        rms = max(0.0, _f(payload.get("rms")))
        peak = max(0.0, _f(payload.get("peak")))
        mapped = self._audio_mapper.map(
            rms,
            sensitivity=self.audioSensitivity,
            gate=self.audioGate,
            hard_cap=self.hardCap,
        )
        self._audio_level = float(mapped["level"])
        self._audio_peak = AudioPulseMapper.meter_percent(peak)
        self._audio_dbfs = float(mapped["dbfs"])
        self._audio_strength = float(mapped["strength"])
        points = payload.get("points")
        if isinstance(points, list) and len(points) == 16:
            self._audio_points = [max(0, min(100, _i(value))) for value in points]
        self._audio_last_sample = _f(payload.get("received_at"), time.monotonic())

    def _append_system_event(self, title: str, detail: str, severity: str = "info") -> None:
        audit.record("app.event", title=title, severity=severity)
        if title == "紧急归零":
            self.toastRequested.emit("输出已紧急停止", detail)
        elif severity == "danger":
            self.toastRequested.emit("操作失败", title + "：" + detail)
        elif severity == "success" and any(word in title for word in ("已保存", "已应用", "已恢复默认", "教程已完成", "已恢复自动")):
            self.toastRequested.emit("保存成功", title + "：" + detail)
        self._events.appendleft({"id": f"system-{time.monotonic_ns()}",
                                 "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                                 "kind": "system", "title": title, "detail": detail,
                                 "severity": severity, "data": {}})
        self.eventsChanged.emit()

    def _apply_state(self, payload: dict[str, Any]) -> None:
        previous_state = self._state
        detector_had_baseline = self._detector.previous is not None
        state = dict(payload["state"])
        state.setdefault("connected", True)
        now = float(payload["received_at"])
        self._state = state
        if (is_story_scene(state) and
                (not is_story_scene(previous_state)
                 or scene_root((state.get("story") or {}).get("asset_name")) != scene_root((previous_state.get("story") or {}).get("asset_name")))):
            # Never reuse battle/menu audio on the first frame of a story.
            self._audio_strength = self._audio_last_sample = 0.0
            self._audio_mapper = AudioPulseMapper()
            self._audio_resume_after = now
        self._last_received = now
        self._sample_times.append(now)
        self._latency_ms = float(payload["latency_ms"])
        self._reader_error = ""
        self._decision = self._safety.observe(state, now)
        self._sync_output_pause()
        if self._mapping.observe_life(state):
            self._detector.reset(now)
            self._death_penalty.cancel()
        detected = self._detector.ingest(state, now)
        if (type(state.get("current_hp")) in {int, float} and state["current_hp"] == 0
                and (previous_state.get("current_hp") != 0 or not detector_had_baseline
                     or previous_state.get("player_address") != state.get("player_address")
                     or previous_state.get("scene") != state.get("scene"))):
            death_detected = any(event.kind == "player_down" for event in detected)
            missing_edge_reasons = []
            if not death_detected:
                if not detector_had_baseline: missing_edge_reasons.append("no-detector-baseline")
                if _f(previous_state.get("current_hp")) <= 0: missing_edge_reasons.append("no-positive-hp-edge")
                if previous_state.get("player_address") != state.get("player_address"): missing_edge_reasons.append("player-object-changed")
                if previous_state.get("scene") != state.get("scene"): missing_edge_reasons.append("scene-changed")
                if state.get("scene") != "gameplay": missing_edge_reasons.append("not-gameplay-scene")
                if state.get("status") != "ok": missing_edge_reasons.append("invalid-read")
                if _f(state.get("max_hp")) <= 0: missing_edge_reasons.append("invalid-max-hp")
            audit.record("death.zero_observed", **audit.state_fields(state),
                         previous_hp=previous_state.get("current_hp"),
                         detector_baseline=detector_had_baseline,
                         actor_changed=previous_state.get("player_address") != state.get("player_address"),
                         scene_changed=previous_state.get("scene") != state.get("scene"),
                         death_detected=death_detected, not_triggered_reasons=missing_edge_reasons)
        allow_gameplay = self._decision.allow_gameplay_output and not self._pause_active
        self._mapping.reconcile_capture(state, allow_output=allow_gameplay, now=now)
        cg_changes = self._defeat_scene.observe(
            state, now=now, allow_story=self._defeat_story_allowed(),
            paused=self._stop_latched,
            registered_scenes=self._config.values["scene_catalog"],
            blocked_scenes=set(self._scene_library.entries) - set(self._config.values["scene_catalog"]),
        )
        asset = str((state.get("story") or {}).get("asset_name") or "")
        current_root = scene_root(asset)
        active_asset = asset if current_root and state.get("scene") in {"adv", "atd", "anv"} else ""
        if active_asset != self._last_scene_asset:
            audit.record("scene.observed", asset=active_asset,
                         scene_root=current_root if active_asset else "",
                         registered=current_root in self._config.values["scene_catalog"],
                         **audit.state_fields(state))
            self._last_scene_asset = active_asset
        capture_key = (active_asset, str((state.get("atd") or {}).get("cut_name") or ""))
        if self._scene_capture_enabled and self.currentSceneId and capture_key != self._last_scene_capture:
            try:
                root = self._scene_library.record(state)
            except (OSError, ValueError) as error:
                self._scene_capture_enabled = False
                self.toastRequested.emit("自动记录已停止", str(error))
            else:
                self._last_scene_capture = capture_key
                audit.record("scene.recorded", scene_root=root, source="automatic")
            self.sceneLibraryChanged.emit()
        elif not active_asset:
            self._last_scene_capture = None
        for event in detected:
            if event.kind == "player_down":
                blockers = []
                if self._stop_latched: blockers.append("emergency-stop")
                if not self._device_connected: blockers.append("phone-not-bound")
                if not self.onboardingCompleted: blockers.append("onboarding-incomplete")
                if self.hardCap <= 0: blockers.append("hard-cap-zero")
                audit.record("death.detected", event_sequence=event.sequence,
                             trigger_blockers=blockers, scheduled=not blockers,
                             hard_cap=self.hardCap, strengths=self._strength_settings(),
                             **audit.state_fields(state))
            if (event.kind == "player_down" and not self._stop_latched
                    and self._device_connected and self.onboardingCompleted and self.hardCap > 0):
                self._death_penalty.trigger(state, self.channelPolicies, now=now, sequence=event.sequence)
                channel_status = {}
                for channel, policy in self.channelPolicies.items():
                    rule = policy["rules"]["player_down"]
                    configured = rule["custom_strength"]
                    if configured is None:
                        configured = self._strength_settings().get(rule["tier"], 0)
                    channel_blocks = []
                    if policy["mode"] == "off": channel_blocks.append("channel-mode-off")
                    if not rule["enabled"]: channel_blocks.append("death-rule-disabled")
                    if configured <= 0: channel_blocks.append("configured-strength-zero")
                    channel_status[channel] = {"blockers":channel_blocks,
                                               "capped_strength":min(self.hardCap, max(0, configured))}
                audit.record("death.scheduled", event_sequence=event.sequence,
                             channels=channel_status,
                             rules={ch: {"mode": policy["mode"],
                                         **policy["rules"]["player_down"]}
                                    for ch, policy in self.channelPolicies.items()})
                self._defeat_scene.record_death(state, now)
                # Only this HP-edge scheduler owns the one-off death punishment.
        for kind, title, detail in cg_changes:
            audit.record("defeat.transition", kind=kind, title=title,
                         scene_root=self._defeat_scene.root, catalogued=self._defeat_scene.catalogued,
                         phase=self._defeat_scene.phase, **audit.state_fields(state))
            self._events.appendleft({"id": f"cg-{time.monotonic_ns()}", "time": datetime.now().astimezone().isoformat(timespec="milliseconds"),
                                     "kind": kind, "title": title, "detail": detail, "severity": "warning", "data": {}})
        if cg_changes:
            self.eventsChanged.emit()
        self._mapping.accept(detected, allow_output=allow_gameplay)
        # An end edge for an old object must not remove a fresh object's hold.
        self._mapping.reconcile_capture(state, allow_output=allow_gameplay, now=now)
        for event in detected:
            self._events.appendleft(event.as_dict())
        if detected:
            self.eventsChanged.emit()
        self._raw_json = json.dumps(state, ensure_ascii=False, indent=2)
        self.rawJsonChanged.emit()

    def _apply_bridge(self, payload: dict[str, Any]) -> None:
        event = payload.get("event")
        if event == "ready":
            self._server_ready = True
            self._server_error = ""
            self._lan_ip = str(payload.get("lan_ip", self._lan_ip))
            self._qr_url = str(payload.get("qr_url", ""))
            self._qr_source = _qr_data_url(self._qr_url)
            self._bridge_status = f"Socket 已就绪 · {self._lan_ip}:{payload.get('port', 9999)}"
        elif event == "connected":
            self._device_connected = True
            self._output_armed = False
            self._mapping.clear_pulses()
            self._defeat_scene.cancel_pulses()
            self._death_penalty.cancel()
            self._detector.pending_damage = None
            self._tested_channels.clear()
            self._manual_test_channel = ""
            self._sync_auto_output()
            self._bridge_status = "DG-LAB App 已连接 · 按游戏状态自动输出（受硬上限约束）"
            self._append_system_event("DG-LAB 已连接", self.outputStatus, "success")
        elif event == "disconnected":
            self._device_connected = False
            self._disarm_output("设备断开")
            self._detector.pending_damage = None
            self._tested_channels.clear()
            self._manual_test_channel = ""
            self._bridge_status = "DG-LAB App 已断开"
            self._append_system_event("DG-LAB 已断开", "已执行安全归零", "warning")
        elif event == "test_started":
            channel = str(payload.get("channel", "")).upper()
            self._manual_test_channel = channel
            self._bridge_status = f"{channel} 通道测试中 · 强度 {payload.get('strength', 5)}"
        elif event == "test_finished":
            channel = str(payload.get("channel", "")).upper()
            if channel in {"A", "B"}:
                self._tested_channels.add(channel)
            self._manual_test_channel = ""
            self._bridge_status = (
                "A/B 低强度测试完成 · 自动输出将按游戏状态恢复"
                if self.deviceTestsComplete
                else f"{channel} 通道测试完成 · 还需测试 "
                     f"{'B' if channel == 'A' else 'A'} 通道"
            )
            self._append_system_event(
                f"{channel} 通道测试完成", "强度已归零，队列已清空", "success"
            )
        elif event in {"error", "server_error"}:
            self._stop_latched = True
            self._priority_output_active = False
            self._death_penalty.cancel()
            self._defeat_scene.cancel_pulses()
            self._user_output_paused = True
            self._sync_output_pause()
            self._output_armed = False
            self._bridge_status = str(payload.get("detail", "Socket 错误"))
            if event == "server_error":
                self._server_ready = self._device_connected = False
                self._server_error = self._bridge_status
                self._qr_url = self._qr_source = ""
            self._append_system_event("Socket 错误", self._bridge_status, "danger")
        elif event == "output_timeout":
            self._stop_latched = True
            self._priority_output_active = False
            self._death_penalty.cancel()
            self._defeat_scene.cancel_pulses()
            self._user_output_paused = True
            self._sync_output_pause()
            self._disarm_output("设备发送看门狗超时", log=True)

    @Slot()
    def _drain(self) -> None:
        changed = False
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            changed = True
            if kind == "telemetry":
                self._apply_state(payload)
            elif kind == "telemetry_error":
                audit.record("telemetry.read_error", reason="read-failed",
                             detail=str(payload.get("detail", ""))[:300])
                self._reader_error = str(payload.get("detail", "读取失败"))
                # Do not retain a capture pulse through even one failed read,
                # or infer a struggle delta across the missing interval.
                self._mapping.stop_capture_pulses()
                self._detector.reset()
                self._defeat_scene.interrupt(time.monotonic())
            elif kind == "dglab":
                self._apply_bridge(payload)
            elif kind == "audio_sample":
                self._apply_audio_sample(payload)
            elif kind == "audio_status":
                self._audio_status = str(payload.get("detail") or payload.get("status") or "音频状态未知")
        now = time.monotonic()
        expired = self._detector.tick(now)
        if expired:
            self._mapping.accept(expired, allow_output=self._decision.allow_gameplay_output and self.telemetryOnline and not self._pause_active)
            for event in expired:
                self._events.appendleft(event.as_dict())
            self.eventsChanged.emit()
            changed = True
        if self._safety.stale(now) and self._decision.mode not in {
                RuntimeMode.DISCONNECTED, RuntimeMode.READ_ERROR}:
            self._decision = SafetyDecision(RuntimeMode.READ_ERROR, False, False, "telemetry-stale")
            self._disarm_output("遥测超过 500 ms 未更新", log=True, preserve_defeat=True)
            self._defeat_scene.interrupt(now)
            changed = True
        changed = self._sync_auto_output() or changed
        preview_decision = (SafetyDecision(RuntimeMode.PAUSED, False, False, "output-paused")
                            if self._pause_active else self._decision)
        preview = self._mapping.preview(preview_decision, now)
        strength_a, strength_b = preview.strength_a, preview.strength_b
        wave_a, wave_b = preview.wave_a, preview.wave_b
        audio_strength = min(self.hardCap, self._audio_strength * self.audioGain) if self._audio_output_allowed() else 0.0
        if audio_strength > 0:
            if self.channelPolicies["A"]["mode"] == "audio" and "story_mode" not in self.channelPolicies["A"]:
                strength_a, wave_a = audio_strength, "audio-reactive"
            if self.channelPolicies["B"]["mode"] == "audio" and "story_mode" not in self.channelPolicies["B"]:
                strength_b, wave_b = audio_strength, "audio-reactive"
        cg = self._defeat_scene.preview(
            self.channelPolicies, self._strength_settings(), self.hardCap, now=now,
            allow=self.telemetryOnline and not self._reader_error and self._defeat_story_allowed(),
            allow_loop=not (self._user_output_paused
                            or (self._state.get("game_ui") or {}).get("is_user_pause")),
        )
        death = self._death_penalty.preview(self._state, self._strength_settings(), self.hardCap, now=now)
        eligible = bool(not self._demo and not self._stop_latched
            and not self._onboarding_active and self.onboardingCompleted and self.hardCap > 0
            and self._device_connected and self.telemetryOnline and not self._reader_error
            and self._state.get("build_supported") is True)
        session = self._defeat_scene
        queue_ready = bool(eligible and session.root and session.confirm_count >= 3
            and 0 <= now - session.updated < 0.5 and self._defeat_story_allowed()
            and session.phase in {"dialogue", "interaction", "stopped"}
            and not self._user_output_paused
            and not (self._state.get("game_ui") or {}).get("is_user_pause")
            and death.strength_a <= 0 and death.strength_b <= 0)
        audio_channels = {ch for ch, policy in self.channelPolicies.items()
                          if story_mode(policy) in {"audio", "fixed_audio", "queue_audio"}}
        queue_channels = {ch for ch, policy in self.channelPolicies.items()
                          if policy["mode"] != "off" and policy["rules"]["defeat_interaction"]["enabled"]
                          and (story_mode(policy) == "queue" or ch in audio_channels)}
        key = (session.pid, session.root, session.sequence) if session.root else None
        asset = str((self._state.get("story") or {}).get("asset_name") or "")
        audio_context = bool(self._defeat_story_allowed() and asset.startswith("ADV/"))
        audio_key = (self._state.get("process_id"), "audio-story", scene_root(asset) or asset) if audio_context else None
        audio_ready = bool(eligible and audio_context and self.audioEmpathyEnabled
                           and 0 <= now - self._audio_last_sample < 0.35
                           and not self._user_output_paused
                           and not (self._state.get("game_ui") or {}).get("is_user_pause")
                           and death.strength_a <= 0 and death.strength_b <= 0)
        active_channels = {ch for ch in queue_channels if audio_ready and ch in audio_channels}
        active_channels |= {ch for ch in queue_channels if queue_ready and ch not in audio_channels}
        keys = {ch: audio_key if ch in audio_channels else key for ch in ("A", "B")}
        self._story_queue_player.tick(keys, now, active_channels)
        queue_active, queue_status = {}, {}
        for channel in ("A", "B"):
            rule = self.channelPolicies[channel]["rules"]["defeat_interaction"]
            plan = self.storyQueues[channel]
            if channel in audio_channels and story_mode(self.channelPolicies[channel]) != "queue_audio":
                plan = sanitize_steps([{**rule, "duration": 30}])
            selected = self._story_queue_player.select(channel, plan, self._strength_settings(), self.hardCap)
            active = channel in active_channels and selected is not None
            if selected:
                selected = dict(selected)
                selected["audio_modulated"] = channel in audio_channels
                if channel in audio_channels:
                    if story_mode(self.channelPolicies[channel]) == "audio":
                        selected["wave"] = "audio-reactive"
                    factor = min(1.0, max(0.0, self._audio_strength / max(1, self.hardCap))) if audio_ready and self._audio_level > self.audioGate else 0.0
                    selected["base_strength"] = selected["strength"]
                    selected["audio_factor"] = round(factor, 3)
                    selected["audio_gain"] = self.audioGain
                    selected["strength"] = min(self.hardCap, selected["strength"] * factor * self.audioGain)
                    # A fresh, authorized queue may retain a user-selected bed
                    # under voice gaps. Never turn explicit rests, zero bases,
                    # master mute, stale capture or blocked scenes into output.
                    floor = (self.audioQueueMinimum if active and audio_ready and self.audioGain > 0
                             and story_mode(self.channelPolicies[channel]) == "queue_audio"
                             and selected["base_strength"] > 0 else 0)
                    selected["minimum_strength"] = floor
                    selected["strength"] = min(self.hardCap, max(floor, selected["strength"]))
                missing = selected["wave"] not in {"idle", "audio-reactive"} and not frames_for(selected["wave"], self._custom_waveforms)
                if missing or selected["wave"] == "idle":
                    selected["strength"] = 0
                selected.update(playing=bool(active), enabled=channel in queue_channels, missing_wave=bool(missing))
            queue_status[channel] = {
                **(selected or {"count": 0, "playing": False, "enabled": channel in queue_channels}),
                "configured": self.channelPolicies[channel]["rules"]["defeat_interaction"].get("playback") == "queue",
            }
            self._story_queue_tokens[channel] = selected["token"] if active else ""
            if active:
                queue_active[channel] = selected
            signature = (bool(active), selected["token"] if selected else "", bool(selected and selected.get("missing_wave")))
            if signature != self._last_queue_audit.get(channel):
                audit.record("story.queue_step", channel=channel, playing=bool(active),
                             index=selected["index"] if selected else None,
                             wave=selected["wave"] if selected else "idle",
                             strength=selected["strength"] if selected else 0,
                             missing_wave=bool(selected and selected.get("missing_wave")))
                self._last_queue_audit[channel] = signature
        if queue_status != self._story_queue_status:
            self._story_queue_status = queue_status
            changed = True
        cg_a = "A" in queue_active or (cg.strength_a > 0 and cg.strength_a >= strength_a)
        cg_b = "B" in queue_active or (cg.strength_b > 0 and cg.strength_b >= strength_b)
        if cg_a:
            strength_a, wave_a = ((queue_active["A"]["strength"], queue_active["A"]["wave"])
                                  if "A" in queue_active else (cg.strength_a, cg.wave_a))
        if cg_b:
            strength_b, wave_b = ((queue_active["B"]["strength"], queue_active["B"]["wave"])
                                  if "B" in queue_active else (cg.strength_b, cg.wave_b))
        death_a, death_b = death.strength_a > 0, death.strength_b > 0
        if death_a:
            strength_a, wave_a = death.strength_a, death.wave_a
        if death_b:
            strength_b, wave_b = death.strength_b, death.wave_b
        multiplier = self._mapping.sensitivity_multiplier
        strength_a = min(self.hardCap, strength_a * multiplier)
        strength_b = min(self.hardCap, strength_b * multiplier)
        next_preview = (strength_a, strength_b, wave_a, wave_b)
        if next_preview != (self._preview_a, self._preview_b, self._wave_a, self._wave_b):
            self._preview_a, self._preview_b, self._wave_a, self._wave_b = next_preview
            changed = True
        priority = bool(death_a or death_b or cg_a or cg_b)
        output_safe = eligible and (priority or (self._output_armed and not self._pause_active
            and (self._decision.allow_gameplay_output or self._decision.allow_story_output)))
        reasons = self._output_block_reasons(priority)
        gate_signature = (output_safe, priority, tuple(reasons), self._decision.mode.value,
                          self._death_penalty.sequence, wave_a, wave_b)
        if gate_signature != self._last_output_audit or now - self._last_output_audit_at >= 10:
            audit.record("output.gate", allowed=output_safe, blockers=reasons,
                         scene_root=scene_root((self._state.get("story") or {}).get("asset_name")),
                         scene_registered=scene_root((self._state.get("story") or {}).get("asset_name")) in self._config.values["scene_catalog"],
                         scene_catalog_count=self.registeredSceneCount,
                         priority=priority, death_sequence=self._death_penalty.sequence,
                         death_preview_reason=death.reason, cg_preview_reason=cg.reason,
                         requested={"A": strength_a, "B": strength_b},
                         waveforms={"A": wave_a, "B": wave_b},
                         hard_cap=self.hardCap, mode=self._decision.mode.value,
                         **audit.state_fields(self._state))
            self._last_output_audit, self._last_output_audit_at = gate_signature, now
        priority_active = bool(eligible and priority)
        priority_kind = ("死亡惩罚" if death_a or death_b
                         else "剧情音频" if any(ch in queue_active for ch in audio_channels)
                         else "场景循环" if self._defeat_scene.catalogued else "败北互动") if priority_active else ""
        if (priority_active, priority_kind) != (self._priority_output_active, self._priority_kind):
            self._priority_output_active, self._priority_kind = priority_active, priority_kind
            changed = True
        self._bridge.set_paused(self._stop_latched or (self._pause_active and not priority_active))
        if output_safe:
            def output_frames(wave_key: str) -> tuple[str, ...]:
                if wave_key == "audio-reactive":
                    return custom_frames(self._audio_points, 80)
                return frames_for(wave_key, self._custom_waveforms)

            self._bridge.update_auto_outputs(
                strength_a,
                output_frames(wave_a) if strength_a > 0 else (),
                wave_key_a=wave_a if wave_a == "audio-reactive" else wave_a + ":" + (self._death_penalty.token("A") if death_a else self._defeat_scene.token("A") + self._story_queue_tokens["A"] if cg_a else self._mapping.pulse_token("A")),
                strength_b=strength_b,
                frames_b=output_frames(wave_b) if strength_b > 0 else (),
                wave_key_b=wave_b if wave_b == "audio-reactive" else wave_b + ":" + (self._death_penalty.token("B") if death_b else self._defeat_scene.token("B") + self._story_queue_tokens["B"] if cg_b else self._mapping.pulse_token("B")),
                hard_cap=self.hardCap,
            )
        self._bridge.set_auto_enabled(output_safe)
        if changed:
            self.changed.emit()

    def _output_block_reasons(self, priority: bool) -> list[str]:
        """Explain the existing gates without changing their authorization logic."""
        checks = [
            (self._demo, "demo-mode"), (self._stop_latched, "emergency-stop"),
            (self._onboarding_active, "onboarding-open"),
            (not self.onboardingCompleted, "onboarding-incomplete"),
            (self.hardCap <= 0, "hard-cap-zero"),
            (not self._device_connected, "phone-not-bound"),
            (not self.telemetryOnline, "telemetry-stale-or-offline"),
            (bool(self._reader_error), "read-error"),
            (self._state.get("build_supported") is not True, "unsupported-build"),
        ]
        if not priority:
            checks.extend([
                (not self._output_armed, "auto-output-not-armed"),
                (self._user_output_paused, "user-output-paused"),
                (game_is_paused(self._state), "game-paused"),
                (not (self._decision.allow_gameplay_output or self._decision.allow_story_output), "scene-not-output-ready"),
            ])
        return [reason for blocked, reason in checks if blocked]

    def shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        audit.record("session.shutdown")
        self._timer.stop()
        self._stop.set()
        self._bridge.emergency_stop()
        self._bridge.stop()
        self._stop_audio_capture()
        if self._hotkey_service is not None:
            self._hotkey_service.close()
        if self._worker.is_alive():
            self._worker.join(timeout=1.5)
