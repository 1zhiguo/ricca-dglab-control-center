"""Actual Qt mouse/key event QA; isolated settings and mock device/hotkey service."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QObject, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

root=Path(__file__).resolve().parents[1]
app=QGuiApplication([])
temporary=tempfile.TemporaryDirectory(dir=root)
config=ProductConfig(Path(temporary.name)/"settings.json")
config.values["onboarding_completed"]=True
with patch("ricca_dglab.backend.ProductConfig",return_value=config),patch("ricca_dglab.backend.TelemetryWorker.start"),patch("ricca_dglab.backend.AudioCaptureWorker.start"),patch("ricca_dglab.backend.enumerate_audio_devices",return_value=[]):
    backend=AppBackend(DemoReader(),demo=True,start_bridge=False)
backend._timer.stop()
service=MagicMock(); service.configure.return_value=(True,"")
backend._hotkey_service=service
engine=QQmlApplicationEngine(); engine.rootContext().setContextProperty("backend",backend)
engine.load(QUrl.fromLocalFile(str(root/"src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects()
window=engine.rootObjects()[0]; window.setWidth(1360); window.setHeight(960)
dialog=window.findChild(QObject,"hotkeyDialog")
guide=window.findChild(QObject,"onboardingDialog")
result=1

def find(name, start=None):
    pending,seen=[start or window],set()
    while pending:
        item=pending.pop()
        if item in seen: continue
        seen.add(item)
        if item.objectName()==name: return item
        pending.extend(item.children())
        if isinstance(item,QQuickItem): pending.extend(item.childItems())
    raise AssertionError(name)

def click(name,start=None):
    item=find(name,start)
    QTest.mouseClick(window,Qt.LeftButton,Qt.NoModifier,item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint())
    app.processEvents()

def close_toast():
    toast=window.findChild(QObject,"saveToast")
    engine.newQObject(toast).property("close").callWithInstance(engine.newQObject(toast))

def shot(name):
    QTest.qWait(200)
    assert window.grabWindow().save(str(root/"artifacts"/name))

def run():
    global result
    try:
        window.setProperty("pageIndex",2)
        dialog.open(); QTest.qWait(150)
        recorder=find("emergencyHotkeyRecorder")
        click("emergencyHotkeyCapture",recorder)
        assert recorder.property("recording")
        QTest.keyClick(window,Qt.Key_F12,Qt.ControlModifier)
        assert recorder.property("chord")=="Ctrl+F12"
        assert not recorder.property("recording")
        shot("hotkey-direct-capture.png")
        click("saveEmergencyHotkeyButton")
        assert backend.emergencyHotkey=="Ctrl+F12"
        assert backend.userOutputPaused and backend._stop_latched
        close_toast()
        dialog.open(); QTest.qWait(100)
        click("emergencyHotkeyCapture",recorder)
        QTest.keyClick(window,Qt.Key_Pause)
        assert recorder.property("chord")=="Pause"
        click("saveEmergencyHotkeyButton")
        assert ProductConfig(config.path).values["emergency_hotkey"]=="Pause"
        close_toast()
        dialog.open(); QTest.qWait(100)
        click("emergencyHotkeyCapture",recorder)
        QTest.keyClick(window,Qt.Key_Escape)
        assert not recorder.property("recording")
        assert recorder.property("chord")=="Pause"
        dialog.close()
        guide.openGuide(); QTest.qWait(100)
        assert guide.property("steps").toVariant()[-2]["title"]=="全局急停：直接录入按键"
        guide.setProperty("step",4); QTest.qWait(100)
        tutorial=find("onboardingHotkeyRecorder")
        click("emergencyHotkeyCapture",tutorial)
        QTest.keyClick(window,Qt.Key_F10)
        assert tutorial.property("chord")=="F10"
        shot("onboarding-hotkey-capture.png")
        service.configure.return_value=(False,"occupied")
        click("onboardingNext")
        assert guide.property("step")==4, "Failed registration must not advance"
        assert backend.emergencyHotkey=="Pause"
        close_toast(); service.configure.return_value=(True,"")
        click("onboardingNext")
        assert guide.property("step")==5
        assert backend.emergencyHotkey=="F10"
        assert ProductConfig(config.path).values["emergency_hotkey"]=="F10"
        close_toast(); guide.setProperty("step",4)
        for language in ("en","ja"):
            backend.setLanguage(language)
            shot("onboarding-hotkey-"+language+".png")
        result=0
        print("Direct Ctrl+F12 capture, single Pause/F10, Esc cancel, penultimate onboarding save/failure, screenshots: OK")
    except Exception:
        import traceback; traceback.print_exc()
    finally: app.quit()

QTimer.singleShot(200,run); QTimer.singleShot(15000,app.quit)
app.exec(); backend.shutdown(); temporary.cleanup(); sys.exit(result)
