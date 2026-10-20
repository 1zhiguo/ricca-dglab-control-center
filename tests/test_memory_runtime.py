"""Resource configuration must not alter audio math or scheduling constants."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


PROBE = r'''
import json, os, time
from ricca_dglab.audio_pulse import AudioCaptureWorker, AudioPulseMapper, np
samples = (np.sin(np.arange(4800, dtype=np.float64).reshape(2400,2) * .017) * .4)
mapper = AudioPulseMapper()
def process():
    rms = float(np.sqrt(np.mean(np.square(samples))))
    peak = float(np.max(np.abs(samples)))
    points = AudioCaptureWorker._meter_points(samples)
    return rms, peak, points
durations = []
for i in range(250):
    start = time.perf_counter()
    features = process()
    durations.append((time.perf_counter()-start)*1000)
mapped = [mapper.map(x, sensitivity=55, gate=12, hard_cap=30) for x in (0,.01,.1,.5,1,0,0)]
print(json.dumps(dict(threads=os.environ.get('OPENBLAS_NUM_THREADS'), features=features,
    mapped=mapped, p95_ms=sorted(durations)[int(len(durations)*.95)],
    mean_ms=sum(durations)/len(durations), block=AudioCaptureWorker.BLOCK_SIZE,
    rate=AudioCaptureWorker.SAMPLE_RATE)))
'''


class MemoryRuntimeTests(unittest.TestCase):
    def run_probe(self, threads):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        if threads is None:
            env.pop("OPENBLAS_NUM_THREADS", None)
        else:
            env["OPENBLAS_NUM_THREADS"] = str(threads)
        output = subprocess.run([sys.executable,"-c",PROBE], env=env, capture_output=True,
                                text=True, timeout=30, check=True)
        return json.loads(output.stdout)

    def test_default_single_thread_matches_original_math_and_capture_cadence(self):
        optimized = self.run_probe(None)
        original = self.run_probe(24)
        self.assertEqual(optimized["threads"], "1")
        self.assertEqual(original["threads"], "24")  # Explicit settings are respected.
        self.assertEqual(optimized["features"], original["features"])
        self.assertEqual(optimized["mapped"], original["mapped"])
        self.assertEqual((optimized["block"], optimized["rate"]), (2400,48000))
        # 50 ms is the unchanged audio block period. Allow generous headroom
        # for shared CI hosts; this is not a real WASAPI latency measurement.
        self.assertLess(optimized["p95_ms"], 50)
        print("Audio block math p95 ms: original=%.3f optimized=%.3f" %
              (original["p95_ms"],optimized["p95_ms"]))
