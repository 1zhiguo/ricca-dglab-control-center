"""Real mouse input QA with isolated config, fake capture and no device output."""
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
from PySide6.QtCore import QObject, QPointF, Qt, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.product_config import ProductConfig

project = Path(__file__).resolve().parents[1]
app = QGuiApplication([])
engine = QQmlApplicationEngine()
temporary = tempfile.TemporaryDirectory(dir=project)
config = ProductConfig(Path(temporary.name) / "settings.json")
config.update({"onboarding_completed": True})
patches = [patch("ricca_dglab.backend.ProductConfig", return_value=config),
           patch("ricca_dglab.backend.TelemetryWorker.start"),
           patch("ricca_dglab.backend.AudioCaptureWorker.start"),
           patch("ricca_dglab.backend.audio_backend_available", return_value=True),
           patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[{"id": "test", "name": "系统回环 · QA 测试（不采集）"}])]
for item in patches:
    item.start()
backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
engine.rootContext().setContextProperty("backend", backend)
engine.load(QUrl.fromLocalFile(str(project / "src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects(), "QML failed to load"
window = engine.rootObjects()[0]
result = 1


def find(name):
    pending = [window]
    seen = set()
    while pending:
        item = pending.pop()
        if item is None or item in seen:
            continue
        seen.add(item)
        if item.objectName() == name:
            return item
        pending.extend(item.children())
        if isinstance(item, QQuickItem):
            pending.extend(item.childItems())
        content = item.property("contentItem")
        if isinstance(content, QObject):
            pending.append(content)
    raise AssertionError(name)


def click(name):
    item = find(name)
    point = item.mapToScene(QPointF(item.width() / 2, item.height() / 2)).toPoint()
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point)
    app.processEvents()


def shot(name):
    assert window.grabWindow().save(str(project / "artifacts" / name))


def run():
    global result
    try:
        window.setProperty("pageIndex", 6)
        QTest.qWait(250)
        click("audioEnabledSwitch")
        assert find("audioEnabledSwitch").property("checked")
        for _ in range(25):
            backend.changed.emit()
            app.processEvents()
        assert find("audioEnabledSwitch").property("checked"), "Refresh overwrote audio draft"
        assert not backend.audioEmpathyEnabled, "Draft must not start capture"
        shot("settings-audio-pending.png")
        # No worker starts: start() is mocked. Exercise the real mouse target.
        click("applyAudioSettingsButton")
        QTest.qWait(100)
        assert ProductConfig(config.path).values["audio_empathy_enabled"]
        assert find("saveToast").property("visible")
        assert find("saveToast").property("heading") == "保存成功"
        shot("settings-audio-saved.png")
        window.setProperty("pageIndex", 3)
        QTest.qWait(100)
        original = config.path.read_bytes()
        click("restoreMappingsButton")
        assert find("confirmResetDialog").property("visible")
        shot("settings-confirm-reset.png")
        click("cancelResetButton")
        assert config.path.read_bytes() == original
        click("restoreMappingsButton")
        click("confirmResetButton")
        assert backend.audioEmpathyEnabled
        assert find("saveToast").property("heading") == "保存成功"
        # Failed saves must never show success or change the saved configuration.
        with patch.object(config, "save", side_effect=OSError("QA 模拟写入失败")):
            assert not backend.saveIntensitySettings(5, 15, 25, 25, 30)
        assert find("saveToast").property("heading") == "操作失败"
        window.setWidth(1120); window.setHeight(720)
        window.setProperty("pageIndex", 6)
        QTest.qWait(150)
        shot("settings-audio-minimum.png")
        print("Audio click + refresh persistence, apply/reload, toast, confirmation cancel/confirm and failure: OK")
        result = 0
    except Exception:
        import traceback
        traceback.print_exc()
    app.quit()


QTimer.singleShot(300, run)
app.aboutToQuit.connect(backend.shutdown)
app.exec()
for item in reversed(patches):
    item.stop()
temporary.cleanup()
sys.exit(result)
