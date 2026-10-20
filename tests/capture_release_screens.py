"""Fresh 1.0.0 marketing screenshots, all telemetry/audio/connection simulated."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow, QQuickItem
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

root=Path(__file__).resolve().parents[1]
app=QGuiApplication([])
temporary=tempfile.TemporaryDirectory(dir=root)
config=ProductConfig(Path(temporary.name)/"settings.json")
config.values.update(onboarding_completed=True,audio_empathy_enabled=True,audio_gain=2.0,audio_queue_minimum=5)
with patch("ricca_dglab.backend.ProductConfig",return_value=config),patch("ricca_dglab.backend.TelemetryWorker.start"),patch("ricca_dglab.backend.AudioCaptureWorker.start"),patch("ricca_dglab.backend.enumerate_audio_devices",return_value=[{"id":"demo","name":"系统回环 · 游戏音频（模拟）"}]):
    backend=AppBackend(DemoReader(),demo=True,start_bridge=False)
backend._timer.stop()
backend._state=DemoReader()()
backend._state.update(current_hp=22.4,max_hp=31,current_magic=50,max_magic=50)
backend._state["stage"]["system_name"]="StageName_20"
backend._hotkey_status="全局急停快捷键已注册"  # Simulated registration, never registers keys.
engine=QQmlApplicationEngine(); engine.rootContext().setContextProperty("backend",backend)
engine.load(QUrl.fromLocalFile(str(root/"src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects()
window=engine.rootObjects()[0]; window.setWidth(1360); window.setHeight(1100)
strategy=window.findChild(QObject,"channelStrategyDialog")
hotkey=window.findChild(QObject,"hotkeyDialog")
editor=next(item for item in window.findChildren(QObject) if item.metaObject().indexOfProperty("seedName")>=0)
jobs=[("overview",0),("strategy",3),("editor",3),("audio",6),("story",5),("hotkey",2)]
index=0; result=1
def call(obj,method): engine.newQObject(obj).property(method).callWithInstance(engine.newQObject(obj))
def find(name):
    pending,seen=[window],set()
    while pending:
        item=pending.pop()
        if item in seen: continue
        seen.add(item)
        if item.objectName()==name: return item
        pending.extend(item.children())
        if isinstance(item,QQuickItem): pending.extend(item.childItems())
    raise AssertionError(name)
def step():
    global index,result
    try:
        if index==len(jobs):
            print("Six 1.0.0 screenshots captured; simulated only, no device, no audio capture")
            result=0; app.quit(); return
        name,page=jobs[index]
        strategy.close(); hotkey.close()
        call(editor,"close")
        # Close the waveform editor before moving to another page.
        if index==3: window.setProperty("editorOnStart",False)
        window.setProperty("pageIndex",page)
        if name=="strategy": strategy.openChannel("A")
        if name=="editor": window.setProperty("editorOnStart",True)
        if name=="hotkey": hotkey.open()
        QTimer.singleShot(400,capture)
    except Exception:
        import traceback; traceback.print_exc(); app.quit()
def capture():
    global index
    try:
        name,_=jobs[index]
        if name=="story":
            assert find("queueWave_0").property("currentValue")=="official_breath", "Do not render the saved wave as Rest"
        assert window.grabWindow().save(str(root/"website/dist/assets/screens"/(name+".png")))
        index+=1
        QTimer.singleShot(80,step)
    except Exception:
        import traceback; traceback.print_exc(); app.quit()
QTimer.singleShot(300,step); QTimer.singleShot(15000,app.quit)
app.exec(); backend.shutdown(); temporary.cleanup(); sys.exit(result)
