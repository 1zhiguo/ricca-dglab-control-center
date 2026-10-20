"""Isolated QML QA: fake telemetry, fake bridge, no game/device operations."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject, QTimer, QUrl, QPointF
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig
from test_defeat_scene import death, cg

project = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory(dir=project)
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values["onboarding_completed"] = True
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._demo = False
backend._bridge = MagicMock()
backend._device_connected = True

def feed(state):
    backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
    backend._drain()
    backend.changed.emit()

feed(dict(death(), current_hp=31, max_hp=31))
backend.toggleOutputPause()
feed(dict(death(), max_hp=31, is_paused=True, pause_mask=1))
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(project / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
window.setWidth(1360)
window.setHeight(1000)
result = 1
state = dict(death(), max_hp=31, is_paused=True, pause_mask=1)

def find(name):
    pending, seen = [window], set()
    while pending:
        item = pending.pop()
        if item in seen:
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

def guarded(callback):
    def run():
        try:
            callback()
        except Exception:
            import traceback
            traceback.print_exc()
            app.quit()
    return run

@guarded
def check_death():
    global state
    assert backend.userOutputPaused and not backend.outputPaused
    assert find("outputStateBadge").property("text") == "死亡惩罚 · 输出中"
    assert find("outputPauseButton").property("label") == "恢复普通输出"
    shot("defeat-priority-during-pause.png")
    backend.toggleOutputPause()
    state = dict(cg(0), is_paused=True, pause_mask=1)
    for _ in range(3):
        feed(state)
    QTimer.singleShot(2900, check_loop)

@guarded
def check_loop():
    assert backend.priorityOutputStatus == "败北互动"
    assert find("outputStateBadge").property("text") == "败北互动 · 输出中"
    position = find("outputPauseButton").mapToScene(QPointF())
    for page in (0, 1, 3, 6):
        window.setProperty("pageIndex", page)
        assert find("outputPauseButton").mapToScene(QPointF()) == position
    window.setProperty("pageIndex", 0)
    shot("defeat-interaction-engine-pause.png")
    backend.emergencyStop()
    backend._drain()
    assert backend.outputPaused and backend.priorityOutputStatus == ""
    backend._bridge.set_auto_enabled.assert_called_with(False)
    QTimer.singleShot(150, check_emergency)

@guarded
def check_emergency():
    global state
    shot("defeat-priority-emergency-stop.png")
    backend.toggleOutputPause()
    backend._defeat_scene.reset()
    state = dict(cg(0), defeat_scene_hint="Scene3D_RiccaGhoul")
    feed(state)
    assert backend.canConfirmCurrentDefeatScene
    QTimer.singleShot(150, check_takeover)

@guarded
def check_takeover():
    global result
    assert find("confirmCurrentDefeatButton").property("visible")
    shot("defeat-current-interaction-takeover.png")
    find("confirmCurrentDefeatButton").clicked.emit()
    assert window.findChild(QObject, "confirmResetDialog").property("visible")
    shot("defeat-current-interaction-confirmation.png")
    find("cancelResetButton").clicked.emit()
    assert not backend._defeat_scene.root
    result = 0
    print("Death priority badge, loop under engine pause, emergency latch, takeover and fixed header: OK")
    app.quit()

timer = QTimer()
timer.timeout.connect(lambda: feed(state))
timer.start(80)
QTimer.singleShot(250, check_death)
QTimer.singleShot(6500, app.quit)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
temporary.cleanup()
sys.exit(result)
