"""Render capture overview and editable rules with no game, socket or audio."""
from pathlib import Path
from copy import deepcopy
import sys
import tempfile
import time
from unittest.mock import patch

from PySide6.QtCore import QObject, QTimer, QUrl, QPointF
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig
from ricca_dglab.models import RuntimeMode, SafetyDecision

project = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
engine = QQmlApplicationEngine()
temporary = tempfile.TemporaryDirectory(dir=project)
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values["onboarding_completed"] = True
original_a = deepcopy(config.values["channel_policies"]["A"])
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
     patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]), \
     patch("ricca_dglab.backend.TelemetryWorker.start"):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._state = {
    "scene": "gameplay", "current_hp": 22.23, "max_hp": 31, "current_magic": 50, "max_magic": 50,
    "action_trigger_hash": 362220413, "stage": {"system_name": "StageName_05"},
    "capture": {"info_address": "0x1000", "current_break_off_count": 5.616,
                "break_off_count_max": 12.073, "break_off_acceptance": True},
}
backend._last_received = time.monotonic()
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(project / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
window.setWidth(1360)
window.setHeight(1000)
dialog = window.findChild(QObject, "channelStrategyDialog")
result = 1


def find(name):
    pending = [window, dialog.property("contentItem")]
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


def step_one():
    try:
        assert find("captureStatusText").property("text") == "可挣扎"
        assert find("armorMultiplierStatus").property("text") == "未破甲 · Pulse ×1.0"
        shot("capture-overview-active.png")
        backend._mapping.rebase_sensitivity(2)  # Simulated broken armor, no device.
        backend.changed.emit()
        QTimer.singleShot(180, step_armor)
    except Exception:
        fail()


def step_armor():
    try:
        assert find("armorMultiplierStatus").property("text") == "已破甲 · Pulse ×1.2"
        shot("armor-broken-single-boost.png")
        window.setWidth(1120)
        window.setHeight(720)
        QTimer.singleShot(180, step_minimum)
    except Exception:
        fail()


def step_minimum():
    try:
        card = find("captureOverviewCard")
        assert card.width() > 600
        shot("capture-overview-minimum.png")
        window.setWidth(1360)
        window.setHeight(1000)
        dialog.openChannel("B")
        QTimer.singleShot(180, step_rules)
    except Exception:
        fail()


def step_rules():
    try:
        keys = [row["key"] for row in dialog.property("ruleRows").toVariant()]
        assert "struggle" in keys and "capture_start" not in keys, "Capture uses one sustained rule, not a duplicate entry pulse"
        choice = find("struggleStrengthChoice")
        choice.setProperty("currentIndex", 4)
        choice.activated.emit(4)
        strength = find("struggleCustomStrength")
        strength.setProperty("value", 13)
        strength.moved.emit()
        duration = find("struggleDuration")
        assert not duration.property("visible"), "Sustained struggle must not have an editable duration"
        wave = find("struggleWaveChoice")
        index = next(i for i, item in enumerate(backend.waveformCatalog) if item["key"] == "impact")
        wave.setProperty("currentIndex", index)
        wave.activated.emit(index)
        QTimer.singleShot(150, step_saved)
    except Exception:
        fail()


def step_saved():
    try:
        shot("capture-channel-rules.png")
        dialog.save()
        saved = ProductConfig(config.path).values["channel_policies"]
        rule = saved["B"]["rules"]["struggle"]
        assert (rule["custom_strength"], rule["duration"], rule["wave"]) == (13, None, "impact")
        assert saved["A"] == original_a
        backend._state["capture"].update(info_address="0x0", current_break_off_count=12.073,
                                          break_off_acceptance=False)
        backend.changed.emit()
        QTimer.singleShot(150, step_escape)
    except Exception:
        fail()


def step_escape():
    global result
    try:
        assert find("captureStatusText").property("text") == "未受困"
        assert backend.captureStatus["progress"] == 0
        shot("capture-overview-escaped.png")
        backend._output_armed = True  # UI-only mock: no socket thread exists.
        backend._device_connected = True
        backend._last_received = time.monotonic()
        backend._decision = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        backend.changed.emit()
        button = find("outputPauseButton")
        assert button.property("label") == "暂停输出"
        button.clicked.emit()
        assert backend.userOutputPaused and backend.outputArmed and backend.outputPaused
        assert button.property("label") == "恢复输出"
        window.setWidth(1120)
        window.setHeight(720)
        QTimer.singleShot(350, step_paused)  # Let animated bar widths settle after resize.
        return
    except Exception:
        fail()
    app.quit()


def step_paused():
    try:
        button = find("outputPauseButton")
        position = button.mapToScene(QPointF(0, 0))
        shot("output-paused-header.png")
        for page in (0, 3, 6):
            window.setProperty("pageIndex", page)
            assert button.mapToScene(QPointF(0, 0)) == position
        backend._state["game_ui"] = {"is_user_pause": True}
        backend._decision = SafetyDecision(RuntimeMode.PAUSED, False, False, "game-paused")
        button.clicked.emit()
        assert not backend.userOutputPaused and backend.outputPaused  # Game pause still wins.
        backend._state["game_ui"]["is_user_pause"] = False
        backend._last_received = time.monotonic()
        backend._decision = SafetyDecision(RuntimeMode.GAMEPLAY_READY, True, False, "ready")
        backend._sync_output_pause()
        backend.changed.emit()
        assert not backend.outputPaused and backend.outputArmed
        assert button.property("label") == "暂停输出"
        QTimer.singleShot(150, step_resumed)
    except Exception:
        fail()


def step_resumed():
    global result
    try:
        shot("output-resumed-header.png")
        print("Capture UI, state duration, pause/resume button, fixed header position and game-pause priority: OK")
        result = 0
    except Exception:
        fail()
    app.quit()


def fail():
    import traceback
    traceback.print_exc()
    app.quit()


# Keep the synthetic snapshot fresh without enabling any telemetry worker.
fresh = QTimer()
fresh.timeout.connect(lambda: setattr(backend, "_last_received", time.monotonic()))
fresh.start(100)
QTimer.singleShot(250, step_one)
QTimer.singleShot(6000, app.quit)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
temporary.cleanup()
sys.exit(result)
