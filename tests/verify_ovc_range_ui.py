"""Preview a 200-cap OVC workbench; fake state and temporary config only."""
from pathlib import Path
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

root = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
temp = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temp.name) / "settings.json")
config.values.update(onboarding_completed=True)
config.values["ovc_profile"].update(strength_low=40, strength_medium=80,
                                   strength_high=120, strength_death=160, hard_cap=200)
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda items: warnings.extend(str(item) for item in items))
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
window.setWidth(1360)
window.setHeight(900)
window.setProperty("pageIndex", 8)
result = 1


def run(index=0):
    global result
    if index == 3:
        assert not warnings, warnings
        assert backend._bridge._loop is None and backend._v4_hub._loop is None
        print("OVC 200-cap screenshots: zh/en/ja passed; no device I/O.", flush=True)
        result = 0
        app.quit()
        return
    language = ("zh", "en", "ja")[index]
    backend.setLanguage(language)

    def capture():
        toast = window.findChild(QObject, "saveToast")
        if toast:
            toast.close()
        workbench = window.findChild(QObject, "ovcWorkbenchPage")
        assert workbench.property("draftCap") == 200
        assert workbench.property("valid")
        sliders = [item for item in workbench.findChildren(QObject)
                   if item.property("to") == 200 and item.property("stepSize") == 10]
        assert len(sliders) >= 5, len(sliders)
        assert window.grabWindow().save(str(root / "artifacts" / f"ovc-range-200-{language}.png"))
        run(index + 1)
    QTimer.singleShot(350, capture)


QTimer.singleShot(350, run)
app.exec()
backend.shutdown()
engine.deleteLater()
temp.cleanup()
raise SystemExit(result)
