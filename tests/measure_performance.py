"""Isolated native-UI resource/heartbeat probe. Never opens a device or microphone."""
import argparse
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import statistics
import tempfile
import time
from unittest.mock import patch

from PySide6.QtCore import QObject, QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from ricca_dglab import audit
from ricca_dglab.backend import AppBackend, DemoReader
from ricca_dglab.models import GameEvent
from ricca_dglab.product_config import ProductConfig
from test_core import gameplay
from test_capture import snapshot
from test_scene_library import anv


class NullBridge:
    available_lan_interfaces = []
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class MemoryCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize",
        "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
        "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage", "PrivateUsage")]


def memory():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    handle = kernel.GetCurrentProcess()
    values, handles = MemoryCounters(), wintypes.DWORD()
    values.cb = ctypes.sizeof(values)
    if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(values), values.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    kernel.GetProcessHandleCount(handle, ctypes.byref(handles))
    return {"working_mb": round(values.WorkingSetSize / 1048576, 2),
            "private_mb": round(values.PrivateUsage / 1048576, 2), "handles": handles.value}


def percentile(values, q):
    return round(sorted(values)[min(len(values) - 1, int((len(values) - 1) * q))], 3) if values else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds-per-phase", type=float, default=12)
    parser.add_argument("--language", choices=["zh", "en", "ja"], default="zh")
    args = parser.parse_args()
    if not 5 <= args.seconds_per_phase <= 60:
        parser.error("seconds-per-phase must be 5..60")
    project = Path(__file__).resolve().parents[1]
    app = QGuiApplication([])
    temporary = tempfile.TemporaryDirectory(dir=project)
    config = ProductConfig(Path(temporary.name) / "settings.json")
    config.values["onboarding_completed"] = True
    config.values["language"] = args.language
    config.values["channel_policies"]["A"]["story_mode"] = "queue"
    config.values["channel_policies"]["B"]["story_mode"] = "queue_audio"
    audit.configure(Path(temporary.name) / "performance.jsonl")
    with patch("ricca_dglab.backend.ProductConfig", return_value=config), \
         patch("ricca_dglab.backend.TelemetryWorker.start"), \
         patch("ricca_dglab.backend.enumerate_audio_devices", return_value=[]):
        backend = AppBackend(DemoReader(), demo=True, start_bridge=False)
    backend._timer.stop()
    backend._demo, backend._device_connected = False, True  # Simulated binding only.
    backend._bridge = NullBridge()
    backend._config.values["audio_empathy_enabled"] = True  # Samples injected, no worker.
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(project / "src/ricca_dglab/qml/ControlCenter.qml")))
    if not engine.rootObjects():
        raise RuntimeError("QML failed to load")
    window = engine.rootObjects()[0]
    strategy = window.findChild(QObject, "channelStrategyDialog")
    phases = ["idle_error", "combat_events", "capture_hold", "story_audio_queue", "ui_switching", "idle_recovery"]
    results, drains, heartbeats, mem_samples = [], [], [], []
    started = time.perf_counter()
    phase_started, cpu_started, last_heartbeat = started, time.process_time(), started
    index, ticks, previous_ui = 0, 0, -1
    peak_preview = 0.0
    failed = []

    def guarded(callback):
        def run():
            try:
                callback()
            except Exception as error:
                import traceback
                traceback.print_exc()
                failed.append(str(error))
                app.quit()
        return run

    def drain():
        nonlocal peak_preview
        t = time.perf_counter()
        backend._drain()
        drains.append((time.perf_counter() - t) * 1000)
        peak_preview = max(peak_preview, backend.previewA, backend.previewB)

    def inject():
        nonlocal ticks, previous_ui
        ticks += 1
        phase, now = phases[index], time.monotonic()
        if phase in {"idle_error", "idle_recovery"}:
            if ticks % 13 == 0:
                backend._queue.put(("telemetry_error", {"detail":"SIMULATED game not running"}))
            return
        state = (snapshot(status="ok", connected=True, build_supported=True, process_id=42) if phase == "capture_hold" else anv() if phase in {"story_audio_queue", "ui_switching"}
                 else gameplay(process_id=42))
        backend._queue.put(("telemetry", {"state":state, "received_at":now, "latency_ms":1}))
        if phase in {"story_audio_queue", "ui_switching"}:
            backend._queue.put(("audio_sample", {"received_at":now, "rms":.2 + .15 * math.sin(now * 3),
                                                  "peak":.5, "points":[10,30,80,100,40,10,0,0]*2}))
        if phase == "combat_events" and ticks % 7 == 0:
            backend._mapping.accept([GameEvent(ticks,now,"test","damage","hit",data={"amount":4}),
                                     GameEvent(ticks+100000,now,"test","action","hit",data={"action":"stand_damage"})])
        if phase == "ui_switching":
            page = int((time.perf_counter() - phase_started) * 3) % 8
            if page != previous_ui:
                strategy.close()
                window.setProperty("pageIndex", page)
                if page == 3:
                    strategy.openChannel("A")
                    strategy.setProperty("category", "story" if ticks % 2 else "battle")
                previous_ui = page

    def heartbeat():
        nonlocal last_heartbeat
        now = time.perf_counter()
        heartbeats.append(max(0, now - last_heartbeat - .05) * 1000)
        last_heartbeat = now

    def sample():
        nonlocal index, phase_started, cpu_started, last_heartbeat, previous_ui, peak_preview
        now = time.perf_counter()
        mem_samples.append(memory())
        if now - phase_started < args.seconds_per_phase:
            return
        cpu = (time.process_time() - cpu_started) / (now - phase_started) * 100
        result = {"phase":phases[index], "seconds":round(now-phase_started,2),
                  "cpu_one_core_percent":round(cpu,2), "cpu_machine_percent":round(cpu / (os.cpu_count() or 1),3),
                  "heartbeat_late_p95_ms":percentile(heartbeats,.95), "heartbeat_late_max_ms":round(max(heartbeats,default=0),3),
                  "drain_p95_ms":percentile(drains,.95), "drain_max_ms":round(max(drains,default=0),3),
                  "memory_start":mem_samples[0], "memory_end":mem_samples[-1],
                  "private_peak_mb":max(row["private_mb"] for row in mem_samples),
                  "queue_backlog":backend._queue.qsize(), "peak_simulated_preview":peak_preview, "audit":audit.status()}
        if phases[index] in {"combat_events", "capture_hold", "story_audio_queue"} and peak_preview <= 0:
            raise AssertionError("Scenario did not exercise output preview: " + phases[index])
        results.append(result)
        print(json.dumps(result,ensure_ascii=False), flush=True)
        index += 1
        if index == len(phases):
            out = {"logical_cpus":os.cpu_count(), "synthetic":True, "seconds":round(now-started,2),
                   "no_device_no_microphone":True,"phases":results,"errors":failed}
            destination = project / "artifacts/performance-ui.json"
            destination.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
            print("REPORT " + str(destination),flush=True)
            app.quit()
            return
        strategy.close()
        window.setProperty("pageIndex", 4 if phases[index] in {"combat_events", "story_audio_queue"} else 0)
        if phases[index] == "idle_recovery":
            backend._config.values["audio_empathy_enabled"] = False
        phase_started, cpu_started, last_heartbeat = now, time.process_time(), now
        previous_ui = -1
        peak_preview = 0.0
        drains.clear(); heartbeats.clear(); mem_samples.clear()

    # Preheat the native renderer before attributing steady-state resource use.
    window.grabWindow().save(str(project / "artifacts/rounded-avatar-overview.png"))
    avatar = window.findChild(QObject, "riccaBrandAvatar")
    assert avatar is not None and avatar.property("radius") == 10
    timers = []
    for interval, callback in ((33,drain),(75,inject),(50,heartbeat),(1000,sample)):
        timer = QTimer()
        timer.setInterval(interval)
        timer.timeout.connect(guarded(callback))
        timer.start()
        timers.append(timer)
    QTimer.singleShot(int((len(phases) * args.seconds_per_phase + 30) * 1000), app.quit)
    app.exec()
    backend.shutdown()
    audit.close()
    temporary.cleanup()
    if failed or len(results) != len(phases):
        raise RuntimeError("Incomplete probe: " + repr(failed))


if __name__ == "__main__":
    main()
