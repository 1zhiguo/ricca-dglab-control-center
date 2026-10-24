"""Manual native-Qt regression and screenshot QA for the simplified workbenches.

Run with PYTHONPATH=src. All files are temporary, telemetry and audio are
mocked, Socket workers never start, and no real device receives output.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import traceback
import sys
from unittest.mock import patch

from PySide6.QtCore import QObject, QPointF, QMetaObject, QTimer, QUrl, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtQuickControls2 import QQuickStyle

from ricca_dglab.backend import AppBackend, DemoReader, _qr_data_url
from ricca_dglab.product_config import ProductConfig


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
CHECKS_ONLY = "--checks-only" in sys.argv
REPORT_PATH = ARTIFACTS / ("redesign-ui-checks-report.json" if CHECKS_ONLY else "redesign-ui-report.json")
(ROOT / ".analysis").mkdir(exist_ok=True)
temporary = tempfile.TemporaryDirectory(dir=ROOT / ".analysis")
config = ProductConfig(Path(temporary.name) / "settings.json")
config.values.update(onboarding_completed=True, socket_protocol="v4")
config.save()
QQuickStyle.setStyle("Basic")
app = QGuiApplication([])
patches = [
    patch("ricca_dglab.backend.ProductConfig", return_value=config),
    patch("ricca_dglab.backend.TelemetryWorker.start"),
    patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]),
    patch("ricca_dglab.backend.read_custom_waveforms", return_value=[]),
    patch("ricca_dglab.backend.audit.record"),
]
for fake in patches:
    fake.start()
backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
backend._timer.stop()
backend._user_output_paused = True
backend._stop_latched = True
hub = backend._v4_hub
hub.server_ready = hub.app_connected = True
hub.controller_id = "redesign-ui-fake-app"
hub.qr_url = hub._build_qr_url()
backend._apply_bridge({"event": "ready", "role": "hub", "port": 9998,
                       "qr_url": hub.qr_url, "lan_ip": hub.lan_ip})
backend._bridge.selected_client_id, backend._bridge.selected_slot_id = "fake", "coyote"
backend._bridge.device_type = "COYOTE_030"
backend._ovc_bridge.selected_client_id, backend._ovc_bridge.selected_slot_id = "fake", "ovc"
backend._ovc_bridge.device_type = "OVC_1"
backend._apply_bridge({"event": "devices", "role": "hub", "devices": [
    {"clientId": "fake", "slotId": "coyote", "name": "Coyote 4", "type": "COYOTE_030",
     "ready": True, "reason": "", "channelAReason": "", "channelBReason": "",
     "props": {"intensityA": 0, "intensityB": 0}},
    {"clientId": "fake", "slotId": "ovc", "name": "Opossum", "type": "OVC_1",
     "ready": True, "reason": "", "channelAReason": "", "channelBReason": "accessory-not-inserted",
     "props": {"intensityA": 0, "intensityB": 0}},
]})
backend._device_connected = backend._ovc_connected = True
backend._bridge.connected = backend._ovc_bridge.connected = True
backend._ovc_status = "负鼠已就绪 · 等待有效游戏事件"
backend.devicesChanged.emit()
engine = QQmlApplicationEngine()
warnings = []
active_phase = "load"
engine.warnings.connect(lambda items: warnings.extend(f"{active_phase}: {item}" for item in items))
engine.rootContext().setContextProperty("backend", backend)
verified_sources = ["qml/ControlCenter.qml", "qml/DeviceWorkbench.qml", "qml/ChannelStrategyDialog.qml",
                    "qml/WaveLibraryDialog.qml", "qml/OnboardingDialog.qml", "assets/locales/catalog.json"]
source_hashes = {name: hashlib.sha256((ROOT / "src/ricca_dglab" / name).read_bytes()).hexdigest()
                 for name in verified_sources}
engine.load(QUrl.fromLocalFile(str(ROOT / "src/ricca_dglab/qml/ControlCenter.qml")))
assert engine.rootObjects(), "Control Center QML did not load"
window = engine.rootObjects()[0]
original_values = deepcopy(config.values)
original_bytes = config.path.read_bytes()
original_qr_source, original_qr_url = backend.qrSource, backend.qrUrl
expected_protocol = "v4"
reports = []
result = 1
REPORT_PATH.write_text(json.dumps({
    "status": "running", "source_hashes": source_hashes,
}, indent=2), encoding="utf-8")


def item(name, parent=window):
    found = parent.findChild(QQuickItem, name)
    # Repeater delegates follow the visual tree, but Qt may parent their
    # QObjects to the delegate model rather than the surrounding workbench.
    if found is None:
        pending = [parent.contentItem() if hasattr(parent, "contentItem") else parent]
        while pending:
            candidate = pending.pop()
            if candidate.objectName() == name:
                found = candidate
                break
            pending.extend(candidate.childItems())
    assert found is not None, f"Missing UI object: {name}"
    return found


def invoke(target, name, *args):
    assert QMetaObject.invokeMethod(target, name, *(Q_ARG("QVariant", value) for value in args)), name


def ancestor_with_property(target, name):
    while target is not None and target.metaObject().indexOfProperty(name) < 0:
        target = target.parentItem()
    assert target is not None, f"No ancestor with {name}"
    return target


def button_with_text(parent, text):
    for child in parent.findChildren(QObject):
        if child.metaObject().indexOfProperty("text") >= 0 and child.property("text") == text and hasattr(child, "clicked"):
            return child
    raise AssertionError(f"Missing action: {text}")


def visible_text(parent):
    """Collect text from actual rendered descendants for translation checks."""
    result = []
    for child in parent.findChildren(QQuickItem):
        if child.isVisible() and child.metaObject().indexOfProperty("text") >= 0:
            value = child.property("text")
            if isinstance(value, str) and value:
                result.append(value)
    return result


def assert_no_io_or_output():
    assert hub._loop is None and backend._bridge._loop is None and backend._ovc_bridge._loop is None
    assert not backend._output_armed and not backend._ovc_plan.allowed
    assert backend._stop_latched and backend._user_output_paused
    assert backend._audio_worker is None


def assert_no_config_changes():
    expected = deepcopy(original_values)
    expected["language"] = config.values["language"]
    # UI-only V3 fixture sets a temporary display protocol without using the
    # real switch operation or writing any settings to disk.
    expected["socket_protocol"] = expected_protocol
    assert config.values == expected
    assert config.path.read_bytes() == original_bytes, "Navigation or drafts wrote settings.json"


def refresh_game():
    backend._last_received = time.monotonic()
    backend._reader_error = ""
    backend._state = {"status": "ok", "connected": True, "build_supported": True,
                      "process_id": 42, "scene": "gameplay", "current_hp": 31, "max_hp": 31,
                      "stage": {"system_name": "StageName_07", "all_resource_loaded": True},
                      "game_ui": {"is_user_pause": False}}
    backend.changed.emit()


def set_case(language, width, height, device, section):
    global expected_protocol
    # Deliberately do not call the persistent language preference setter here.
    config.values["language"] = language
    expected_protocol = "v3" if section == "v3-ovc-qr" else "v4"
    config.values["socket_protocol"] = expected_protocol
    backend._qr_source, backend._qr_url = original_qr_source, original_qr_url
    backend.languageChanged.emit()
    window.setWidth(width)
    window.setHeight(height)
    refresh_game()
    hub.app_connected = True
    backend._onboarding_active = False
    backend._device_connected = backend._ovc_connected = True
    backend._bridge.connected = backend._ovc_bridge.connected = True
    backend._ovc_status = "负鼠已就绪 · 等待有效游戏事件"
    backend.changed.emit()
    for name in ("waveLibraryDialog", "onboardingDialog"):
        dialog = window.findChild(QObject, name)
        if dialog:
            dialog.close()
    for confirmation in window.findChildren(QObject, "confirmResetDialog"):
        confirmation.close()
    for dialog in window.findChildren(QObject):
        if dialog.metaObject().indexOfProperty("imageSource") >= 0 and dialog.metaObject().indexOfProperty("stepTitle") >= 0:
            dialog.close()
    for prefix in ("pulse", "ovc"):
        dialog = window.findChild(QObject, prefix + "ChannelStrategyDialog")
        if dialog:
            dialog.close()
    if device == "connection":
        window.setProperty("pageIndex", 1)
        page = ancestor_with_property(item("connectionDetailsButton"), "detailsExpanded")
        page.setProperty("detailsExpanded", False)
        page.setProperty("qrExpanded", False)
        page.property("contentItem").setProperty("contentY", 0)
        if section == "details":
            item("connectionDetailsButton").clicked.emit()
        elif section == "qr":
            item("toggleConnectionQrButton").clicked.emit()
        elif section == "disconnected":
            hub.app_connected = False
            backend._device_connected = backend._ovc_connected = False
            backend._bridge.connected = backend._ovc_bridge.connected = False
            backend._ovc_status = "负鼠未连接"
            backend.changed.emit()
        elif section == "v3-ovc-qr":
            backend._device_connected = False
            backend._bridge.connected = False
            backend._qr_url = "https://www.dungeon-lab.com/app-download.php#DGLAB-SOCKET#ws://127.0.0.1:9999/fake-v3"
            backend._qr_source = _qr_data_url(backend._qr_url)
            backend.changed.emit()
            app.processEvents()
            qr_button = item("ovcQrButton")
            assert qr_button.isVisible() and qr_button.property("enabled")
            assert not page.property("appConnected") and page.property("showQr"), "OVC App hid unconnected V3 QR"
            qr_button.clicked.emit()
            preview = next(dialog for dialog in window.findChildren(QObject)
                           if dialog.metaObject().indexOfProperty("imageSource") >= 0
                           and dialog.metaObject().indexOfProperty("stepTitle") >= 0)
            assert preview.property("visible")
            assert preview.property("imageSource").toString() == backend.v4QrSource
            assert backend.socketProtocol == "v3", "Opening OVC QR switched Pulse protocol"
            preview.close()
    elif device == "library":
        window.setProperty("pageIndex", 3)
        library = window.findChild(QObject, "waveLibraryDialog")
        library.setProperty("advanced", False)
        library.open()
        if section == "fixed-confirm":
            item("advancedWaveActionsButton").clicked.emit()
            button_with_text(library, "应用固定波形").clicked.emit()
    elif device == "tutorial":
        guide = window.findChild(QObject, "onboardingDialog")
        invoke(guide, "openGuide")
        guide.setProperty("step", int(section))
    else:
        window.setProperty("pageIndex", 3 if device == "pulse" else 8)
        workbench = item(device + "WorkbenchPage")
        workbench.setProperty("queueExpanded", False)
        workbench.setProperty("audioExpanded", False)
        canonical = {"queue-detail": "story", "audio-detail": "story", "event-detail": "battle"}.get(section, section)
        invoke(workbench, "showSection", canonical)
        if section == "queue-detail":
            invoke(workbench, "showQueue", "A")
        elif section == "audio-detail":
            workbench.setProperty("audioExpanded", True)
        elif section == "event-detail":
            app.processEvents()
            item("editBattleRule_damage_light", workbench).clicked.emit()
    toast = window.findChild(QObject, "saveToast")
    if toast:
        toast.close()


def assert_frame(device, section):
    assert_no_config_changes()
    assert_no_io_or_output()
    sidebar = item("sidebarStatusCard")
    assert sidebar.mapToScene(QPointF(0, sidebar.height())).y() <= window.height() + 1
    if device == "connection":
        cards = [item(name) for name in ("gameTelemetryCard", "socketConnectionCard",
                                        "pulseConnectionCard", "ovcConnectionCard")]
        for card in cards:
            assert card.width() > 260 and card.height() > 80, card.objectName()
            assert card.x() >= -1 and card.x() + card.width() <= card.parentItem().width() + 1
        assert abs(cards[2].height() - cards[3].height()) <= 1, "Controller cards are no longer symmetric"
        if section == "details":
            assert item("connectionAdvancedDetails").isVisible()
        elif section in {"qr", "disconnected", "v3-ovc-qr"}:
            qr = item("connectionQrImage")
            assert qr.isVisible() and qr.width() >= 100 and qr.height() >= 100
            assert qr.property("source").toString().startswith("data:image/")
            if section == "v3-ovc-qr":
                assert item("ovcQrButton").isVisible() and backend.socketProtocol == "v3"
    elif device == "library":
        library = window.findChild(QObject, "waveLibraryDialog")
        assert library.property("visible")
        assert library.property("width") <= window.width() - 40
        if section == "fixed-confirm":
            confirmation = library.findChild(QObject, "confirmResetDialog")
            assert confirmation.property("visible")
            assert confirmation.property("heading") == "将当前波形应用到全部事件？"
            assert confirmation.property("confirmLabel") == "确认应用"
    elif device == "tutorial":
        guide = window.findChild(QObject, "onboardingDialog")
        assert guide.property("visible") and guide.property("step") == int(section)
        assert item("onboardingNext").property("enabled")
    else:
        assert_workbench_frame(device, section)


def assert_workbench_frame(device, section):
    workbench = item(device + "WorkbenchPage")
    assert workbench.isVisible() and workbench.width() >= 700
    canonical = {"queue-detail": "story", "audio-detail": "story", "event-detail": "battle"}.get(section, section)
    assert workbench.property("section") == canonical
    if section == "event-detail":
        dialog = workbench.findChild(QObject, device + "ChannelStrategyDialog")
        assert dialog.property("visible")
        assert dialog.property("focusedRuleKey") == "damage_light"
        rows = dialog.property("ruleRows")
        assert len(rows.toVariant() if hasattr(rows, "toVariant") else rows) == 1
    buttons = [item(device + suffix, workbench) for suffix in (
        "StrengthSectionButton", "StrategySectionButton", "QueueSectionButton")]
    for button in buttons:
        assert button.isVisible() and button.width() > 90 and button.height() >= 36
        assert button.mapToItem(workbench, 0, 0).x() >= 0
        assert button.mapToItem(workbench, button.width(), 0).x() <= workbench.width() + 1
        content = button.property("contentItem")
        if isinstance(content, QQuickItem):
            assert content.property("implicitWidth") <= content.width() + 2, (
                device, section, "Tab text clipped", content.property("text"))
    assert len({round(button.y(), 1) for button in buttons}) == 1
    if section == "strength":
        assert not workbench.property("strengthDirty")
    if backend.language == "en":
        for button in buttons:
            texts = visible_text(button)
            assert texts and all(not any("\u3400" <= ch <= "\u9fff" for ch in text) for text in texts), texts


cases = [(language, width, height, device, section)
         for language in ("zh", "en", "ja")
         for width, height in ((1360, 900), (1120, 720))
         for device, section in [("connection", ""),
                                 ("pulse", "strength"), ("pulse", "battle"), ("pulse", "story"),
                                 ("ovc", "strength"), ("ovc", "battle"), ("ovc", "story")]]
cases += [(language, 1120, 720, device, detail)
          for language in ("zh", "en", "ja")
          for device in ("pulse", "ovc")
          for detail in ("event-detail", "queue-detail", "audio-detail")]
cases += [(language, 1120, 720, device, detail)
          for language in ("zh", "en", "ja")
          for device, detail in [("connection", "details"), ("connection", "qr"),
                                 ("connection", "disconnected"), ("library", "preview"),
                                 ("library", "fixed-confirm"),
                                 *(("tutorial", str(step)) for step in range(4))]]
cases += [(language, 1120, 720, "connection", "v3-ovc-qr") for language in ("zh", "en", "ja")]
if CHECKS_ONLY:
    cases = []


def check_drafts_and_isolated_saves():
    """Verify unsaved edits stay local and explicit saves stay per-device."""
    global expected_protocol, active_phase
    active_phase = "draft-navigation"
    expected_protocol = "v4"
    config.values["socket_protocol"] = "v4"
    backend.changed.emit()
    pulse, ovc = item("pulseWorkbenchPage"), item("ovcWorkbenchPage")
    for workbench in (pulse, ovc):
        original_low = workbench.property("draftLow")
        workbench.setProperty("draftLow", original_low + 1)
        assert workbench.property("strengthDirty")
        invoke(workbench, "showSection", "battle")
        invoke(workbench, "showSection", "story")
        invoke(workbench, "showSection", "strength")
        assert workbench.property("draftLow") == original_low + 1, "Navigation discarded unsaved strength draft"
        assert_no_config_changes()
        invoke(workbench, "loadSaved")
        assert workbench.property("draftLow") == original_low and not workbench.property("strengthDirty")
    # Preserve intentionally invalid/out-of-cap drafts too; no setter auto-applies them.
    ovc.setProperty("draftLow", 99)
    assert not ovc.property("valid")
    assert_no_config_changes()
    invoke(ovc, "loadSaved")
    before = deepcopy(config.values)
    active_phase = "save-pulse-intensity"
    pulse.setProperty("draftLow", backend.lowStrength + 1)
    item("saveIntensityButton", pulse).clicked.emit()
    assert config.values["ovc_profile"] == before["ovc_profile"], "Pulse save modified OVC profile"
    assert backend.lowStrength == before["strength_low"] + 1
    assert ProductConfig(config.path).values == config.values
    after_pulse = deepcopy(config.values)
    active_phase = "save-ovc-intensity"
    ovc.setProperty("draftLow", 10)
    item("saveOvcIntensityButton", ovc).clicked.emit()
    assert {key: value for key, value in config.values.items() if key != "ovc_profile"} == {
        key: value for key, value in after_pulse.items() if key != "ovc_profile"}, "OVC save modified Pulse settings"
    assert backend.ovcController.lowStrength == 10
    assert ProductConfig(config.path).values == config.values
    assert_no_io_or_output()


def check_stable_models_and_policy_refresh():
    """Telemetry must not rebuild event delegates; real policy changes must."""
    global active_phase
    for prefix, controller in (("pulse", backend), ("ovc", backend.ovcController)):
        active_phase = prefix + "-cache-and-policy-save"
        workbench = item(prefix + "WorkbenchPage")
        invoke(workbench, "showSection", "battle")
        app.processEvents()
        original_row = item("battleRule_damage_light", workbench)
        for _ in range(20):
            backend.changed.emit()
            backend.ovcController.changed.emit()
        app.processEvents()
        assert item("battleRule_damage_light", workbench) is original_row, "Unchanged telemetry recreated event delegates"
        original = deepcopy(config.values)
        policy = deepcopy(controller.channelPolicies["A"])
        wave = next(wave["key"] for wave in controller.waveformCatalog if wave["key"] != policy["rules"]["damage_light"]["wave"])
        policy["rules"]["damage_light"]["wave"] = wave
        assert controller.saveChannelPolicy("A", policy)
        app.processEvents()
        updated = item("battleRule_damage_light", workbench).property("rule")
        assert (updated.toVariant() if hasattr(updated, "toVariant") else updated)["wave"] == wave
        if prefix == "pulse":
            assert config.values["ovc_profile"] == original["ovc_profile"]
        else:
            assert {key: value for key, value in config.values.items() if key != "ovc_profile"} == {
                key: value for key, value in original.items() if key != "ovc_profile"}
        assert_no_io_or_output()


def check_focused_event_save_preserves_metadata():
    """A quick event edit must not rewrite advanced/legacy policy fields."""
    global active_phase
    for prefix, controller in (("pulse", backend), ("ovc", backend.ovcController)):
        active_phase = prefix + "-focused-event-save"
        seed = deepcopy(controller.channelPolicies["A"])
        seed.update(mode="action_audio", story_mode="queue_audio",
                    damage_light_max=1.234, damage_medium_max=5.678)
        assert controller.saveChannelPolicy("A", seed)
        baseline = deepcopy(controller.channelPolicies)
        original = deepcopy(config.values)
        expected = deepcopy(baseline["A"])
        expected["rules"]["hit_normal"]["duration"] = 1.75
        assert expected["damage_light_max"] == 1.234 and expected["damage_medium_max"] == 5.678
        dialog = item(prefix + "WorkbenchPage").findChild(QObject, prefix + "ChannelStrategyDialog")
        invoke(dialog, "openEvent", "A", "hit_normal")
        assert dialog.property("focusedRuleKey") == "hit_normal"
        assert dialog.property("selectedMode") == "action", "Fixture must exercise legacy mode normalization"
        invoke(dialog, "setRule", "hit_normal", "duration", 1.75)
        invoke(dialog, "save")
        assert not dialog.property("visible"), "Focused event save failed"
        assert controller.channelPolicies["A"] == expected, "Event save rewrote unrelated rules, metadata, or fractional thresholds"
        assert controller.channelPolicies["B"] == baseline["B"], "Event save changed channel B"
        if prefix == "pulse":
            assert config.values["ovc_profile"] == original["ovc_profile"]
        else:
            assert {key: value for key, value in config.values.items() if key != "ovc_profile"} == {
                key: value for key, value in original.items() if key != "ovc_profile"}
        assert ProductConfig(config.path).values == config.values
        assert_no_io_or_output()


def check_shared_audio_status_notify():
    """Global listening notifications update OVC without its own signal."""
    global active_phase
    window.setProperty("pageIndex", 8)
    workbench = item("ovcWorkbenchPage")
    invoke(workbench, "showSection", "story")
    workbench.setProperty("audioExpanded", True)
    previous = config.values["audio_empathy_enabled"]
    saved_bytes = config.path.read_bytes()
    for enabled in (False, True, False):
        active_phase = "shared-audio-notify-" + str(enabled)
        config.values["audio_empathy_enabled"] = enabled
        backend.changed.emit()  # Intentionally do not emit OvcController.changed.
        app.processEvents()
        expected = "音频监听已开启" if enabled else "音频监听未开启，音频模式暂不响应。"
        assert backend.localize(expected, backend.language) in visible_text(workbench), "OVC audio-listening label stayed stale"
        assert config.path.read_bytes() == saved_bytes
        assert_no_io_or_output()
    config.values["audio_empathy_enabled"] = previous
    backend.changed.emit()


def run(index=0):
    global result, active_phase
    if index == len(cases):
        try:
            check_drafts_and_isolated_saves()
            check_stable_models_and_policy_refresh()
            check_focused_event_save_preserves_metadata()
            check_shared_audio_status_notify()
            assert source_hashes == {
                name: hashlib.sha256((ROOT / "src/ricca_dglab" / name).read_bytes()).hexdigest()
                for name in verified_sources}, "UI source changed during capture; rerun screenshots against frozen source"
            assert not warnings, "QML warnings:\n" + "\n".join(warnings)
            REPORT_PATH.write_text(json.dumps({
                "status": "passed",
                "screenshots": reports, "config_navigation_unchanged": True,
                "independent_explicit_saves": True, "real_output": False,
                "stable_telemetry_delegate_models": True, "saved_policy_summary_refresh": True,
                "focused_event_metadata_preserved": True, "shared_audio_status_notify": True,
                "source_hashes": source_hashes,
                "qml_warnings": warnings,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Unified UI: {len(reports)} screenshots, no-write navigation, retained drafts, isolated saves passed; no real output.", flush=True)
            result = 0
        except Exception:
            traceback.print_exc()
            REPORT_PATH.write_text(json.dumps({
                "status": "failed", "screenshots": reports, "qml_warnings": warnings,
                "source_hashes": source_hashes,
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        app.quit()
        return
    language, width, height, device, section = cases[index]
    active_phase = f"{language}-{width}-{device}-{section}"
    try:
        set_case(*cases[index])
    except Exception:
        traceback.print_exc()
        app.quit()
        return

    def capture():
        try:
            refresh_game()
            assert_frame(device, section)
            if section in {"queue-detail", "audio-detail"}:
                workbench = item(device + "WorkbenchPage")
                flickable = item(device + "StoryQueueEditor", workbench).parentItem()
                while flickable and flickable.metaObject().indexOfProperty("contentY") < 0:
                    flickable = flickable.parentItem()
                assert flickable is not None, "Expanded story controls have no scroll viewport"
                target = max(0, flickable.property("contentHeight") - flickable.height()) if section == "audio-detail" else 240
                flickable.setProperty("contentY", target)
            elif device == "connection" and section == "details":
                flickable = ancestor_with_property(item("connectionAdvancedDetails"), "contentY")
                flickable.setProperty("contentY", max(0, flickable.property("contentHeight") - flickable.height()))
            elif device == "connection":
                page = ancestor_with_property(item("connectionDetailsButton"), "detailsExpanded")
                page.property("contentItem").setProperty("contentY", 0)
            filename = f"redesign-{language}-{width}-{device}{'-' + section if section else ''}.png"
            assert window.grabWindow().save(str(ARTIFACTS / filename))
            reports.append(filename)
            run(index + 1)
        except Exception:
            traceback.print_exc()
            app.quit()
    QTimer.singleShot(250, capture)


QTimer.singleShot(250, run)
app.exec()
backend.shutdown()
engine.deleteLater()
for fake in reversed(patches):
    fake.stop()
temporary.cleanup()
raise SystemExit(result)
