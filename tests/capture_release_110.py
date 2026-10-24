"""Fresh 1.1.0 screenshots: temporary settings, simulated devices, no I/O."""
from pathlib import Path
import tempfile
import traceback
from unittest.mock import patch

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle

from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

root = Path(__file__).resolve().parents[1]
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
temporary = tempfile.TemporaryDirectory(dir=root / ".analysis")
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values.update(onboarding_completed=True, socket_protocol="v4")
config.save()
original = config.path.read_bytes()
patches = [patch("ricca_dglab.backend.ProductConfig", return_value=config),
           patch("ricca_dglab.backend.TelemetryWorker.start"),
           patch("ricca_dglab.backend.AudioCaptureWorker.start"),
           patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]),
           patch("ricca_dglab.backend.read_custom_waveforms", return_value=[]),
           patch("ricca_dglab.backend.audit.record")]
for fake in patches:
    fake.start()
backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._state = DemoReader()()
backend._stop_latched = backend._user_output_paused = True
hub = backend._v4_hub
hub.server_ready = hub.app_connected = True
hub.controller_id = "simulated-release-preview-no-server"
hub.qr_url = hub._build_qr_url()
backend._apply_bridge({"event": "ready", "role": "hub", "port": 9998,
                       "qr_url": hub.qr_url, "lan_ip": hub.lan_ip})
devices = []
for role, kind, name in (("coyote", "COYOTE_030", "Coyote"), ("ovc", "OVC_1", "Opossum")):
    sender = hub.channel(role)
    sender.selected_client_id, sender.selected_slot_id = "preview", role
    sender.device_type = kind
    sender.connected = True
    devices.append({"clientId": "preview", "slotId": role, "type": kind, "name": name,
                    "ready": True, "reason": "", "channelAReason": "", "channelBReason": "",
                    "props": {"intensityA": 0, "intensityB": 0},
                    "slotState": {"hasDevice": True}})
backend._apply_bridge({"event": "devices", "role": "hub", "devices": devices})
backend._device_connected = backend._ovc_connected = True
backend._ovc_status = "负鼠已就绪 · 等待有效游戏事件"
backend.devicesChanged.emit()
engine = QQmlApplicationEngine()
warnings = []
engine.warnings.connect(lambda messages: warnings.extend(str(item) for item in messages))
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(root / "src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects()
window = engine.rootObjects()[0]
window.setWidth(1440)
window.setHeight(1000)
jobs = [("overview", 0), ("devices", 1), ("strategy", 3),
        ("ovc", 8), ("manual", 9), ("story", 5)]
index, result = 0, 1


def find(name):
    pending, seen = [window], set()
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
    raise AssertionError(name)


def step():
    global result
    try:
        if index == len(jobs):
            assert not warnings, "\n".join(warnings)
            assert config.path.read_bytes() == original
            assert hub._loop is None and backend._bridge._loop is None
            assert not backend._output_armed and not backend._ovc_plan.allowed
            print("Six fresh 1.1.0 screenshots; no Socket/audio/output; settings unchanged.", flush=True)
            result = 0
            app.quit()
            return
        name, page = jobs[index]
        window.setProperty("pageIndex", page)
        if name in {"strategy", "ovc"}:
            find("ovcWorkbenchPage" if name == "ovc" else "pulseWorkbenchPage").setProperty("section", "battle")
        backend.changed.emit()
        QTimer.singleShot(500, capture)
    except Exception:
        traceback.print_exc()
        app.quit()


def capture():
    global index
    try:
        name, _ = jobs[index]
        assert window.grabWindow().save(str(root / "website/dist/assets/screens" / (name + ".png")))
        index += 1
        QTimer.singleShot(100, step)
    except Exception:
        traceback.print_exc()
        app.quit()


QTimer.singleShot(400, step)
QTimer.singleShot(20000, app.quit)
app.exec()
backend.shutdown()
engine.deleteLater()
temporary.cleanup()
for fake in reversed(patches):
    fake.stop()
raise SystemExit(result)
