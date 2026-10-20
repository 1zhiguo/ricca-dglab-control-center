"""Verify mandatory manual cap entry and saved onboarding in real QML."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from PySide6.QtCore import QObject, QTimer, QUrl
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
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(project / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
guide = window.findChild(QObject, "onboardingDialog")
window.setProperty("showOnboardingOnStart", True)
result = 1


def find(name):
    pending = [window, guide.property("contentItem")]
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


def step_start():
    try:
        assert guide.property("visible") and not backend.onboardingCompleted
        assert find("onboardingCapInput").property("text") == ""
        shot("onboarding-overview.png")
        find("onboardingNext").clicked.emit()
        QTimer.singleShot(150, step_tour)
    except Exception:
        fail()


def step_tour():
    try:
        index = guide.property("step")
        assert window.property("pageIndex") == (0, 1, 2, 3, 2)[index]
        if index < 4:
            shot("onboarding-step-" + str(index + 1) + ".png")
            find("onboardingNext").clicked.emit()
            QTimer.singleShot(150, step_tour)
            return
        assert not find("onboardingNext").property("enabled")
        window.setWidth(1120)
        window.setHeight(720)
        QTimer.singleShot(200, step_cap)
    except Exception:
        fail()


def step_cap():
    try:
        shot("onboarding-hard-cap-minimum.png")
        field = find("onboardingCapInput")
        field.setProperty("text", "101")
        assert not find("onboardingNext").property("enabled")
        field.setProperty("text", "0")
        assert find("onboardingNext").property("enabled")
        find("onboardingNext").clicked.emit()
        assert not guide.property("visible")
        restored = ProductConfig(config.path)
        assert restored.values["hard_cap"] == 0 and restored.values["onboarding_completed"]
        assert backend.hardCap == 0 and not backend.outputArmed
        # Rewatch is available and requires a fresh explicit entry to save again.
        find("onboardingHelpButton").clicked.emit()
        assert guide.property("visible") and guide.property("step") == 0
        assert field.property("text") == ""
        for _ in range(4):
            find("onboardingNext").clicked.emit()
        field.setProperty("text", "42")
        QTimer.singleShot(200, step_save)
    except Exception:
        fail()


def step_save():
    global result
    try:
        shot("onboarding-hard-cap-entered.png")
        find("onboardingNext").clicked.emit()
        restored = ProductConfig(config.path)
        assert restored.values["hard_cap"] == backend.hardCap == 42
        assert restored.values["onboarding_completed"]
        assert backend._mapping.hard_cap == 42 and not backend.outputArmed
        print("Onboarding navigation, blank/invalid input, zero cap, persisted apply and rewatch: OK")
        result = 0
    except Exception:
        fail()
    app.quit()


QTimer.singleShot(300, step_start)
QTimer.singleShot(6000, app.quit)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
temporary.cleanup()
sys.exit(result)
