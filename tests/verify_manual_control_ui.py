"""Manual tab and HUD-help QA, fake senders and temp config only."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock

from PySide6.QtCore import QObject, QTimer, QUrl, QMetaObject, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

root=Path(__file__).resolve().parents[1]
temporary=tempfile.TemporaryDirectory(dir=root/".analysis")
config=ProductConfig(Path(temporary.name)/"settings.json")
config.values["onboarding_completed"]=True
config.save()
original=deepcopy(config.values)
original_bytes=config.path.read_bytes()
QQuickStyle.setStyle("Basic")
app=QGuiApplication([])
with patch("ricca_dglab.backend.ProductConfig",return_value=config), patch("ricca_dglab.backend.TelemetryWorker.start"), patch("ricca_dglab.backend.enumerate_audio_devices",return_value=[]), patch("ricca_dglab.backend.audit.record"):
    backend=AppBackend(DemoReader(),demo=True,start_bridge=False)
backend._timer.stop()
backend._bridge=MagicMock(connected=True)
backend._ovc_bridge=MagicMock(connected=True)
backend._v4_hub=MagicMock()
backend._device_connected=backend._ovc_connected=True
backend._state={"status":"error"}
backend._reader_error="fake telemetry failure"
engine=QQmlApplicationEngine()
warnings=[]
engine.warnings.connect(lambda items:warnings.extend(str(item) for item in items))
engine.rootContext().setContextProperty("backend",backend)
engine.load(QUrl.fromLocalFile(str(root/"src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects(), "Main QML did not load: "+"\n".join(warnings)
window=engine.rootObjects()[0]
result=1
reports=[]

def find(name,parent=window):
    pending=[parent];seen=set()
    while pending:
        item=pending.pop()
        if item is None or item in seen:continue
        seen.add(item)
        if item.objectName()==name:return item
        pending.extend(item.children())
        if isinstance(item,QQuickItem):pending.extend(item.childItems())
    raise AssertionError(name)

def invoke(obj,method,*args):
    assert QMetaObject.invokeMethod(obj,method,*(Q_ARG("QVariant",arg) for arg in args)),method

cases=[(locale,device,width,height) for locale in ("zh","en","ja") for device in ("pulse","ovc") for width,height in ((1360,900),(1120,720))]

def run(index=0):
    global result
    if index==len(cases):
        try:
            assert not warnings,"\n".join(warnings)
            assert config.path.read_bytes()==original_bytes
            assert {k:v for k,v in config.values.items() if k!="language"}=={k:v for k,v in original.items() if k!="language"}
            (root/"artifacts/manual-ui-report.json").write_text(json.dumps(dict(screenshots=reports,config_unchanged=True,real_output=False,qml_warnings=warnings),indent=2),encoding="utf-8")
            print("Manual UI: 12 screenshots, mock-only start/stop, no game, unchanged config, no QML warnings.")
            result=0
        finally:app.quit()
        return
    locale,device,width,height=cases[index]
    try:
        backend._demo=False # Production authorization exercised with fake senders.
        backend._stop_latched=backend._user_output_paused=False
        config.values["language"]=locale;backend.languageChanged.emit()
        window.setWidth(width);window.setHeight(height)
        find("manualControlNavButton").clicked.emit()
        assert window.property("pageIndex")==9
        panel=find(device+"ManualPanel")
        route="coyote" if device=="pulse" else "ovc"
        backend.setManualMode(route,True)
        panel.setProperty("strengthA",10);panel.setProperty("strengthB",0)
        backend.changed.emit()
        find("startManualOutputButton",panel).clicked.emit()
        assert backend._manual_playback[route].running
        assert not backend.telemetryOnline
    except Exception:
        import traceback;traceback.print_exc();app.quit();return
    def capture():
        try:
            for key in ("startManualOutputButton","stopManualOutputButton"):
                button=find(key,panel)
                assert button.width()>70
                content=button.property("contentItem")
                assert content.property("implicitWidth")<=content.width()+2,(locale,key,"clipped")
            filename=f"manual-{locale}-{width}-{device}.png"
            assert window.grabWindow().save(str(root/"artifacts"/filename))
            reports.append(filename)
            find("stopManualOutputButton",panel).clicked.emit()
            assert not backend._manual_playback[route].running
            backend._stop_latched=True;backend.changed.emit()
            assert not find("startManualOutputButton",panel).property("enabled")
            run(index+1)
        except Exception:
            import traceback;traceback.print_exc();app.quit()
    QTimer.singleShot(300,capture)

QTimer.singleShot(250,run)
app.exec()
backend.shutdown()
temporary.cleanup()
raise SystemExit(result)
