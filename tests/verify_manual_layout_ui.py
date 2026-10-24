"""Single/dual manual dashboard, draft controls and sticky footer QA; no I/O."""
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QObject, QPointF, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

root = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
temp = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temp.name) / "settings.json")
config.values["onboarding_completed"] = True
config.save()
original = config.path.read_bytes()
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
        patch("ricca_dglab.backend.TelemetryWorker.start"), \
        patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._device_connected = True
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda items: warnings.extend(str(item) for item in items))
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/ControlCenter.qml")))
window = engine.rootObjects()[0]
window.setProperty("pageIndex", 9)
page = window.findChild(QQuickItem, "manualControlPage")
pulse = window.findChild(QQuickItem, "pulseManualPanel")
ovc = window.findChild(QQuickItem, "ovcManualPanel")
cases = [(locale, width, height, dual) for locale in ("zh", "en", "ja")
         for width, height in ((1360, 900), (1120, 720)) for dual in (False, True)]
result = 1


def find_item(parent, name):
    pending = [parent]
    seen = set()
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
    raise AssertionError(f"Missing UI item: {name}")


def run(index=0):
    global result
    if index == len(cases):
        assert not warnings, "\n".join(warnings)
        assert config.path.read_bytes() == original
        assert backend._bridge._loop is None and backend._v4_hub._loop is None
        print("Manual layout: 12 single/dual/language/size screenshots and draft-only controls passed; no output.", flush=True)
        result = 0
        app.quit()
        return
    locale, width, height, dual = cases[index]
    config.values["language"] = locale
    backend.languageChanged.emit()
    backend._ovc_connected = dual
    window.setWidth(width);window.setHeight(height)
    backend.changed.emit()

    def capture():
        assert ovc.isVisible() == dual
        if dual:
            assert abs(pulse.width() - ovc.width()) < 3
            assert ovc.x() >= pulse.x() + pulse.width() + 8
        else:
            assert pulse.width() > pulse.parentItem().width() * .95
        before = deepcopy(config.values)
        for panel in ([pulse, ovc] if dual else [pulse]):
            step = 10 if panel == ovc else 1
            panel.setProperty("strengthA", 0)
            panel.findChild(QObject, "manualIncreaseA").clicked.emit()
            assert panel.property("strengthA") == step
            panel.findChild(QObject, "manualDecreaseA").clicked.emit()
            assert panel.property("strengthA") == 0
            waves = panel.property("catalog")
            first = panel.property("waveA")
            panel.findChild(QObject, "manualSelectChannelB").clicked.emit()
            find_item(panel, "manualWaveTile_" + waves[1]["key"]).clicked.emit()
            assert panel.property("waveB") == waves[1]["key"]
            assert panel.property("waveA") == first
            panel.findChild(QObject, "manualSelectChannelA").clicked.emit()
            footer = panel.findChild(QQuickItem, "stopManualOutputButton")
            assert footer.mapToScene(QPointF(0, footer.height())).y() <= window.height() - 15
            assert panel.findChild(QQuickItem, "manualBodyScroll").height() > 230
            assert not backend._manual_playback["ovc" if panel == ovc else "coyote"].running
        assert config.values == before
        sidebar = window.findChild(QQuickItem, "sidebarStatusCard")
        assert sidebar.mapToScene(QPointF(0, sidebar.height())).y() <= window.height() + 1
        assert window.grabWindow().save(str(root / "artifacts" / f"manual-layout-{locale}-{width}-{'dual' if dual else 'single'}.png"))
        run(index + 1)
    QTimer.singleShot(300, capture)


QTimer.singleShot(400, run)
QTimer.singleShot(30000, app.quit)
app.exec()
backend.shutdown()
engine.deleteLater()
temp.cleanup()
raise SystemExit(result)
