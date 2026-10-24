"""Render readiness states with fake telemetry/Apps; no network or hardware.

Run manually with PYTHONPATH=src. Screenshots cover six states, two
window sizes and Chinese/English/Japanese, using a throwaway config directory.
"""
from pathlib import Path
import tempfile
import time
import traceback
from unittest.mock import patch

from PySide6.QtCore import QObject, QPointF, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig


root = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values.update(onboarding_completed=True, socket_protocol="v4")
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
        patch("ricca_dglab.backend.TelemetryWorker.start"), \
        patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._user_output_paused = True
backend._stop_latched = True
hub = backend._v4_hub
hub.server_ready = True
hub.controller_id = "readiness-ui-mock"
hub.qr_url = hub._build_qr_url()
backend._apply_bridge({"event": "ready", "role": "hub", "protocol": "v4",
                       "qr_url": hub.qr_url, "port": 9998, "lan_ip": hub.lan_ip})
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda items: warnings.extend(str(item) for item in items))
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects(), "Control Center QML did not load"
window = engine.rootObjects()[0]
window.setProperty("pageIndex", 1)
artifacts = root / "artifacts"
artifacts.mkdir(exist_ok=True)
result = 1
cases = [(language, width, height, name, game, phone)
         for language in ("zh", "en", "ja")
         for width, height in ((1360, 900), (1120, 720))
         for name, game, phone in (("none", False, False), ("game-only", True, False),
                                   ("app-unselected", False, True), ("app-only", False, True), ("both", True, True),
                                   ("disconnected", False, False), ("inactive-v4", False, False))]


def apply_state(language, width, height, name, game, phone):
    backend._config.values["socket_protocol"] = "v3" if name == "inactive-v4" else "v4"
    backend.setLanguage(language)
    window.setWidth(width)
    window.setHeight(height)
    backend._last_received = time.monotonic() if game else 0
    backend._reader_error = ""
    backend._state = {"status": "ok" if game else "disconnected", "connected": game,
                      "process_id": 42 if game else 0, "build_supported": True,
                      "scene": "gameplay" if game else "none", "current_hp": 31,
                      "max_hp": 31, "current_mp": 50, "max_mp": 50,
                      "player_address": "0x123" if game else None,
                      "stage": {"name": "StageName_07", "all_resource_loaded": True},
                      "game_ui": {"is_user_pause": False}}
    hub.app_connected = phone or name == "inactive-v4"
    routes_connected = phone and name != "app-unselected"
    backend._device_connected = backend._ovc_connected = routes_connected
    backend._bridge.connected = backend._ovc_bridge.connected = routes_connected
    backend._ovc_status = "负鼠已就绪" if phone else "负鼠未连接"
    # Listening is not a phone connection: this remains True even in `none`.
    backend._server_ready = True
    backend.changed.emit()
    toast = window.findChild(QObject, "saveToast")
    if toast:
        toast.close()


def item(name):
    found = window.findChild(QQuickItem, name)
    assert found is not None, f"Missing UI object: {name}"
    return found


def assert_readiness(card, expected):
    assert card.property("readiness") == expected, (card.objectName(), card.property("readiness"), expected)
    assert bool(card.property("connectionReady")) == (expected == 2), card.objectName()
    assert bool(card.property("glowActive")) == (expected == 2), card.objectName()
    color = card.property("glowColor")
    assert color is not None and color.isValid(), card.objectName()
    expected_color = card.property("accent") if expected == 2 else window.property("yellow" if expected == 1 else "border")
    assert color.rgba() == expected_color.rgba(), card.objectName()


def assert_geometry():
    game, socket = item("gameTelemetryCard"), item("socketConnectionCard")
    pulse, ovc = item("pulseConnectionCard"), item("ovcConnectionCard")
    for card in (game, socket, pulse, ovc):
        assert card.width() > 260 and card.height() > 100, card.objectName()
        assert card.x() >= -1, card.objectName()
        assert card.x() + card.width() <= card.parentItem().width() + 1, card.objectName()
    assert socket.x() >= game.x() + game.width() + 8, "Top cards overlap"
    assert ovc.x() >= pulse.x() + pulse.width() + 8, "Controller cards overlap"
    for top in (game, socket):
        top_bottom = top.mapToItem(pulse.parentItem(), 0, top.height()).y()
        assert top_bottom + 8 <= pulse.y(), "Telemetry and QR must be above controller configuration"
    assert item("ovcWorkbenchNavButton").isVisible(), "OVC must have its own sidebar destination"
    sidebar = item("sidebarStatusCard")
    assert sidebar.isVisible()
    assert sidebar.mapToScene(QPointF(0, sidebar.height())).y() <= window.height() + 1, "Sidebar status is clipped"


def run(index=0):
    global result
    if index == len(cases):
        assert not warnings, "QML warnings:\n" + "\n".join(warnings)
        print(f"Readiness UI: {len(cases)} state/size/language screenshots passed; no sockets or outputs.", flush=True)
        result = 0
        app.quit()
        return
    case = cases[index]
    language, width, height, name, game, phone = case
    try:
        apply_state(*case)
    except Exception:
        traceback.print_exc()
        app.quit()
        return

    def capture():
        try:
            backend._last_received = time.monotonic() if game else 0
            backend.changed.emit()
            assert bool(backend.telemetryReady) == game
            assert_readiness(item("gameTelemetryCard"), 2 if game else 0)
            assert_readiness(item("socketConnectionCard"), 2 if phone else 0)
            routes_connected = phone and name != "app-unselected"
            route_state = 2 if game and routes_connected else 1 if routes_connected else 0
            assert_readiness(item("pulseConnectionCard"), route_state)
            assert_readiness(item("ovcConnectionCard"), route_state)
            assert_geometry()
            assert backend._bridge._loop is None and hub._loop is None
            assert not backend._output_armed and not backend._ovc_plan.allowed
            assert backend._stop_latched and backend._user_output_paused
            assert window.grabWindow().save(str(artifacts / f"readiness-{language}-{width}-{name}.png"))
            run(index + 1)
        except Exception:
            traceback.print_exc()
            app.quit()
    QTimer.singleShot(400, capture)


QTimer.singleShot(250, run)
app.exec()
backend.shutdown()
engine.deleteLater()
temporary.cleanup()
raise SystemExit(result)
