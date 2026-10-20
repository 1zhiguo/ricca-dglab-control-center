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
original_b_entry_duration = config.values["channel_policies"]["B"]["rules"]["player_down"]["duration"]
original_b_mode = config.values["channel_policies"]["B"]["mode"]
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
        modes = dialog.property("modes").toVariant()
        assert not any(item["key"] in {"audio", "action_audio"} for item in modes)
        mode.setProperty("currentIndex", 2)
        mode.activated.emit(2)
        child("strategyStoryTab").clicked.emit()
        assert dialog.property("category") == "story"
        story = child("storyModeChoice")
        assert story.property("count") == 6
        for index, key in enumerate(("fixed", "queue", "audio", "fixed_audio", "queue_audio", "off")):
            story.setProperty("currentIndex", index)
            story.activated.emit(index)
            assert dialog.property("draft").toVariant()["story_mode"] == key
        story.setProperty("currentIndex", 0)
        story.activated.emit(0)
        child("strategyBattleTab").clicked.emit()
        assert dialog.property("category") == "battle"
        original_draft = dialog.property("draft").toVariant()
        expected = {"hp":{"damage_light", "damage_medium", "damage_heavy"},
                    "action":{"struggle", "hit_small", "hit_normal", "heavy_land", "wall_bounce", "boss_catch"},
                    "penalty":{"player_down", "armor_break"}}
        for key, keys in expected.items():
            child("battleFilter_" + key).clicked.emit()
            assert {row["key"] for row in dialog.property("ruleRows").toVariant()} == keys
            assert dialog.property("draft").toVariant() == original_draft
        child("battleFilter_all").clicked.emit()
        assert not any(row["key"] == "defeat_interaction" for row in dialog.property("ruleRows").toVariant())
        assert all(row["key"] != "guard" for row in dialog.property("ruleRows").toVariant())
        assert child("player_downDuration").property("visible")
        assert child("player_downDuration").property("to") == 10
        assert child("armor_breakDuration").property("to") == 5
        assert not child("struggleDuration").property("visible")
        assert not any(row["key"] in {"capture_start", "defeat_scene_enter"}
                       for row in dialog.property("ruleRows").toVariant())
        assert not child("defeat_interactionDuration").property("visible")
        entry_duration = child("player_downDuration")
        entry_duration.setProperty("value", 1.7)
        entry_duration.moved.emit()
        child("strategyStoryTab").clicked.emit()
        QTimer.singleShot(150, step_story_preview)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_story_preview():
    global result
    try:
        capture("channel-story-category-fixed.png")
        story = child("storyModeChoice")
        story.setProperty("currentIndex", 4)
        story.activated.emit(4)
        assert dialog.property("selectedMode") == "both"
        QTimer.singleShot(150, step_story_queue_preview)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_story_queue_preview():
    global result
    try:
        capture("channel-story-category-queue-audio.png")
        story = child("storyModeChoice")
        story.setProperty("currentIndex", 0)
        story.activated.emit(0)
        child("strategyBattleTab").clicked.emit()
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
        target = child("struggleDuration")
        flickable = target.parentItem()
        while flickable and not flickable.inherits("QQuickFlickable"):
            flickable = flickable.parentItem()
        assert flickable is not None
        position = target.mapToItem(flickable, 0, 0).y() + flickable.property("contentY")
        flickable.setProperty("contentY", max(0, position - 150))
        QTimer.singleShot(100, step_capture_hold)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_capture_hold():
    global result
    try:
        capture("channel-capture-hold.png")
        child("battleFilter_penalty").clicked.emit()
        QTimer.singleShot(150, step_penalty_filter)
    except Exception:
        import traceback
        traceback.print_exc()
        result = 1
        app.quit()


def step_penalty_filter():
    global result
    try:
        capture("channel-battle-penalty-filter.png")
        child("battleFilter_all").clicked.emit()
        wave_choice = child("damage_lightWaveChoice")
        flickable = wave_choice.parentItem()
        while flickable and not flickable.inherits("QQuickFlickable"):
            flickable = flickable.parentItem()
        flickable.setProperty("contentY", 0)
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
        assert saved["B"]["mode"] == original_b_mode
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
        assert dialog.property("selectedMode") == "action"
        assert dialog.property("selectedStoryMode") == "queue_audio"
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
        assert saved["B"]["mode"] == "none"
        assert saved["B"]["story_mode"] == "queue_audio"
        assert saved["A"]["rules"]["player_down"]["duration"] == 1.7
        assert saved["B"]["rules"]["player_down"]["duration"] == original_b_entry_duration
        assert saved["A"]["rules"]["defeat_interaction"]["duration"] is None
        assert saved["A"]["story_mode"] == "fixed"
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
