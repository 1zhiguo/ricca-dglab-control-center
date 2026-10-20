"""Render the real HUD without connecting to a game or a DG-LAB device."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.hud import ForegroundGameWindow, GameViewport, HudController, hud_geometry, screen_for_viewport
from ricca_dglab.product_config import ProductConfig


project = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
engine = QQmlApplicationEngine()
temporary = tempfile.TemporaryDirectory(dir=project)
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values["onboarding_completed"] = True
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
        patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._state = {"scene": "gameplay"}
backend._last_received = time.monotonic()
backend._preview_a = 15
backend._preview_b = 25
backend._wave_a = "impact"
backend._wave_b = "heavy_land"
engine.rootContext().setContextProperty("backend", backend)
qml = project / "src/ricca_dglab/qml"
engine.load(QUrl.fromLocalFile(str(qml / "ControlCenter.qml")))
main = engine.rootObjects()[0]
engine.load(QUrl.fromLocalFile(str(qml / "GameHud.qml")))
window = engine.rootObjects()[1]
screen = app.primaryScreen()
ratio = screen.devicePixelRatio()
virtual_game = GameViewport(
    round(screen.geometry().x() * ratio), round(screen.geometry().y() * ratio),
    round(1280 * ratio), round(720 * ratio),
    round(screen.geometry().x() * ratio), round(screen.geometry().y() * ratio), screen.name(),
)
viewport = [virtual_game]
controller = HudController(backend, window, viewport_reader=lambda pid: viewport[0])
controller.timer.stop()
window.setProperty("controller", controller)
result = 1


def capture():
    global result
    try:
        backend._last_received = time.monotonic()
        if sys.platform == "win32":
            reader = ForegroundGameWindow()
            # Read a real owned Qt window's Win32 client geometry without
            # changing the user's foreground window to obtain that handle.
            reader.api.GetForegroundWindow = lambda: int(main.winId())
            actual = reader(os.getpid())
            assert actual is not None
            assert screen_for_viewport(actual, app.screens()) == main.screen(), (actual, [value.name() for value in app.screens()])
            assert abs(actual.width - round(main.width() * main.screen().devicePixelRatio())) <= 2
        controller.tick()
        assert window.isVisible()
        required = Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.Tool
        assert window.flags() & required == required
        if sys.platform == "win32":
            api = ctypes.WinDLL("user32", use_last_error=True)
            api.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            api.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            styles = api.GetWindowLongPtrW(int(window.winId()), -20)
            assert styles & 0x20, "WS_EX_TRANSPARENT missing"
            assert styles & 0x08000000, "WS_EX_NOACTIVATE missing"
            assert styles & 0x80, "WS_EX_TOOLWINDOW missing"
        controller._history_a = [0,.1,.3,.7,.8,.5,.2,0] * 4
        controller._history_b = [0,.8,.1,.5,.1,.9,.2,0] * 4
        controller.changed.emit()
        QTimer.singleShot(200, capture_frame)
    except Exception:
        import traceback
        traceback.print_exc()
        app.quit()


def capture_frame():
    global result
    try:
        assert window.grabWindow().save(str(project / "artifacts/hud-overlay-preview.png"))
        assert main.grabWindow().save(str(project / "artifacts/hud-toolbar-check.png"))
        for scene in ("none", "other", "unknown"):
            backend._state["scene"] = scene
            backend.changed.emit()
            assert not window.isVisible(), scene
            controller.tick()
            assert not window.isVisible(), scene
        backend._state["scene"] = "adv"
        backend._last_received = time.monotonic()
        controller.tick()
        assert window.isVisible()
        assert window.geometry() == hud_geometry(
            virtual_game, dpr=ratio, screen_x=screen.geometry().x(),
            screen_y=screen.geometry().y(), top_aligned=True)
        QTimer.singleShot(150, capture_story)
    except Exception:
        import traceback
        traceback.print_exc()
        app.quit()


def capture_story():
    try:
        assert window.grabWindow().save(str(project / "artifacts/hud-story-top-preview.png"))
        backend._state["scene"] = "gameplay"
        backend._last_received = time.monotonic()
        controller.tick()
        assert window.geometry() == hud_geometry(
            virtual_game, dpr=ratio, screen_x=screen.geometry().x(),
            screen_y=screen.geometry().y())
        assert backend.setGameHudEnabled(False)
        assert not window.isVisible()
        assert not ProductConfig(config.path).values["game_hud_enabled"]
        assert backend.setGameHudEnabled(True)
        backend._last_received = time.monotonic()
        controller.tick()
        assert window.isVisible()
        viewport[0] = None
        controller.tick()
        assert not window.isVisible()
        main.setWidth(1120)
        main.setHeight(720)
        QTimer.singleShot(150, capture_minimum)
    except Exception:
        import traceback
        traceback.print_exc()
        app.quit()


def capture_minimum():
    global result
    try:
        assert main.grabWindow().save(str(project / "artifacts/hud-toolbar-minimum.png"))
        print("HUD render, scene filtering, ADV top/gameplay bottom, native click-through styles, persisted toggle and focus hiding: OK")
        result = 0
    finally:
        app.quit()


QTimer.singleShot(150, capture)
QTimer.singleShot(6000, app.quit)
app.aboutToQuit.connect(controller.shutdown)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
temporary.cleanup()
sys.exit(result)
