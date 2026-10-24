"""HUD/settings screenshot matrix; fake readings, no sockets or actual output."""
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QObject, QMetaObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.hud_settings import HUD_DEFAULTS
from ricca_dglab.ovc_pipeline import OvcOutputPlan
from ricca_dglab.product_config import ProductConfig

root = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
temp = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temp.name) / "settings.json")
config.values.update(onboarding_completed=True)
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
original = deepcopy(config.values)
backend._device_connected = backend._ovc_connected = True
backend._priority_output_active = True  # Fake live presentation, never a sender.
backend._pulse_route_paused = backend._ovc_route_paused = False
backend._preview_a, backend._preview_b = 18, 24
backend._config.values["ovc_profile"]["hard_cap"] = 200
backend._ovc_plan = OvcOutputPlan(strength_a=80, strength_b=160, hard_cap=200, allowed=True, paused=False)
original = deepcopy(config.values)
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda items: warnings.extend(str(item) for item in items))
engine.rootContext().setContextProperty("backend", backend)
qml = root / "src/ricca_dglab/qml"
engine.load(QUrl.fromLocalFile(str(qml / "ControlCenter.qml")))
main = engine.rootObjects()[0]
engine.load(QUrl.fromLocalFile(str(qml / "GameHud.qml")))
hud = engine.rootObjects()[1]
hud.setWidth(730)
hud.setHeight(68)
hud.show()
dialog = main.findChild(QObject, "hudSettingsDialog")
cases = [(language, width, height, scale) for language in ("zh", "en", "ja")
         for width, height in ((1360, 900), (1120, 720)) for scale in (60, 100, 180)]
result = 1


def run(index=0):
    global result
    if index == len(cases):
        assert not warnings, "\n".join(warnings)
        assert {k:v for k,v in config.values.items() if k not in {"language", "hud_settings"}} == {
            k:v for k,v in original.items() if k not in {"language", "hud_settings"}}
        assert backend._bridge._loop is None and backend._v4_hub._loop is None
        print("HUD customization: 18 language/size/scale settings and overlay screenshots passed; no hardware output.", flush=True)
        result = 0
        app.quit()
        return
    language, width, height, scale = cases[index]
    backend.setLanguage(language)
    main.setWidth(width); main.setHeight(height)
    config.values["hud_settings"] = {**HUD_DEFAULTS, "scale": scale}
    backend.changed.emit()
    hud.setWidth(round(730 * scale / 100)); hud.setHeight(round(68 * scale / 100))
    QMetaObject.invokeMethod(dialog, "openSettings")

    def capture():
        toast = main.findChild(QObject, "saveToast")
        toast.close()
        assert dialog.property("visible")
        assert dialog.property("width") <= main.width() - 40
        assert dialog.property("height") <= main.height() - 35
        assert main.findChild(QObject, "hudSetting_scale").property("value") == scale
        assert main.findChild(QObject, "saveHudSettingsButton").property("enabled")
        assert main.grabWindow().save(str(root / "artifacts" / f"hud-settings-{language}-{width}-{scale}.png"))
        assert hud.grabWindow().save(str(root / "artifacts" / f"hud-gold-{language}-{scale}.png"))
        QMetaObject.invokeMethod(dialog, "close")
        run(index + 1)
    QTimer.singleShot(250, capture)


QTimer.singleShot(400, run)
QTimer.singleShot(30000, app.quit)
app.exec()
hud.hide()
backend._priority_output_active = False
backend.shutdown()
engine.deleteLater()
temp.cleanup()
raise SystemExit(result)
