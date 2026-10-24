"""Render independent OVC settings using temporary config, no runtime or sockets."""
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
app = QGuiApplication([])
backend = UiBackend(config)
controller = OvcController(backend)
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.rootContext().setContextProperty("ovcController", controller)
engine.loadData(b'''import QtQuick
import QtQuick.Controls
ApplicationWindow {
    visible: true; width: 1280; height: 900; color: "#111a14"
    OvcConfigDialog { id: dialog; controller: ovcController }
}''', QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/OvcDialogVerification.qml")))
assert engine.rootObjects(), "OVC dialog QML failed to load"
window = engine.rootObjects()[0]
dialog = window.findChild(QObject, "ovcConfigDialog")
assert dialog is not None
result = 1


def strength():
    assert QMetaObject.invokeMethod(dialog, "openSettings")


def strategy():
    dialog.setProperty("section", "strategy")


def queue():
    dialog.setProperty("section", "queue")


def nested_strategy():
    dialog.setProperty("section", "strategy")
    button = dialog.findChild(QObject, "openOvcStrategyA")
    assert button is not None
    button.clicked.emit()


def english():
    dialog.findChild(QObject, "ovcChannelStrategyDialog").close()
    backend._config.values["language"] = "en"
    backend.languageChanged.emit()
    dialog.setProperty("section", "strength")


def japanese_small():
    backend._config.values["language"] = "ja"
    backend.languageChanged.emit()
    window.setWidth(1120)
    window.setHeight(720)


steps = [(strength, "ovc-independent-strength.png"), (strategy, "ovc-independent-patterns.png"),
         (queue, "ovc-independent-queue.png"), (nested_strategy, "ovc-independent-strategy.png"),
         (english, "ovc-independent-strength-en.png"), (japanese_small, "ovc-independent-strength-ja-small.png")]


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
        assert window.grabWindow().save(str(root / "artifacts" / filename))
        run(index + 1)
    QTimer.singleShot(350, capture)


QTimer.singleShot(200, run)
app.exec()
temporary.cleanup()
raise SystemExit(result)
