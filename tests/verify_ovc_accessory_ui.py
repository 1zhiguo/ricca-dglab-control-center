"""Accessory guidance screenshots with fake state; no sockets or device output."""
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch

from PySide6.QtCore import QObject, QTimer, QUrl
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
original = deepcopy(config.values)
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
        patch("ricca_dglab.backend.TelemetryWorker.start"), \
        patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._stop_latched = backend._user_output_paused = False
backend._v4_hub.app_connected = True
backend._ovc_bridge.selected_client_id = "fake-app"
backend._ovc_bridge.selected_slot_id = "fake-ovc"
device = {"clientId": "fake-app", "slotId": "fake-ovc", "type": "OVC_1",
          "label": "OVC · OVC_1", "channelAReason": "accessory-not-inserted",
          "channelBReason": "accessory-not-inserted"}
backend._v4_devices = [device]
backend._ovc_connected = False
assert "A 或 B" in backend.ovcAccessoryHint
for missing, other in (("A", "B"), ("B", "A")):
    device["channel" + other + "Reason"] = ""
    device["channel" + missing + "Reason"] = "accessory-not-inserted"
    assert backend.ovcAccessoryHint.startswith(missing + " 口")
device["channelAReason"] = device["channelBReason"] = ""
assert backend.ovcAccessoryHint == ""
device["channelAReason"] = device["channelBReason"] = "accessory-not-inserted"
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda items: warnings.extend(str(item) for item in items))
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
window.setProperty("pageIndex", 1)
window.setWidth(1120)
window.setHeight(720)
result = 1


def run(index=0):
    global result
    if index == 3:
        assert not warnings, warnings
        # Only the explicitly selected preview language may change in memory.
        assert {k: v for k, v in config.values.items() if k != "language"} == {
            k: v for k, v in original.items() if k != "language"}
        print("OVC accessory UI: 3 languages passed; no device I/O.", flush=True)
        result = 0
        app.quit()
        return
    language = ("zh", "en", "ja")[index]
    backend.setLanguage(language)
    backend.devicesChanged.emit()
    backend.changed.emit()

    def capture():
        toast = window.findChild(QObject, "saveToast")
        if toast:
            toast.close()
        hint = window.findChild(QQuickItem, "ovcRouteStatus")
        card = window.findChild(QQuickItem, "ovcConnectionCard")
        button = window.findChild(QObject, "ovcRoutePauseButton")
        assert hint.property("sourceText") == backend.ovcAccessoryHint
        assert button.property("unavailable")
        assert button.property("label") == "无法启用 · 查看原因"
        button.clicked.emit()
        toast = window.findChild(QObject, "saveToast")
        assert toast.property("heading") == "暂时无法启用"
        assert toast.property("message") == backend.ovcEnableReason
        assert backend.ovcRoutePaused and not backend._ovc_plan.allowed
        toast.close()
        assert hint.height() >= hint.property("contentHeight") - 1
        assert hint.y() + hint.height() < card.height() - 50
        flickable = card.parentItem()
        while flickable and not flickable.inherits("QQuickFlickable"):
            flickable = flickable.parentItem()
        flickable.setProperty("contentY", max(0, flickable.property("contentHeight") - flickable.height()))
        QTimer.singleShot(150, save)

    def save():
        assert window.grabWindow().save(str(root / "artifacts" / f"ovc-accessory-{language}.png"))
        run(index + 1)

    QTimer.singleShot(300, capture)


QTimer.singleShot(300, run)
app.exec()
backend.shutdown()
engine.deleteLater()
temporary.cleanup()
raise SystemExit(result)
