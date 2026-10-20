"""Read-only loopback meters: never save audio or initialize a device bridge."""
import json
import queue
import threading
import time

from ricca_dglab.audio_pulse import AudioCaptureWorker, audio_backend_available, enumerate_audio_devices


def main():
    devices = [item for item in enumerate_audio_devices() if item["loopback"]]
    print(json.dumps({"available": audio_backend_available(), "devices": devices}, ensure_ascii=True), flush=True)
    stop = threading.Event()
    workers = []
    for device in devices:
        outbox = queue.Queue()
        worker = AudioCaptureWorker(outbox, device["id"], stop)
        workers.append((device, outbox, worker))
        worker.start()
    time.sleep(4)
    stop.set()
    for device, outbox, worker in workers:
        worker.join(timeout=1)
        samples, statuses = [], []
        while not outbox.empty():
            kind, payload = outbox.get_nowait()
            if kind == "audio_sample":
                samples.append(payload)
            else:
                statuses.append(payload)
        print(json.dumps({"device": device["name"], "statuses": statuses,
                          "samples": len(samples),
                          "max_rms": max((sample["rms"] for sample in samples), default=0),
                          "max_peak": max((sample["peak"] for sample in samples), default=0)},
                         ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
