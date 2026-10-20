"""Exercise channel editing without sockets, game access or user settings writes."""
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
config.values["onboarding_completed"] = True
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
        patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(project / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
window.setProperty("pageIndex", 3)
window.setProperty("strategyOnStart", "A")
dialog = window.findChild(QObject, "channelStrategyDialog")
result = 1


def child(name):
    pending = [dialog, dialog.property("contentItem")]
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


def capture(name):
    assert window.grabWindow().save(str(project / "artifacts" / name))


def step_one():
    global result
    try:
        mode = child("channelModeChoice")
        mode.setProperty("currentIndex", 2)
        mode.activated.emit(2)
        assert all(row["key"] != "guard" for row in dialog.property("ruleRows").toVariant())
        assert child("defeat_scene_enterDuration").property("visible")
        assert not child("defeat_interactionDuration").property("visible")
        entry_duration = child("defeat_scene_enterDuration")
        entry_duration.setProperty("value", 1.7)
        entry_duration.moved.emit()
        QTimer.singleShot(150, step_two)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_two():
    global result
    try:
        choice = child("damage_lightStrengthChoice")
        choice.setProperty("currentIndex", 4)
        choice.activated.emit(4)
        strength = child("damage_lightCustomStrength")
        strength.setProperty("value", 17)
        strength.moved.emit()
        duration = child("damage_lightDuration")
        duration.setProperty("value", 0.1)
        duration.moved.emit()
        QTimer.singleShot(150, step_three)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_three():
    global result
    try:
        assert child("damage_lightStrengthChoice").property("currentIndex") == 4
        assert child("damage_lightCustomStrength").property("value") == 17
        capture("channel-a-both-custom.png")
        wave_choice = child("damage_lightWaveChoice")
        popup = engine.newQObject(wave_choice).property("popup")
        popup.property("open").callWithInstance(popup)
        QTimer.singleShot(200, step_popup)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_popup():
    global result
    try:
        wave_choice = child("damage_lightWaveChoice")
        popup = engine.newQObject(wave_choice).property("popup")
        capture("channel-wave-dropdown-preview.png")
        popup.property("close").callWithInstance(popup)
        wave_index = next(index for index, item in enumerate(backend.waveformCatalog) if item["key"] == "guard")
        wave_choice.setProperty("currentIndex", wave_index)
        wave_choice.activated.emit(wave_index)
        dialog.save()
        saved = ProductConfig(config.path).values["channel_policies"]
        assert saved["A"]["mode"] == "both"
        assert saved["A"]["rules"]["damage_light"]["duration"] == 0.1
        assert saved["A"]["rules"]["damage_light"]["custom_strength"] == 17
        assert saved["A"]["rules"]["damage_light"]["wave"] == "guard"
        assert saved["B"]["mode"] == "action"
        dialog.openChannel("B")
        window.setWidth(1120)
        window.setHeight(720)
        QTimer.singleShot(200, step_four)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_four():
    global result
    try:
        capture("channel-b-minimum-window.png")
        mode = child("channelModeChoice")
        mode.setProperty("currentIndex", 3)
        mode.activated.emit(3)
        QTimer.singleShot(150, step_five)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_five():
    global result
    try:
        capture("channel-b-audio.png")
        dialog.save()
        saved = ProductConfig(config.path).values["channel_policies"]
        assert saved["B"]["mode"] == "audio"
        assert saved["A"]["rules"]["defeat_scene_enter"]["duration"] == 1.7
        assert saved["B"]["rules"]["defeat_scene_enter"]["duration"] == 2.8
        assert saved["A"]["rules"]["defeat_interaction"]["duration"] is None
        assert saved["A"]["rules"]["damage_light"]["custom_strength"] == 17
        print("QML channel save, routing, custom strength, 0.1s duration and independent A/B persistence: OK")
        backend._timer.stop()
        backend._state = {"scene": "atd", "story": {"asset_name": "ADV/Scene3D_RiccaHellplant/Scene3D_RiccaHellplant.csv"}}
        backend.changed.emit()
        dialog.close()
        window.setProperty("pageIndex", 6)
        QTimer.singleShot(200, step_six)
        return
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
    app.quit()


def step_six():
    global result
    try:
        capture("audio-atd-scene-check.png")
        assert backend.storySceneActive
        result = 0
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
    app.quit()


QTimer.singleShot(500, step_one)
QTimer.singleShot(10000, app.quit)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
temporary.cleanup()
sys.exit(result)
