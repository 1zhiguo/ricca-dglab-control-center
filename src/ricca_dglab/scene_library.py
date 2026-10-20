"""Local scene documentation, deliberately separate from output authorisation."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import re

from .defeat_scene import scene_root


def valid_scene_id(value):
    return isinstance(value, str) and re.fullmatch(r"Scene(?:3D|ANV)_[A-Za-z0-9_-]+", value) is not None


class SceneLibrary:
    def __init__(self, path: Path):
        self.path = path
        self.entries = {}
        self.error = ""
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if raw.get("format") != "RiccaSceneLibrary/1" or not isinstance(raw.get("scenes"), dict):
                    raise ValueError("无法识别场景库格式")
                for key, entry in raw["scenes"].items():
                    if valid_scene_id(key) and isinstance(entry, dict):
                        self.entries[key] = {
                            "id": key, "note": str(entry.get("note") or "")[:160],
                            "first_seen": str(entry.get("first_seen") or ""),
                            "last_seen": str(entry.get("last_seen") or ""),
                            **{field: [item[:512] for item in entry.get(field, []) if isinstance(item, str)][:128]
                               if isinstance(entry.get(field), list) else []
                               for field in ("assets", "cuts", "types")},
                        }
            except (OSError, ValueError, AttributeError, TypeError) as error:
                self.error = str(error)

    def _commit(self, entries):
        if self.error:
            raise OSError("原场景库读取失败，为避免覆盖已取消保存：" + self.error)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({"format": "RiccaSceneLibrary/1", "scenes": entries},
                                        ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(self.path)
        self.entries = entries

    def record(self, state):
        asset = str((state.get("story") or {}).get("asset_name") or "")
        root = scene_root(asset)
        if (not root or state.get("scene") not in {"adv", "atd", "anv"}
                or state.get("status") != "ok" or state.get("build_supported") is not True):
            raise ValueError("尚未读取到有效的 Scene3D / SceneANV 剧情资源")
        entries = deepcopy(self.entries)
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        entry = entries.setdefault(root, {"id": root, "note": "", "first_seen": now,
                                          "assets": [], "cuts": [], "types": []})
        entry["last_seen"] = now
        for field, value in (("assets", asset), ("types", state["scene"]),
                             ("cuts", str((state.get("atd") or {}).get("cut_name") or "")[:120])):
            if not isinstance(entry.get(field), list):
                entry[field] = []
            if value and value not in entry[field] and len(entry[field]) < 128:
                entry[field].append(value)
        self._commit(entries)
        return root

    def save_note(self, root, note):
        if root not in self.entries:
            raise ValueError("场景尚未记录")
        entries = deepcopy(self.entries)
        entries[root]["note"] = str(note).strip()[:160]
        self._commit(entries)

    def rows(self, enabled):
        return [{"id": key, "note": str(value.get("note") or ""),
                 "lastSeen": str(value.get("last_seen") or ""),
                 "enabled": key in enabled,
                 "assetCount": len(value.get("assets") or [])}
                for key, value in sorted(self.entries.items())]
