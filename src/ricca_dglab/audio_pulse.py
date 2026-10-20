"""System-audio capture and deterministic audio-to-pulse envelope mapping."""

from __future__ import annotations

import math
import queue
import threading
import time
from typing import Any


try:  # Optional at import time so the rest of the control center still starts.
    import numpy as np
    import soundcard as sc
except ImportError:  # pragma: no cover - depends on the local native runtime
    np = None
    sc = None


def audio_backend_available() -> bool:
    return sc is not None and np is not None


def enumerate_audio_devices() -> list[dict[str, Any]]:
    """Return capture and WASAPI loopback sources understood by SoundCard."""
    if not audio_backend_available():
        return []
    devices: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        sources = sc.all_microphones(include_loopback=True)
        default_speaker = sc.default_speaker()
        default_speaker_id = str(getattr(default_speaker, "id", "")) if default_speaker else ""
    except Exception:
        return []
    for source in sources:
        identifier = str(getattr(source, "id", "") or getattr(source, "name", "")).strip()
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        loopback = bool(getattr(source, "isloopback", False))
        is_default = bool(loopback and identifier == default_speaker_id)
        name = str(getattr(source, "name", identifier))
        devices.append({
            "id": identifier,
            "name": (
                "系统回环（默认）· " if is_default
                else "系统回环 · " if loopback
                else "录音输入 · "
            ) + name,
            "loopback": loopback,
            "default": is_default,
        })
    devices.sort(key=lambda item: (not item["default"], not item["loopback"], item["name"].casefold()))
    return devices


class AudioPulseMapper:
    """Map a logarithmic audio meter into a gated, capped pulse strength."""

    def __init__(self) -> None:
        self.envelope = 0.0

    @staticmethod
    def meter_percent(rms: float) -> float:
        value = max(1e-8, float(rms))
        dbfs = max(-60.0, min(0.0, 20.0 * math.log10(value)))
        return (dbfs + 60.0) / 60.0 * 100.0

    def map(self, rms: float, *, sensitivity: int, gate: int, hard_cap: int) -> dict[str, float | bool]:
        level = self.meter_percent(rms)
        threshold = max(0.0, min(95.0, float(gate)))
        sensitivity_scale = 0.35 + max(1, min(100, int(sensitivity))) / 100.0 * 1.65
        target = max(0.0, (level - threshold) / max(1.0, 100.0 - threshold))
        target = min(1.0, target * sensitivity_scale)
        coefficient = 0.62 if target > self.envelope else 0.16
        self.envelope += (target - self.envelope) * coefficient
        if self.envelope < 0.008:
            self.envelope = 0.0
        cap = max(0, min(100, int(hard_cap)))
        return {
            "level": level,
            "strength": self.envelope * cap,
            "active": self.envelope > 0.02,
            "dbfs": max(-60.0, min(0.0, 20.0 * math.log10(max(1e-8, float(rms))))),
        }


class AudioCaptureWorker(threading.Thread):
    """Capture one selected input/loopback source without touching the UI thread."""

    SAMPLE_RATE = 48_000
    BLOCK_SIZE = 2_400

    def __init__(self, outbox: queue.Queue, device_id: str, stop_event: threading.Event) -> None:
        super().__init__(name="RiccaAudioCapture", daemon=True)
        self.outbox = outbox
        self.device_id = str(device_id)
        self.stop_event = stop_event

    @staticmethod
    def _meter_points(samples: Any) -> list[int]:
        mono = np.mean(samples, axis=1) if getattr(samples, "ndim", 1) > 1 else samples
        chunks = np.array_split(mono, 16)
        return [
            round(AudioPulseMapper.meter_percent(float(np.sqrt(np.mean(np.square(chunk))))))
            if len(chunk) else 0
            for chunk in chunks
        ]

    def run(self) -> None:
        if not audio_backend_available():
            self.outbox.put(("audio_status", {"status": "unavailable", "detail": "缺少 SoundCard 音频模块"}))
            return
        try:
            source = sc.get_microphone(id=self.device_id, include_loopback=True)
            if source is None:
                raise RuntimeError("所选音频设备不存在")
            self.outbox.put(("audio_status", {"status": "listening", "detail": f"正在监听 {source.name}"}))
            with source.recorder(samplerate=self.SAMPLE_RATE, channels=2,
                                 blocksize=self.BLOCK_SIZE) as recorder:
                while not self.stop_event.is_set():
                    samples = recorder.record(numframes=self.BLOCK_SIZE)
                    if samples is None or not len(samples):
                        continue
                    rms = float(np.sqrt(np.mean(np.square(samples))))
                    peak = float(np.max(np.abs(samples)))
                    self.outbox.put(("audio_sample", {
                        "rms": rms,
                        "peak": peak,
                        "points": self._meter_points(samples),
                        "received_at": time.monotonic(),
                    }))
        except Exception as error:
            self.outbox.put(("audio_status", {"status": "error", "detail": str(error)}))

