"""Queue editor routing/save/screenshots using fake telemetry and no Socket."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QTimer, QUrl, QMetaObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig
from test_scene_library import anv

project = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory(dir=project)
config = ProductConfig(Path(temporary.name)/"settings.json")
config.values["onboarding_completed"] = True
original_b_queue = deepcopy(config.values["story_queues"]["B"])
with patch("ricca_dglab.backend.ProductConfig",return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices",return_value=[]):
    backend = AppBackend(DemoReader(),demo=True,start_bridge=False)
backend._timer.stop()
backend._demo = False
backend._bridge = MagicMock()
backend._device_connected = True
state = anv()
result = 1
simulate_audio = False

def feed():
    backend._apply_state({"state":state,"received_at":time.monotonic(),"latency_ms":1})
    if simulate_audio:
        backend._audio_last_sample = time.monotonic()
        backend._audio_level = 70
        backend._audio_strength = backend.hardCap * 0.5
    backend._drain()
for _ in range(3): feed()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend",backend)
engine.load(QUrl.fromLocalFile(str(project/"src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects()
window = engine.rootObjects()[0]
window.setWidth(1360); window.setHeight(1000)
window.setProperty("pageIndex",3)
window.setProperty("strategyOnStart","A")

def find(name, start=None):
    pending, seen = [window if start is None else start], set()
    while pending:
        item = pending.pop()
        if item in seen: continue
        seen.add(item)
        if item.objectName()==name: return item
        pending.extend(item.children())
        if isinstance(item,QQuickItem): pending.extend(item.childItems())
    raise AssertionError(name)

def guarded(callback):
    def run():
        try: callback()
        except Exception:
            import traceback
            traceback.print_exc()
            app.quit()
    return run

def screenshot(name):
    assert window.grabWindow().save(str(project/"artifacts"/name))

def scroll_to_editor():
    editor = find("storyQueueEditor")
    flick = find("storyPage").property("contentItem")
    maximum = max(0,float(flick.property("contentHeight"))-float(flick.property("height")))
    flick.setProperty("contentY",min(maximum,max(0,editor.y()-16)))

@guarded
def select_queue():
    find("strategyStoryTab").clicked.emit()
    assert find("channelStrategyDialog").property("category") == "story"
    choice = find("defeat_interactionWaveChoice")
    index = choice.property("count")-1
    choice.setProperty("currentIndex",index)
    screenshot("story-queue-strategy-option.png")
    choice.activated.emit(index)
    assert window.property("pageIndex")==5
    assert not find("channelStrategyDialog").property("visible")
    assert backend.channelPolicies["A"]["rules"]["defeat_interaction"]["playback"]=="queue"
    QMetaObject.invokeMethod(find("saveToast"),"close")
    QTimer.singleShot(180,edit_queue)

@guarded
def edit_queue():
    editor = find("storyQueueEditor")
    editor.setProperty("dirty",True)
    editor.setProperty("draft",[
        {"wave":"impact","duration":2.5,"tier":"low","custom_strength":17},
        {"wave":"idle","duration":1.0,"tier":"low","custom_strength":0},
        {"wave":"official_bouncy","duration":3.0,"tier":"medium","custom_strength":None},
    ])
    editor.setProperty("draftEnabled",True)
    QTimer.singleShot(180,save_queue)

@guarded
def save_queue():
    strength = find("queueStrength_0")
    strength.setProperty("value",19)
    strength.valueModified.emit()
    duration = find("queueDuration_0")
    duration.setProperty("value",2.0)
    duration.moved.emit()
    feed()
    find("saveStoryQueueQuickButton").clicked.emit()
    saved = ProductConfig(config.path).values
    assert saved["story_queues"]["A"][0]["custom_strength"]==19
    assert saved["story_queues"]["A"][0]["duration"]==2.0
    assert len(saved["story_queues"]["A"])==3
    assert saved["hard_cap"]==30
    QMetaObject.invokeMethod(find("saveToast"),"close")
    scroll_to_editor()
    QTimer.singleShot(180,check_saved)

@guarded
def check_saved():
    screenshot("story-queue-editor-a.png")
    backend.toggleOutputPause()
    feed()
    QTimer.singleShot(180,check_paused)

@guarded
def check_paused():
    assert backend.previewA==0 and backend.userOutputPaused
    screenshot("story-queue-editor-paused.png")
    find("storyQueueChannelB").clicked.emit()
    assert find("storyQueueEditor").property("channel")=="B"
    assert find("storyQueueEditor").property("draftEnabled")  # New hybrid B default uses queues.
    window.setWidth(1120); window.setHeight(720)
    QTimer.singleShot(180,check_narrow)

@guarded
def check_narrow():
    global simulate_audio
    scroll_to_editor()
    screenshot("story-queue-editor-b-small.png")
    assert len(backend.storyQueues["A"])==3
    assert backend.storyQueues["B"] == original_b_queue
    simulate_audio = True
    backend._config.values["audio_empathy_enabled"] = True
    backend._audio_status = "模拟音频 · 仅界面验证"
    backend.toggleOutputPause()
    for _ in range(3): feed()
    window.setWidth(1360); window.setHeight(1000)
    window.setProperty("pageIndex",6)
    QTimer.singleShot(180,check_audio_page)

@guarded
def check_audio_page():
    global result
    assert find("audioEnabledSwitch").property("checked")
    assert backend.previewB>0
    assert backend.audioPulseStrength==backend.previewB
    assert backend.priorityOutputStatus=="剧情音频"
    screenshot("audio-hybrid-queue.png")
    find("editAudioStoryQueueButton").clicked.emit()
    assert window.property("pageIndex")==5
    assert find("storyQueueEditor").property("channel")=="B"
    result = 0
    print("Queue strategy/editor routing, save, pause, narrow layout and hybrid audio queue page/link: OK")
    app.quit()

timer = QTimer()
timer.timeout.connect(feed); timer.start(80)
QTimer.singleShot(250,select_queue)
QTimer.singleShot(10000,app.quit)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
temporary.cleanup()
sys.exit(result)
