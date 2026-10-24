"""Session-only manual playback, independent of telemetry and saved mappings."""
from dataclasses import dataclass
import math


@dataclass
class ManualPlayback:
    enabled: bool = False
    running: bool = False
    strength_a: int = 0
    strength_b: int = 0
    wave_a: str = "idle"
    wave_b: str = "idle"
    deadline: float = 0.0
    sequence: int = 0
    reason: str = "manual-idle"

    def stop(self, reason="manual-stopped"):
        self.running = False
        self.deadline = 0.0
        self.reason = reason

    def start(self, strength_a, wave_a, strength_b, wave_b, seconds, *, now, cap, waves, max_strength=100):
        values = (strength_a, strength_b, seconds, now)
        if (not self.enabled or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)
                or not 1 <= seconds <= 300 or not 0 <= strength_a <= max_strength
                or not 0 <= strength_b <= max_strength or cap <= 0
                or (strength_a > 0 and wave_a not in waves)
                or (strength_b > 0 and wave_b not in waves)):
            return False
        a, b = min(cap, int(strength_a)), min(cap, int(strength_b))
        if not (a or b):
            return False
        self.strength_a, self.strength_b = a, b
        self.wave_a, self.wave_b = wave_a, wave_b
        self.deadline = now + seconds
        self.sequence += 1
        self.reason, self.running = "manual-running", True
        return True

    def check(self, *, now, blocker=""):
        if self.running:
            if blocker:
                self.stop(blocker)
            elif now >= self.deadline:
                self.stop("manual-timeout")

    def summary(self, now):
        return dict(enabled=self.enabled, running=self.running,
                    strength_a=self.strength_a if self.running else 0,
                    strength_b=self.strength_b if self.running else 0,
                    wave_a=self.wave_a, wave_b=self.wave_b,
                    remaining=max(0, math.ceil(self.deadline-now)) if self.running else 0,
                    reason=self.reason)
