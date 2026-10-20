"""Render all EN/JA pages and strategy/tutorial dialogs with no real outputs."""
from copy import deepcopy
from pathlib import Path
import re
import sys
import tempfile
from unittest.mock import patch

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

project = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory(dir=project)
config = ProductConfig(Path(temporary.name)/"settings.json")
config.values["onboarding_completed"] = True
with patch("ricca_dglab.backend.ProductConfig",return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices",return_value=[]):
    backend = AppBackend(DemoReader(),demo=True,start_bridge=False)
backend._timer.stop()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend",backend)
engine.load(QUrl.fromLocalFile(str(project/"src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects()
window = engine.rootObjects()[0]
window.setWidth(1360); window.setHeight(960)
strategy = window.findChild(QObject,"channelStrategyDialog")
guide = window.findChild(QObject,"onboardingDialog")
hotkey = window.findChild(QObject,"hotkeyDialog")
original = deepcopy(config.values)
jobs = [(locale,page,None) for locale in ("en","ja") for page in range(8)]
jobs += [(locale,3,kind) for locale in ("en","ja") for kind in ("battle","story","tutorial","small")]
jobs += [(locale,2,"hotkey") for locale in ("en","ja")]
index, result = 0, 1


def items(start):
    seen, pending = set(), [start]
    while pending:
        item = pending.pop()
        if item is None or item in seen: continue
        seen.add(item)
        yield item
        pending.extend(item.children())
        if isinstance(item,QQuickItem): pending.extend(item.childItems())


def next_job():
    global index,result
    try:
        if index == len(jobs):
            assert config.values["language"] == "ja"
            assert {k:v for k,v in config.values.items() if k!="language"} == {k:v for k,v in original.items() if k!="language"}
            assert not backend.deviceConnected
            assert not backend.audioEmpathyEnabled
            assert ProductConfig(config.path).values["language"] == "ja"
            print("EN/JA: 8 pages, independent strategies, tutorial, small window; settings and output unchanged: OK")
            result = 0
            app.quit()
            return
        locale,page,kind = jobs[index]
        strategy.close(); guide.close(); hotkey.close()
        backend.setLanguage(locale)
        window.setWidth(1120 if kind=="small" else 1360)
        window.setHeight(720 if kind=="small" else 960)
        # Let the native resize finish before opening a popup, as a real user
        # does; opening during the pending resize can discard Canvas textures.
        if kind=="small": QTest.qWait(100)
        window.setProperty("pageIndex",page)
        if kind in {"battle","story","small"}:
            strategy.openChannel("B" if kind=="small" else "A")
            strategy.setProperty("category","story" if kind=="story" else "battle")
        elif kind=="tutorial": guide.openGuide()
        elif kind=="hotkey": hotkey.open()
        # Hide save toast before visual verification without changing settings.
        toast=window.findChild(QObject,"saveToast")
        if toast: engine.newQObject(toast).property("close").callWithInstance(engine.newQObject(toast))
        QTimer.singleShot(400 if kind=="small" else 240,capture)
    except Exception:
        import traceback; traceback.print_exc(); app.quit()


def capture():
    global index
    try:
        locale,page,kind=jobs[index]
        leaks=[]
        for item in items(window):
            if item.metaObject().indexOfProperty("sourceText") < 0: continue
            if not item.property("visible") or item.property("translateEnabled") is False: continue
            rendered=str(item.property("text") or "")
            if locale=="en" and re.search(r"[\u3400-\u9fff]",rendered) and rendered not in {"中文","日本語"}:
                leaks.append(rendered)
        assert not leaks, repr(leaks[:12])
        destination=project/"artifacts"/("locale-"+locale+"-"+(kind or "page"+str(page))+".png")
        assert window.grabWindow().save(str(destination))
        index+=1
        QTimer.singleShot(40,next_job)
    except Exception:
        import traceback; traceback.print_exc(); app.quit()


QTimer.singleShot(200,next_job)
QTimer.singleShot(25000,app.quit)
app.exec()
backend.shutdown()
temporary.cleanup()
sys.exit(result)
