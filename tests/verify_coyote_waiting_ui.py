"""Render retained Coyote selection while waiting; fake slots, no hardware I/O."""
from copy import deepcopy
from pathlib import Path
import tempfile
import time
import traceback
from unittest.mock import patch

from PySide6.QtCore import QObject, QPointF, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.ovc_pipeline import OvcOutputPlan
from ricca_dglab.product_config import ProductConfig


root = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values.update(onboarding_completed=True, socket_protocol="v4")
original_config = deepcopy(config.values)
with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
        patch("ricca_dglab.backend.TelemetryWorker.start"), \
        patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
    backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
hub = backend._v4_hub
hub.controller_id = "coyote-waiting-ui-mock"
hub.server_ready = hub.app_connected = True
hub.qr_url = hub._build_qr_url()
backend._apply_bridge({"event": "ready", "role": "hub", "protocol": "v4",
                       "qr_url": hub.qr_url, "port": 9998, "lan_ip": hub.lan_ip})
backend._bridge.selected_client_id = backend._ovc_bridge.selected_client_id = "qa-app"
backend._bridge.selected_slot_id, backend._bridge.device_type = "qa-coyote", "COYOTE_030"
backend._ovc_bridge.selected_slot_id, backend._ovc_bridge.device_type = "qa-ovc", "OVC_1"
backend._ovc_bridge.connected = backend._ovc_connected = True
backend._ovc_route_paused = False
backend._ovc_status = "负鼠振动同步中"
ovc_plan = OvcOutputPlan(strength_a=7, wave_a="ovc_beat", hard_cap=20,
                         allowed=True, paused=False, reason="fake-ui-only")
backend._ovc_plan = ovc_plan
devices = [{
    "clientId": "qa-app", "slotId": "qa-coyote", "name": "Coyote 4", "type": "COYOTE_030",
    "ready": False, "reason": "bluetooth-not-connected", "channelAReason": "bluetooth-not-connected",
    "channelBReason": "bluetooth-not-connected", "slotState": {"hasDevice": False},
    # The regression: cached Bluetooth properties can disagree with slot readiness.
    "props": {"connectState": 1, "intensityA": 0, "intensityB": 0}}, {
    "clientId": "qa-app", "slotId": "qa-ovc", "name": "Opossum", "type": "OVC_1",
    "ready": True, "reason": "", "channelAReason": "", "channelBReason": "",
    "slotState": {"hasDevice": True}, "props": {"connectState": 1, "intensityA": 7, "intensityB": 0}}]
backend._apply_bridge({"event": "devices", "role": "hub", "protocol": "v4", "devices": devices})
backend._device_connected = True
backend._pulse_route_paused = False
backend._output_armed = True
backend._apply_bridge({"event": "waiting", "role": "coyote", "protocol": "v4",
                       "target_id": "qa-app", "slot_id": "qa-coyote", "device_type": "COYOTE_030"})
backend._state = {"status": "ok", "connected": True, "process_id": 42, "build_supported": True,
                  "scene": "gameplay", "current_hp": 31, "max_hp": 31,
                  "current_mp": 50, "max_mp": 50, "player_address": "0x123",
                  "stage": {"name": "StageName_07", "all_resource_loaded": True},
                  "game_ui": {"is_user_pause": False}}
backend._last_received = time.monotonic()
backend.changed.emit()
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda items: warnings.extend(str(item) for item in items))
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects(), "Control Center QML did not load"
window = engine.rootObjects()[0]
window.setWidth(1120)
window.setHeight(720)
window.setProperty("pageIndex", 1)
result = 1


def item(name):
    value = window.findChild(QQuickItem, name)
    assert value is not None, f"Missing UI object: {name}"
    return value


def scroll_to_controllers():
    card = item("pulseConnectionCard")
    flickable = card.parentItem()
    while flickable is not None and not flickable.inherits("QQuickFlickable"):
        flickable = flickable.parentItem()
    assert flickable is not None
    flickable.setProperty("contentY", max(0, flickable.property("contentHeight") - flickable.height()))


def assert_waiting(muted=False):
    assert backend.v4DeviceIndex == 1
    assert not backend.deviceConnected
    assert backend.pulseRoutePaused and not backend._output_armed
    assert backend.v4DeviceStatus.startswith("通道已静音" if muted else "等待设备就绪")
    assert backend.pulseDeviceMuted == muted
    choice = item("v4DeviceChoice")
    assert choice.property("currentIndex") == 1
    assert "Coyote 4" in choice.property("currentText")
    assert item("pulseRoutePauseButton").property("enabled")
    assert item("pulseRoutePauseButton").property("unavailable")
    assert backend.ovcDeviceIndex == 1 and backend.ovcConnected
    assert backend._ovc_plan == ovc_plan and backend._ovc_plan.allowed
    assert not backend.ovcRoutePaused
    assert item("ovcRoutePauseButton").property("enabled")
    assert item("pulseConnectionCard").property("readiness") == 1
    assert item("ovcConnectionCard").property("readiness") == 2
    assert backend._bridge._loop is None and hub._loop is None


cases = [(language, mode) for language in ("zh", "en", "ja") for mode in ("initial", "updates", "muted")]


def run(index=0):
    global result
    if index == len(cases):
        try:
            assert not warnings, "QML warnings:\n" + "\n".join(warnings)
            assert {key: value for key, value in config.values.items() if key != "language"} == {
                key: value for key, value in original_config.items() if key != "language"}
            print("Coyote waiting/mute UI: 9 states and 3 help screenshots passed; no sockets or outputs.", flush=True)
            result = 0
        except Exception:
            traceback.print_exc()
        finally:
            app.quit()
        return
    language, mode = cases[index]
    repeated, muted = mode == "updates", mode == "muted"
    try:
        backend.setLanguage(language)
        incoming=deepcopy(devices)
        if muted:
            incoming[0].update(reason="channel-muted",channelAReason="channel-muted",channelBReason="channel-muted")
            incoming[0]["slotState"]={"hasDevice":True,"channelA":{"isMuted":True},"channelB":{"isMuted":True}}
        backend._apply_bridge({"event":"devices","role":"hub","protocol":"v4","devices":incoming})
        backend._apply_bridge({"event":"waiting","role":"coyote","protocol":"v4","target_id":"qa-app","slot_id":"qa-coyote"})
        if repeated:
            for update in range(12):
                incoming = deepcopy(devices)
                incoming[0]["props"]["updateSequence"] = update
                backend._apply_bridge({"event": "devices", "role": "hub", "protocol": "v4", "devices": incoming})
                backend.changed.emit()
        backend._last_received = time.monotonic()
        backend.changed.emit()
    except Exception:
        traceback.print_exc()
        app.quit()
        return

    def capture():
        try:
            backend._last_received = time.monotonic()
            backend.changed.emit()
            scroll_to_controllers()
            assert_waiting(muted)
            window.findChild(QObject, "saveToast").close()
            sidebar = item("sidebarStatusCard")
            assert sidebar.mapToScene(QPointF(0, sidebar.height())).y() <= window.height() + 1
            name = f"coyote-waiting-{language}-{mode}.png"
            assert window.grabWindow().save(str(root / "artifacts" / name))
            if muted:
                item("pulseRoutePauseButton").clicked.emit()
                toast=window.findChild(QObject,"saveToast")
                assert toast.property("heading")=="暂时无法启用" and toast.property("visible")
                assert "静音" in toast.property("message")
                assert_waiting(True)
                assert window.grabWindow().save(str(root / "artifacts" / f"coyote-muted-guide-{language}.png"))
                toast.close()
            run(index + 1)
        except Exception:
            traceback.print_exc()
            app.quit()
    QTimer.singleShot(400, capture)


QTimer.singleShot(250, run)
app.exec()
backend.shutdown()
engine.deleteLater()
temporary.cleanup()
raise SystemExit(result)
