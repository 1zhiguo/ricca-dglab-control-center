"""Validated capture telemetry, independent of animation hashes or enemy type."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CaptureState:
    known: bool = False
    active: bool = False
    address: int = 0
    can_struggle: bool = False
    count: float = 0.0
    maximum: float = 0.0

    @property
    def progress(self) -> float:
        return min(1.0, self.count / self.maximum) if self.active and self.maximum > 0 else 0.0


def capture_state(state: dict) -> CaptureState:
    if state.get("scene") != "gameplay" or state.get("capture_read_error"):
        return CaptureState()
    raw = state.get("capture")
    if not isinstance(raw, dict):
        return CaptureState()
    try:
        text = raw["info_address"]
        if not isinstance(text, str) or not text.startswith("0x"):
            return CaptureState()
        address = int(text, 16)
        count = float(raw["current_break_off_count"])
        maximum = float(raw["break_off_count_max"])
        acceptance = raw["break_off_acceptance"]
        if (not 0 <= address < 2**64 or not isinstance(acceptance, bool)
                or not all(math.isfinite(value) for value in (count, maximum))
                or not 0 <= count <= 1_000_000 or not 0 <= maximum <= 1_000_000
                or (acceptance and (maximum <= 0 or count > maximum + 0.05))):
            return CaptureState()
        return CaptureState(True, address != 0, address, address != 0 and acceptance, count, maximum)
    except (KeyError, TypeError, ValueError, OverflowError):
        return CaptureState()
