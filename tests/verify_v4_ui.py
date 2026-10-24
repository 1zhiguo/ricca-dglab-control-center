"""Parallel Pulse + OVC UI QA; fake devices and temporary config, no outputs."""
from copy import deepcopy
from pathlib import Path
import tempfile
from unittest.mock import patch

from PySide6.QtCore import QObject, QMetaObject, Q_ARG, QPointF, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem  # Register the screenshot-capable QQuickWindow conversion.
from PySide6.QtQuickControls2 import QQuickStyle

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

root = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values["onboarding_completed"] = True
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
     patch("ricca_dglab.backend.TelemetryWorker.start"), \
     patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
electrical_levels = (backend.lowStrength, backend.mediumStrength, backend.highStrength,
                     backend.deathStrength, backend.hardCap)
electrical_policies = deepcopy(backend.channelPolicies)
electrical_waves = deepcopy(backend.waveformCatalog)
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects(), "QML did not load"
window = engine.rootObjects()[0]
result = 1


def ready():
    assert backend.selectSocketProtocol("v4")
    assert not backend.selectOutputProfile("ovc"), "OVC must not replace Pulse"
    hub = backend._v4_hub
    hub.controller_id = "qa-v4-controller"
    hub.server_ready = hub.app_connected = True
    hub.qr_url = hub._build_qr_url()
    bridge = backend._bridge
    bridge.selected_client_id, bridge.selected_slot_id = "qa-app", "qa-coyote"
    bridge.device_type = "COYOTE_030"
    ovc_bridge = backend._ovc_bridge
    ovc_bridge.selected_client_id, ovc_bridge.selected_slot_id = "qa-app", "qa-ovc"
    ovc_bridge.device_type = "OVC_1"
    backend._apply_bridge({"event": "ready", "role": "hub", "lan_ip": hub.lan_ip,
                           "port": 9998, "qr_url": hub.qr_url})
    backend._apply_bridge({"event": "devices", "role": "hub", "devices": [{
        "clientId": "qa-app", "slotId": "qa-coyote", "name": "Coyote 4", "type": "COYOTE_030",
        "ready": True, "reason": "", "channelAReason": "", "channelBReason": "",
        "props": {"intensityA": 0, "intensityB": 0}}, {
        "clientId": "qa-app", "slotId": "qa-ovc", "name": "Opossum", "type": "OVC_1",
        "ready": True, "reason": "", "channelAReason": "", "channelBReason": "accessory-not-inserted",
        "props": {"intensityA": 0, "intensityB": 0}}]})
    backend._device_connected = backend._ovc_connected = True
    backend._ovc_status = "负鼠已就绪 · 单独启用振动，不影响 Pulse"
    backend.devicesChanged.emit()
    backend.changed.emit()
    window.setProperty("pageIndex", 1)
    assert window.findChild(QObject, "outputProfileChoice") is None
    assert len(backend.v4Devices) == len(backend.ovcDevices) == 1
    assert backend.v4DeviceIndex == backend.ovcDeviceIndex == 1
    assert_electrical_unchanged()


def assert_electrical_unchanged():
    assert backend.outputProfile == "coyote"
    assert (backend.lowStrength, backend.mediumStrength, backend.highStrength,
            backend.deathStrength, backend.hardCap) == electrical_levels
    assert backend.channelPolicies == electrical_policies
    assert backend.waveformCatalog == electrical_waves


def personal():
    window.setProperty("pageIndex", 2)
    assert_electrical_unchanged()


def waves():
    window.setProperty("pageIndex", 3)
    assert not any(w["key"].startswith("ovc_") for w in backend.waveformCatalog)
    assert_electrical_unchanged()


def ovc_strength():
    window.setProperty("pageIndex", 1)
    window.findChild(QObject, "openOvcConfigButton").clicked.emit()
    assert window.property("pageIndex") == 8
    workbench = window.findChild(QObject, "ovcWorkbenchPage")
    assert workbench is not None
    assert QMetaObject.invokeMethod(workbench, "showSection", Q_ARG("QVariant", "strength"))
    controller = backend.ovcController
    assert controller.outputProfile == "ovc"
    assert (controller.lowStrength, controller.hardCap) == (5, 20)
    assert len(controller.waveformCatalog) == 5
    assert all(w["key"].startswith("ovc_") for w in controller.waveformCatalog)
    assert_electrical_unchanged()


def strategy():
    workbench = window.findChild(QObject, "ovcWorkbenchPage")
    workbench.setProperty("section", "strategy")
    workbench.findChild(QObject, "openOvcStrategyA").clicked.emit()
    assert_electrical_unchanged()


def story():
    workbench = window.findChild(QObject, "ovcWorkbenchPage")
    workbench.findChild(QObject, "ovcChannelStrategyDialog").close()
    workbench.setProperty("section", "queue")
    assert_electrical_unchanged()


def english():
    window.setProperty("pageIndex", 1)
    backend.setLanguage("en")


def japanese_small():
    backend.setLanguage("ja")
    window.setWidth(1120)
    window.setHeight(720)


def chinese_small():
    backend.setLanguage("zh")


def english_workbench():
    backend.setLanguage("en")
    window.setWidth(1360)
    window.setHeight(900)
    window.findChild(QObject, "ovcWorkbenchNavButton").clicked.emit()
    assert window.property("pageIndex") == 8


def japanese_workbench():
    backend.setLanguage("ja")
    window.setWidth(1120)
    window.setHeight(720)
    window.findChild(QObject, "ovcWorkbenchPage").setProperty("section", "strategy")


def v3_with_ovc():
    window.setProperty("pageIndex", 1)
    selection = (backend._ovc_bridge.selected_client_id, backend._ovc_bridge.selected_slot_id)
    assert backend.selectSocketProtocol("v3")
    assert backend.ovcConnected
    assert selection == (backend._ovc_bridge.selected_client_id, backend._ovc_bridge.selected_slot_id)
    assert backend.ovcDeviceIndex == 1
    assert_electrical_unchanged()


steps = [(ready, "parallel-connection-zh.png"), (personal, "parallel-coyote-intensity.png"),
         (waves, "parallel-coyote-waveforms.png"), (ovc_strength, "parallel-ovc-intensity.png"),
         (strategy, "parallel-ovc-strategy.png"), (story, "parallel-ovc-story-queue.png"),
         (english, "parallel-connection-en.png"), (japanese_small, "parallel-connection-ja-small.png"),
         (chinese_small, "parallel-connection-zh-small.png"),
         (english_workbench, "parallel-ovc-workbench-en.png"),
         (japanese_workbench, "parallel-ovc-workbench-ja-small.png"),
         (v3_with_ovc, "parallel-v3-with-ovc.png")]


def run(index=0):
    global result
    if index == len(steps):
        result = 0
        app.quit()
        return
    action, filename = steps[index]
    try:
        action()
    except Exception:
        import traceback
        traceback.print_exc()
        app.quit()
        return

    def capture():
        try:
            window.findChild(QObject, "saveToast").close()
            pulse_card = window.findChild(QQuickItem, "pulseConnectionCard")
            ovc_card = window.findChild(QQuickItem, "ovcConnectionCard")
            game_card = window.findChild(QQuickItem, "gameTelemetryCard")
            socket_card = window.findChild(QQuickItem, "socketConnectionCard")
            assert pulse_card.width() >= 300 and ovc_card.width() >= 300
            assert ovc_card.x() >= pulse_card.x() + pulse_card.width()
            assert ovc_card.x() + ovc_card.width() <= ovc_card.parentItem().width() + 1
            for top in (game_card, socket_card):
                assert top is not None
                top_bottom = top.mapToItem(pulse_card.parentItem(), 0, top.height()).y()
                assert top_bottom <= pulse_card.y() + 1, "Telemetry / QR must precede controller settings"
            workbench = window.findChild(QQuickItem, "ovcWorkbenchPage")
            assert workbench is not None
            sidebar = window.findChild(QQuickItem, "sidebarStatusCard")
            assert sidebar is not None
            assert sidebar.mapToScene(QPointF(0, sidebar.height())).y() <= window.height() + 1, "Sidebar status is clipped"
            if window.property("pageIndex") == 8:
                assert workbench.isVisible()
                assert workbench.width() > 600
            assert_electrical_unchanged()
            assert window.grabWindow().save(str(root / "artifacts" / filename))
            run(index + 1)
        except Exception:
            import traceback
            traceback.print_exc()
            app.quit()
    QTimer.singleShot(450, capture)


QTimer.singleShot(250, run)
app.exec()
backend.shutdown()
engine.deleteLater()
temporary.cleanup()
raise SystemExit(result)
