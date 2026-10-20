"""Measure import/Qt/renderer memory layers in a fresh, device-free process."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile


class Memory(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in ("peak", "working", "paged_peak", "paged",
        "nonpaged_peak", "nonpaged", "pagefile", "pagefile_peak", "private")]


class Thread(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD),
                ("id", wintypes.DWORD), ("pid", wintypes.DWORD),
                ("base", wintypes.LONG), ("delta", wintypes.LONG), ("flags", wintypes.DWORD)]


def measure(stage):
    kernel, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(Thread)]
    kernel.Thread32Next.argtypes = kernel.Thread32First.argtypes
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
    values = Memory(); values.cb = ctypes.sizeof(values)
    assert psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(values), values.cb)
    snapshot = kernel.CreateToolhelp32Snapshot(4, 0)
    thread = Thread(); thread.size = ctypes.sizeof(thread)
    count, more = 0, kernel.Thread32First(snapshot, ctypes.byref(thread))
    while more:
        count += thread.pid == os.getpid()
        more = kernel.Thread32Next(snapshot, ctypes.byref(thread))
    kernel.CloseHandle(snapshot)
    row = {"stage":stage,"working_mb":round(values.working/1048576,2),
           "private_mb":round(values.private/1048576,2),"threads":count}
    print(json.dumps(row),flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blas-threads", type=int)
    parser.add_argument("--tag", default="baseline")
    parser.add_argument("--production", action="store_true", help="import audio through the production initialization path")
    args = parser.parse_args()
    if args.blas_threads:
        os.environ["OPENBLAS_NUM_THREADS"] = str(args.blas_threads)
        os.environ["OMP_NUM_THREADS"] = str(args.blas_threads)
    report = [measure("python")]
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow
    report.append(measure("Qt imports"))
    if args.production:
        from ricca_dglab import audio_pulse
        report.append(measure("production audio runtime"))
    else:
        import numpy
        report.append(measure("numpy"))
        import soundcard
        report.append(measure("SoundCard"))
    from unittest.mock import patch
    from ricca_dglab.backend import AppBackend, DemoReader
    from ricca_dglab.product_config import ProductConfig
    report.append(measure("backend imports"))
    app = QGuiApplication([])
    report.append(measure("QGuiApplication"))
    project = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(dir=project) as directory:
        config = ProductConfig(Path(directory)/"settings.json")
        config.values["onboarding_completed"] = True
        with patch("ricca_dglab.backend.ProductConfig",return_value=config), \
             patch("ricca_dglab.backend.TelemetryWorker.start"), \
             patch("ricca_dglab.backend.enumerate_audio_devices",return_value=[]):
            backend = AppBackend(DemoReader(),demo=True,start_bridge=False)
        backend._timer.stop()
        report.append(measure("backend instance"))
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("backend",backend)
        engine.load(QUrl.fromLocalFile(str(project/"src/ricca_dglab/qml/ControlCenter.qml")))
        assert engine.rootObjects()
        report.append(measure("QML loaded"))
        def finish():
            window = engine.rootObjects()[0]
            window.grabWindow()
            report.append(measure("renderer settled"))
            (project / ("artifacts/memory-layers-"+args.tag+".json")).write_text(
                json.dumps(report,indent=2),encoding="utf-8")
            app.quit()
        QTimer.singleShot(1500,finish)
        app.exec()
        backend.shutdown()


if __name__ == "__main__":
    main()
