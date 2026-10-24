"""Immediate story-switch UI/persistence QA; temporary config and no sockets."""
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QObject, QMetaObject, QTimer, QUrl, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

root = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
temp = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temp.name) / "settings.json")
config.values["onboarding_completed"] = True
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
        patch("ricca_dglab.backend.TelemetryWorker.start"), \
        patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._pulse_route_paused = backend._ovc_route_paused = True
backend._device_connected = backend._ovc_connected = True
original = deepcopy(config.values)
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda items: warnings.extend(str(item) for item in items))
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
result = 1
cases = [(language, device, width, height) for language in ("zh", "en", "ja")
         for device in ("pulse", "ovc") for width, height in ((1360, 900), (1120, 720))]


def run(index=0):
    global result
    if index == len(cases):
        assert not warnings, "\n".join(warnings)
        assert backend._bridge._loop is None and backend._v4_hub._loop is None
        print("Story switch UI: 12 language/device/size cases, immediate save/off and route pause preserved; no hardware output.", flush=True)
        result = 0
        app.quit()
        return
    language, device, width, height = cases[index]
    backend.setLanguage(language)
    window.setWidth(width);window.setHeight(height)
    window.setProperty("pageIndex", 3 if device == "pulse" else 8)
    workbench = window.findChild(QObject, device + "WorkbenchPage")
    QMetaObject.invokeMethod(workbench, "showQueue", Q_ARG("QVariant", "A"))
    controller = backend if device == "pulse" else backend.ovcController
    controller.setStoryQueueEnabled("A", True)

    def capture():
        editor = workbench.findChild(QObject, device + "StoryQueueEditor")
        toggle = editor.findChild(QObject, "storyQueueEnabled")
        assert toggle.property("checked")
        before_queues = deepcopy(controller.storyQueues)
        before_b = deepcopy(controller.channelPolicies["B"])
        # Keep an unsaved segment edit: the switch must not save/discard it.
        editor.setProperty("dirty", True)
        toggle.setProperty("checked", False)
        toggle.toggled.emit()
        assert not controller.channelPolicies["A"]["rules"]["defeat_interaction"]["enabled"]
        assert not toggle.property("checked")
        assert editor.property("dirty")
        assert controller.storyQueues == before_queues
        assert controller.channelPolicies["B"] == before_b
        assert backend.pulseRoutePaused and backend.ovcRoutePaused
        restored = ProductConfig(config.path).values
        policies = restored["channel_policies"] if device == "pulse" else restored["ovc_profile"]["channel_policies"]
        assert not policies["A"]["rules"]["defeat_interaction"]["enabled"]
        assert workbench.findChild(QObject, device + "WorkbenchOutputToggle").property("text") in {"启用 Pulse", "启用振动"}
        toast = window.findChild(QObject, "saveToast")
        toast.close()
        editor.setProperty("dirty", False)
        def save():
            assert window.grabWindow().save(str(root / "artifacts" / f"story-switch-{device}-{language}-{width}.png"))
            run(index + 1)
        QTimer.singleShot(160, save)
    QTimer.singleShot(300, capture)


QTimer.singleShot(300, run)
QTimer.singleShot(30000, app.quit)
app.exec()
backend.shutdown()
engine.deleteLater()
temp.cleanup()
raise SystemExit(result)
