"""Display-only desktop overlay, positioned like Manaka's compact Unity HUD."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import math
import sys
import time
from typing import Callable

from PySide6.QtCore import QObject, Property, QRect, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from .safety import is_story_scene


@dataclass(frozen=True)
class GameViewport:
    # Win32 physical client coordinates, excluding window borders/title bar.
    x: int
    y: int
    width: int
    height: int
    monitor_x: int = 0
    monitor_y: int = 0
    monitor_name: str = ""
    monitor_width: int = 0
    monitor_height: int = 0


def screen_for_viewport(viewport: GameViewport, screens):
    for screen in screens:
        if screen.name().casefold() == viewport.monitor_name.casefold():
            return screen
    # Qt can expose EDID friendly names ("LG ULTRAGEAR") rather than Win32's
    # "\\\\.\\DISPLAY1". Match physical monitor bounds as well as its origin.
    for screen in screens:
        bounds, dpr = screen.geometry(), screen.devicePixelRatio()
        dimensions_match = (
            abs(bounds.width() * dpr - viewport.monitor_width) <= 2
            and abs(bounds.height() * dpr - viewport.monitor_height) <= 2
        )
        origin_match = any(
            abs(bounds.x() * scale - viewport.monitor_x) <= 2
            and abs(bounds.y() * scale - viewport.monitor_y) <= 2
            for scale in (1.0, dpr)
        )
        if dimensions_match and origin_match:
            return screen
    return None


def hud_geometry(viewport: GameViewport, *, dpr: float = 1.0,
                 screen_x: int = 0, screen_y: int = 0,
                 top_aligned: bool = False) -> QRect:
    """Manaka anchors/scaling; ADV uses the same 24-unit margin at the top."""
    scale = math.sqrt(viewport.width * viewport.height / (1920.0 * 1080.0))
    left = viewport.x + viewport.width * 0.21
    top = (viewport.y + 24 * scale if top_aligned
           else viewport.y + viewport.height - (24 + 68) * scale)
    return QRect(
        round(screen_x + (left - viewport.monitor_x) / dpr),
        round(screen_y + (top - viewport.monitor_y) / dpr),
        max(1, round(viewport.width * 0.38 / dpr)),
        max(1, round(68 * scale / dpr)),
    )


class ForegroundGameWindow:
    """Query the foreground game's client bounds; never activate any window."""

    def __init__(self) -> None:
        self.api = ctypes.WinDLL("user32", use_last_error=True) if sys.platform == "win32" else None
        if self.api is None:
            return
        api = self.api
        api.GetForegroundWindow.argtypes = []
        api.GetForegroundWindow.restype = wintypes.HWND
        api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        api.GetWindowThreadProcessId.restype = wintypes.DWORD
        for name in ("IsWindowVisible", "IsIconic"):
            getattr(api, name).argtypes = [wintypes.HWND]
            getattr(api, name).restype = wintypes.BOOL
        api.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        api.GetClientRect.restype = wintypes.BOOL
        api.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        api.ClientToScreen.restype = wintypes.BOOL
        api.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        api.MonitorFromWindow.restype = wintypes.HANDLE
        api.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        api.GetMonitorInfoW.restype = wintypes.BOOL
        api.SetThreadDpiAwarenessContext.argtypes = [wintypes.HANDLE]
        api.SetThreadDpiAwarenessContext.restype = wintypes.HANDLE

    def __call__(self, process_id: int) -> GameViewport | None:
        if self.api is None or process_id <= 0:
            return None
        api = self.api
        handle = api.GetForegroundWindow()
        owner = wintypes.DWORD()
        api.GetWindowThreadProcessId(handle, ctypes.byref(owner))
        if owner.value != process_id or not api.IsWindowVisible(handle) or api.IsIconic(handle):
            return None

        class MonitorInfo(ctypes.Structure):
            _fields_ = [("size", wintypes.DWORD), ("monitor", wintypes.RECT),
                        ("work", wintypes.RECT), ("flags", wintypes.DWORD),
                        ("device", wintypes.WCHAR * 32)]

        # Physical pixels first, then map to the target QScreen's logical units.
        previous_dpi = api.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
        try:
            bounds, origin = wintypes.RECT(), wintypes.POINT(0, 0)
            monitor = MonitorInfo()
            monitor.size = ctypes.sizeof(monitor)
            if not api.GetClientRect(handle, ctypes.byref(bounds)) or not api.ClientToScreen(handle, ctypes.byref(origin)):
                return None
            if bounds.right < 64 or bounds.bottom < 64:
                return None
            if not api.GetMonitorInfoW(api.MonitorFromWindow(handle, 2), ctypes.byref(monitor)):
                return None
            return GameViewport(origin.x, origin.y, bounds.right, bounds.bottom,
                                monitor.monitor.left, monitor.monitor.top, monitor.device,
                                monitor.monitor.right - monitor.monitor.left,
                                monitor.monitor.bottom - monitor.monitor.top)
        finally:
            if previous_dpi:
                api.SetThreadDpiAwarenessContext(previous_dpi)


class HudController(QObject):
    changed = Signal()

    def __init__(self, backend, window, *, viewport_reader: Callable | None = None) -> None:
        super().__init__(window)
        self.backend = backend
        self.window = window
        self.viewport_reader = viewport_reader or ForegroundGameWindow()
        self._demo_preview = viewport_reader is not None
        self._visible = False
        self._history_a = [0.0] * 32
        self._history_b = [0.0] * 32
        self._wave_tokens: dict[str, tuple[str, float]] = {}
        self._last_sample = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.tick)
        backend.changed.connect(self._check_enabled)
        self.timer.start()

    @Property(bool, notify=changed)
    def visible(self) -> bool:
        return self._visible

    @Property("QVariantList", notify=changed)
    def historyA(self) -> list[float]:
        return list(self._history_a)

    @Property("QVariantList", notify=changed)
    def historyB(self) -> list[float]:
        return list(self._history_b)

    def _can_display(self) -> bool:
        # Fail closed for menus, costume screens and unknown scene types.
        return (self.backend.gameHudEnabled and self.backend.telemetryOnline
                and (self.backend.gameScene == "gameplay" or is_story_scene(self.backend._state)))

    def _check_enabled(self) -> None:
        if not self._can_display():
            self._hide()

    def _hide(self) -> None:
        self.window.hide()
        if self._visible:
            self._visible = False
            self._history_a = [0.0] * 32
            self._history_b = [0.0] * 32
            self._wave_tokens.clear()
            self.changed.emit()

    def _sample(self, channel: str, now: float) -> float:
        strength = self.backend.previewA if channel == "A" else self.backend.previewB
        wave = self.backend.waveA if channel == "A" else self.backend.waveB
        points = self.backend.waveAPoints if channel == "A" else self.backend.waveBPoints
        token = wave + self.backend._mapping.pulse_token(channel)
        last_token, started = self._wave_tokens.get(channel, ("", now))
        if token != last_token:
            started = now
            self._wave_tokens[channel] = (token, started)
        if not points or strength <= 0:
            return 0.0
        point = points[int(max(0, now - started) / 0.1) % len(points)]
        return max(0.0, min(1.0, point / 100 * strength / max(1, self.backend.hardCap)))

    def tick(self) -> None:
        if getattr(self.backend, "_demo", False) and not self._demo_preview:
            self._hide()
            return
        if not self._can_display():
            self._hide()
            return
        viewport = self.viewport_reader(self.backend.processId)
        if viewport is None:
            self._hide()
            return
        screen = screen_for_viewport(viewport, QGuiApplication.screens())
        if screen is None:
            self._hide()
            return
        bounds = hud_geometry(viewport, dpr=screen.devicePixelRatio(),
                              screen_x=screen.geometry().x(), screen_y=screen.geometry().y(),
                              top_aligned=is_story_scene(self.backend._state))
        if self.window.screen() != screen:
            self.window.setScreen(screen)
        if self.window.geometry() != bounds:
            self.window.setGeometry(bounds)
        if not self._visible:
            self._visible = True
            self.window.show()
            self.changed.emit()
        now = time.monotonic()
        if now - self._last_sample >= 0.1:
            self._last_sample = now
            self._history_a = self._history_a[1:] + [self._sample("A", now)]
            self._history_b = self._history_b[1:] + [self._sample("B", now)]
            self.changed.emit()

    def shutdown(self) -> None:
        self.timer.stop()
        self._hide()
