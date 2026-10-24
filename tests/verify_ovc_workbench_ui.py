"""Embedded OVC workbench QA; temporary config, fake backend, no hardware I/O."""
from copy import deepcopy
from pathlib import Path
import tempfile

from PySide6.QtCore import QObject, Property, QMetaObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from test_ovc_controller import FakeBackend
from ricca_dglab.ovc_controller import OvcController
from ricca_dglab.product_config import ProductConfig


class UiBackend(FakeBackend):
    @Property(str, constant=True)
    def uiFontFamily(self):
        return "Microsoft YaHei UI"


root = Path(__file__).resolve().parents[1]
temporary = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temporary.name) / "settings.json")
electrical = {key: deepcopy(value) for key, value in config.values.items() if key != "ovc_profile"}
app = QGuiApplication([])
backend = UiBackend(config)
controller = OvcController(backend)
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.rootContext().setContextProperty("ovcController", controller)
engine.loadData(b'''import QtQuick
import QtQuick.Controls
ApplicationWindow {
    visible: true; width: 1050; height: 740; color: "#111a14"
    OvcWorkbench { id: workbench; anchors.fill: parent; anchors.margins: 20; controller: ovcController }
}''', QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/OvcWorkbenchVerification.qml")))
assert engine.rootObjects(), "OVC workbench QML failed to load"
window = engine.rootObjects()[0]
workbench = window.findChild(QObject, "ovcWorkbenchPage")
assert workbench is not None
result = 1


def strength():
    assert not workbench.property("dialogMode")
    assert workbench.property("draftCap") == controller.hardCap


def strategy():
    workbench.findChild(QObject, "ovcStrategySectionButton").clicked.emit()


def queue():
    workbench.findChild(QObject, "ovcQueueSectionButton").clicked.emit()


def nested_strategy():
    workbench.findChild(QObject, "openOvcStrategyA").clicked.emit()


def english_small():
    workbench.findChild(QObject, "ovcChannelStrategyDialog").close()
    backend._config.values["language"] = "en"
    backend.languageChanged.emit()
    workbench.findChild(QObject, "ovcStrengthSectionButton").clicked.emit()
    window.setWidth(896)
    window.setHeight(616)


def japanese_small():
    backend._config.values["language"] = "ja"
    backend.languageChanged.emit()
    workbench.findChild(QObject, "ovcStrategySectionButton").clicked.emit()


def unsaved_queue_confirmation():
    backend._config.values["language"] = "zh"
    backend.languageChanged.emit()
    editor = workbench.findChild(QObject, "ovcStoryQueueEditor")
    editor.setProperty("dirty", True)
    assert QMetaObject.invokeMethod(workbench, "requestClose")
    confirmation = workbench.findChild(QObject, "ovcResetConfirmation")
    assert confirmation.property("visible")


steps = [(strength, "ovc-workbench-strength.png"), (strategy, "ovc-workbench-patterns.png"),
         (queue, "ovc-workbench-queue.png"), (nested_strategy, "ovc-workbench-strategy.png"),
         (english_small, "ovc-workbench-strength-en-small.png"),
         (japanese_small, "ovc-workbench-patterns-ja-small.png"),
         (unsaved_queue_confirmation, "ovc-workbench-discard-confirmation.png")]


def run(index=0):
    global result
    if index == len(steps):
        result = 0
        app.quit()
        return
    action, filename = steps[index]
    try:
        action()
    except Exception:
        import traceback
        traceback.print_exc()
        app.quit()
        return

    def capture():
        assert {key: value for key, value in config.values.items()
                if key not in {"ovc_profile", "language"}} == {
                    key: value for key, value in electrical.items() if key != "language"}
        assert window.grabWindow().save(str(root / "artifacts" / filename))
        run(index + 1)
    QTimer.singleShot(350, capture)


QTimer.singleShot(200, run)
app.exec()
temporary.cleanup()
raise SystemExit(result)
