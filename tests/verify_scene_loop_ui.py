"""Screenshot QA with temporary settings, simulated telemetry and no real Socket."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QTimer, QUrl, QPointF, QMetaObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig
from test_defeat_scene import cg

project = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory(dir=project)
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values["onboarding_completed"] = True
config.values["scene_catalog"] = ["Scene3D_RiccaGhoul"]  # Exercise a future ANV discovery.
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._demo = False
backend._bridge = MagicMock()
backend._device_connected = True
state = cg(1)
state.update(is_paused=True, pause_mask=1)
state["story"]["act_screen_paused"] = True
state["stage_name"] = "StageName_07"
result = 1

def feed():
    backend._apply_state({"state": state, "received_at": time.monotonic(), "latency_ms": 1})
    backend._drain()
    backend.changed.emit()

for _ in range(3):
    feed()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(project / "src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects(), "QML failed to load"
window = engine.rootObjects()[0]
window.setWidth(1360)
window.setHeight(860)

def find(name, start=None):
    pending, seen = [window if start is None else start], set()
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

def guarded(callback):
    def run():
        try:
            callback()
        except Exception:
            import traceback
            traceback.print_exc()
            app.quit()
    return run

def shot(name):
    card, button = find("overviewPauseCard"), find("overviewPauseButton")
    offset = button.mapToItem(card, QPointF())
    assert offset.x() >= 17 and offset.y() >= 17
    assert offset.x() + button.width() <= card.width() - 17
    assert button.height() > 110 and button.width() > 180
    assert window.grabWindow().save(str(project / "artifacts" / name))

@guarded
def check_running():
    assert backend.previewA == backend.lowStrength
    assert backend.priorityOutputStatus == "场景循环"
    assert find("overviewPauseLabel").property("text") == "暂停输出"
    shot("scene-loop-overview-running.png")
    find("overviewPauseButton").clicked.emit()
    feed()
    QTimer.singleShot(180, check_paused)

@guarded
def check_paused():
    assert backend.userOutputPaused and backend.previewA == 0
    backend._bridge.set_auto_enabled.assert_called_with(False)
    assert find("overviewPauseLabel").property("text") == "恢复输出"
    shot("scene-loop-overview-paused.png")
    find("overviewPauseButton").clicked.emit()
    feed()
    window.setWidth(1120)
    window.setHeight(720)
    QTimer.singleShot(180, check_small)

@guarded
def check_small():
    global state
    assert not backend.userOutputPaused
    assert backend.previewA == backend.lowStrength
    shot("scene-loop-overview-small.png")
    from test_scene_library import anv
    state = anv()
    for _ in range(3): feed()
    window.setWidth(1360)
    window.setHeight(860)
    window.setProperty("pageIndex", 5)
    QTimer.singleShot(180, check_scene_page)

@guarded
def check_scene_page():
    assert backend.previewA == 0  # Newly discovered scene is not auto-enabled.
    assert find("openSceneLibraryButton").property("visible")
    assert window.grabWindow().save(str(project / "artifacts/scene-library-story-page.png"))
    feed()  # Screenshot capture must not turn a synthetic sample stale.
    find("openSceneLibraryButton").clicked.emit()
    find("recordCurrentSceneDialogButton").clicked.emit()
    assert backend.sceneLibrary[0]["id"] == "SceneANV_RiccaClaretMp"
    assert not backend.sceneLibrary[0]["enabled"]
    QMetaObject.invokeMethod(find("saveToast"), "close")
    QTimer.singleShot(180, check_scene_library)

@guarded
def check_scene_library():
    assert find("sceneLibraryDialog").property("visible")
    assert window.grabWindow().save(str(project / "artifacts/scene-library-dialog.png"))
    find("sceneLoopToggle_SceneANV_RiccaClaretMp").clicked.emit()
    QTimer.singleShot(180, check_scene_confirmation)

@guarded
def check_scene_confirmation():
    assert find("sceneLoopEnableConfirmation").property("visible")
    assert "SceneANV_RiccaClaretMp" not in backend._config.values["scene_catalog"]
    assert window.grabWindow().save(str(project / "artifacts/scene-library-confirmation.png"))
    QMetaObject.invokeMethod(find("sceneLoopEnableConfirmation"), "close")
    backend.toggleOutputPause()
    find("registerCollectedScenesButton").clicked.emit()
    QTimer.singleShot(180, check_batch_confirmation)

@guarded
def check_batch_confirmation():
    confirmation = find("sceneLoopEnableConfirmation")
    assert confirmation.property("visible")
    assert "34" in confirmation.property("heading")
    assert window.grabWindow().save(str(project / "artifacts/scene-batch-registration-confirmation.png"))
    feed()
    find("confirmResetButton", confirmation).clicked.emit()
    assert backend.registeredSceneCount == 34
    assert backend.userOutputPaused
    QMetaObject.invokeMethod(find("saveToast"), "close")
    QTimer.singleShot(180, check_batch_registered)

@guarded
def check_batch_registered():
    global result
    assert "白名单 34" in find("sceneRegistrationCount").property("text")
    assert backend.previewA == 0
    assert window.grabWindow().save(str(project / "artifacts/scene-batch-registered.png"))
    result = 0
    print("Scene loops/pause, record-only library and in-process 34-scene registration preserving pause: OK")
    app.quit()

timer = QTimer()
timer.timeout.connect(feed)
timer.start(80)
QTimer.singleShot(250, check_running)
QTimer.singleShot(8000, app.quit)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
temporary.cleanup()
sys.exit(result)
