"""Explicit offline allowlist update; never imports the device bridge or sends output."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re


def collected_ids(log_path, session):
    ids = set()
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        root = record.get("scene_root")
        if (record.get("event") == "scene.recorded" and record.get("session") == session
                and isinstance(root, str) and re.fullmatch(r"Scene(?:3D|ANV)_[A-Za-z0-9_-]+", root)):
            ids.add(root)
    return sorted(ids)


def register_file(path, ids, stamp):
    path = Path(path)
    original = path.read_bytes()
    raw = json.loads(original.decode("utf-8-sig"))
    if not isinstance(raw, dict):
        raise ValueError("Configuration must be an object")
    previous = raw.get("scene_catalog", [])
    if previous is None:
        previous = []
    if not isinstance(previous, list) or any(not isinstance(value, str) for value in previous):
        raise ValueError("Invalid existing scene catalogue; refusing to overwrite")
    updated = {**raw, "scene_catalog": sorted(set(previous) | set(ids))}
    payload = json.dumps(updated, ensure_ascii=False, indent=2).encode("utf-8")
    # Preserve all non-catalogue data exactly as JSON values, even legacy formats.
    assert {k: v for k, v in updated.items() if k != "scene_catalog"} == {
        k: v for k, v in raw.items() if k != "scene_catalog"}
    archive = path.with_name(path.name + ".before-scene-registration-" + stamp)
    with archive.open("xb") as stream:
        stream.write(original)
    temporary = path.with_name(path.name + ".scene-registration.tmp")
    temporary.write_bytes(payload)
    if path.read_bytes() != original:
        raise OSError("Configuration changed concurrently; registration cancelled")
    temporary.replace(path)
    assert json.loads(path.read_bytes()) == updated
    return {"file": str(path), "scene_count": len(updated["scene_catalog"]), "backup": str(archive)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--settings", type=Path, action="append", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    args = parser.parse_args()
    ids = collected_ids(args.log, args.session)
    if len(ids) != args.expected_count:
        raise SystemExit(f"Expected {args.expected_count} collected IDs, found {len(ids)}; nothing changed")
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    results = [register_file(path, ids, stamp) for path in args.settings]
    print(json.dumps({"registered": len(ids), "results": results, "device_commands_sent": 0}, ensure_ascii=False))
