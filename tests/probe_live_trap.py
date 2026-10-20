"""Record minimal read-only trap snapshots without any DG-LAB bridge."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ricca_hp_smoke_test import read_state


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=15)
    args = parser.parse_args()
    if not 0 < args.duration <= 60:
        parser.error("duration must be 0–60 seconds")
    target = Path(__file__).resolve().parents[1] / "artifacts" / ("trap-probe-" + time.strftime("%Y%m%d-%H%M%S") + ".jsonl")
    print(str(target), flush=True)
    started = time.monotonic()
    previous = None
    with target.open("x", encoding="utf-8") as stream:
        while time.monotonic() - started < args.duration:
            try:
                raw = read_state()
                state = {key: raw.get(key) for key in (
                    "scene", "process_id", "player_address", "current_hp", "is_paused",
                    "character_state_name", "action_trigger_name", "action_trigger_hash", "capture", "capture_read_error")}
                story = raw.get("story") or {}
                state["story_asset"] = story.get("asset_name")
                state["story_line"] = story.get("line_index")
                signature = json.dumps(state, ensure_ascii=True, sort_keys=True)
                if signature != previous:
                    previous = signature
                    state["elapsed"] = round(time.monotonic() - started, 3)
                    line = json.dumps(state, ensure_ascii=True)
                    stream.write(line + "\n")
                    stream.flush()
                    print(line, flush=True)
            except Exception as error:
                print(json.dumps({"error": str(error)}, ensure_ascii=True), flush=True)
            time.sleep(0.075)


if __name__ == "__main__":
    main()
