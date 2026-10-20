"""Connection error/QR/address UI QA without sockets, audio or user writes."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch, MagicMock

from PySide6.QtCore import QObject, QTimer, QUrl, QPointF
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

project = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
engine = QQmlApplicationEngine()
temporary = tempfile.TemporaryDirectory(dir=project)
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values["onboarding_completed"] = True
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
bridge = backend._bridge
bridge.available_lan_ips = ("192.168.124.33", "10.8.0.2")
bridge.available_lan_interfaces = [
    {"address": "192.168.124.33", "label": "Ethernet · 192.168.124.33"},
    {"address": "10.8.0.2", "label": "VPN adapter · 10.8.0.2（虚拟/VPN）"},
]
bridge.refresh_lan_ips = lambda: None
backend._lan_addresses = list(bridge.available_lan_ips)
backend._lan_ip = bridge.lan_ip = bridge.available_lan_ips[0]
backend._apply_bridge({"event": "server_error", "detail": "端口 9999 已被占用。请关闭重复窗口，或点“连接不上？”查看占用进程。"})
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(project / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
window.setProperty("pageIndex", 1)
help_dialog = window.findChild(QObject, "connectionHelpDialog")
result = 1


def find(name):
    pending = [window, help_dialog.property("contentItem")]
    seen = set()
    while pending:
        item = pending.pop()
        if item is None or item in seen:
            continue
        seen.add(item)
        if item.objectName() == name:
            return item
        pending.extend(item.children())
        if isinstance(item, QQuickItem):
            pending.extend(item.childItems())
    raise AssertionError(name)


def shot(name):
    assert window.grabWindow().save(str(project / "artifacts" / name))


def fail():
    import traceback
    traceback.print_exc()
    app.quit()


def step_error():
    try:
        assert "不可用" in find("connectionQrPlaceholder").property("text")
        assert find("outputPauseButton").property("label") == "恢复输出"
        shot("connection-port-conflict.png")
        window.setWidth(1120)
        window.setHeight(720)
        QTimer.singleShot(350, step_minimum)
    except Exception:
        fail()


def step_minimum():
    try:
        image = find("connectionQrImage")
        point = image.mapToScene(QPointF(0, 0))
        assert point.x() > 0 and point.x() + image.width() < window.width()
        assert point.y() > 74 and point.y() + image.height() < window.height()
        shot("connection-port-conflict-minimum.png")
        with patch("ricca_dglab.backend.port_listeners", return_value=[{"pid": 1234, "name": "pythonw.exe", "ours": False}]):
            find("connectionHelpButton").clicked.emit()
        assert help_dialog.property("visible")
        assert "1234" in backend.connectionDiagnostics
        QTimer.singleShot(200, step_help)
    except Exception:
        fail()


def step_help():
    try:
        shot("connection-help-dialog.png")
        help_dialog.close()
        bridge.server_ready = True
        bridge.controller_id = "qa-controller"
        backend._apply_bridge({"event": "ready", "lan_ip": bridge.lan_ip, "port": 9999,
                               "qr_url": bridge._build_qr_url()})
        old_qr = backend.qrSource
        choice = find("connectionAddressChoice")
        choice.setProperty("currentIndex", 1)
        choice.activated.emit(1)
        backend._drain()
        assert backend.lanAddress == "10.8.0.2"
        assert "ws://10.8.0.2:9999/" in backend.qrUrl
        assert backend.qrSource and backend.qrSource != old_qr
        assert not backend.outputArmed and backend.serverError == ""
        QTimer.singleShot(250, step_ready)
    except Exception:
        fail()


def step_ready():
    try:
        assert not find("connectionQrPlaceholder").property("visible")
        shot("connection-address-switched.png")
        # No Socket thread: production eligibility, simulated handshake only.
        backend._bridge = MagicMock()
        backend._demo = False
        backend.toggleOutputPause()
        backend._apply_state({"state": {"connected": True, "status": "ok", "build_supported": True,
                              "scene": "atd", "story": {"asset_name": "ADV/test.csv"}},
                              "received_at": time.monotonic(), "latency_ms": 1})
        backend._apply_bridge({"event": "connected"})
        backend._drain()
        backend.changed.emit()
        assert backend.outputArmed and not backend.deviceTestsComplete
        window.setWidth(1360)
        window.setHeight(860)
        QTimer.singleShot(250, step_connected)
    except Exception:
        fail()


def step_connected():
    global result
    try:
        assert find("outputPauseButton").property("label") == "暂停输出"
        notice = find("automaticOutputNotice")
        assert "连接后自动同步" in notice.property("text")
        assert notice.mapToScene(QPointF()).x() > 250
        shot("connection-automatic-output.png")
        backend.emergencyStop()
        backend._drain()
        assert find("outputPauseButton").property("label") == "恢复输出"
        backend._bridge.set_auto_enabled.assert_called_with(False)
        print("Connection diagnostics, QR, automatic output and emergency resume UI: OK")
        result = 0
    except Exception:
        fail()
    app.quit()


QTimer.singleShot(300, step_error)
QTimer.singleShot(6000, app.quit)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
temporary.cleanup()
sys.exit(result)
