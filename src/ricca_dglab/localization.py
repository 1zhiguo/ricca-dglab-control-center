"""Bounded, display-only translations. Never translates game state or IDs."""
from functools import lru_cache
import json
from pathlib import Path
import re

LANGUAGES = {"zh", "en", "ja"}
CATALOG = json.loads((Path(__file__).parent / "assets/locales/catalog.json").read_text(encoding="utf-8"))
_cjk = re.compile(r"[\u3400-\u9fff]")
_fragments = re.compile("(?=(" + "|".join(re.escape(s) for s in sorted(CATALOG, key=len, reverse=True)) + "))") if CATALOG else None


@lru_cache(maxsize=4096)
def translate(source: str, language: str) -> str:
    if language == "zh" or language not in LANGUAGES or not _cjk.search(source):
        return source
    index = 0 if language == "en" else 1
    if source in CATALOG:
        return CATALOG[source][index]
    # Backend messages compose translated labels with numbers, process IDs and
    # paths. Keep those values intact; unknown external errors are left verbatim.
    if not _fragments or len(source) > 16384:
        return source
    # Consider overlapping phrases: in "A 通道策略已保存", the complete status
    # suffix must win over the shorter "A 通道" label at the previous position.
    chosen = []
    for match in sorted(_fragments.finditer(source), key=lambda m:len(m.group(1)), reverse=True):
        start, phrase = match.start(), match.group(1)
        end = start + len(phrase)
        if not any(start < stop and end > begin for begin, stop, _ in chosen):
            chosen.append((start, end, CATALOG[phrase][index]))
    result, offset = [], 0
    for start, end, value in sorted(chosen):
        result.extend((source[offset:start], value))
        offset = end
    result.append(source[offset:])
    return "".join(result)
