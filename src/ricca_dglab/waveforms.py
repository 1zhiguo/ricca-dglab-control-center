"""DG-LAB waveform presets shared by preview, editor and Socket output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def _frame(frequency: int, amplitude: int) -> str:
    frequency = max(10, min(240, int(frequency)))
    amplitude = max(0, min(100, int(amplitude)))
    return (f"{frequency:02X}" * 4) + (f"{amplitude:02X}" * 4)


@dataclass(frozen=True)
class WaveformPreset:
    key: str
    name: str
    description: str
    source: str
    color: str
    frames: tuple[str, ...]

    @property
    def points(self) -> tuple[int, ...]:
        return tuple(
            round(sum(int(frame[index:index + 2], 16) for index in range(8, 16, 2)) / 4)
            for frame in self.frames
        )

    @property
    def frequency(self) -> int:
        values = [
            round(sum(int(frame[index:index + 2], 16) for index in range(0, 8, 2)) / 4)
            for frame in self.frames
        ]
        return round(sum(values) / len(values)) if values else 80


def _official_frames() -> dict[str, tuple[str, ...]]:
    """Curated DG-LAB Coyote V3 presets reused from the Manaka project."""
    return {
        "official_breath": tuple(_frame(10, a) for a in (0, 20, 40, 60, 80, 100, 100, 100, 0, 0, 0, 0)),
        "official_heartbeat": tuple(
            _frame(f, a) for f, a in (
                *((112, 100),) * 6,
                *((10, 0),) * 5,
                (10, 75), (10, 83), (10, 91), (10, 100),
                *((10, 0),) * 10,
                (10, 75), (10, 83), (10, 91), (10, 100),
                *((10, 0),) * 6,
            )
        ),
        "official_tide": tuple(
            _frame(f, a) for f, a in (
                (10, 0), (11, 16), (13, 33), (14, 50), (16, 66), (18, 83),
                (19, 100), (21, 92), (22, 84), (24, 76), (26, 68), (26, 0),
                (27, 16), (29, 33), (30, 50), (32, 66), (34, 83), (35, 100),
                (37, 92), (38, 84), (40, 76), (42, 68), (10, 0),
            )
        ),
        "official_pulsating": tuple(_frame(10, a) for a in (100, 0, 100, 66, 33, 0, 0, 0) * 3),
        "official_gradual": tuple(_frame(10, a) for a in (0, 28, 0, 52, 0, 73, 0, 87, 0, 100, 0, 0, 28, 0, 52, 0, 73, 0, 87, 0, 100, 0, 0)),
        "official_bouncy": tuple(
            _frame(10 + index // 2, amplitude)
            for index, amplitude in enumerate((0, 33, 66, 100) * 12 + (0, 0))
        ),
        "official_ripple": tuple(
            _frame(frequency, amplitude)
            for frequency in (10, 17, 25, 33, 40, 48, 56, 63, 71, 79, 86, 94, 100, 102)
            for amplitude in (0, 50, 100, 73)
        ) + (_frame(10, 0),),
    }


_OFFICIAL = _official_frames()

PRESETS: dict[str, WaveformPreset] = {
    "official_breath": WaveformPreset("official_breath", "官方·呼吸", "缓慢抬升并留出休止", "DG-LAB 官方", "#62d6e8", _OFFICIAL["official_breath"]),
    "official_heartbeat": WaveformPreset("official_heartbeat", "官方·心跳", "重拍与渐强回拍", "DG-LAB 官方", "#ff82b5", _OFFICIAL["official_heartbeat"]),
    "official_tide": WaveformPreset("official_tide", "官方·潮汐", "频率与包络连续推进", "DG-LAB 官方", "#9d8cff", _OFFICIAL["official_tide"]),
    "official_pulsating": WaveformPreset("official_pulsating", "官方·连击", "三组清晰强弱连击", "DG-LAB 官方", "#ffc857", _OFFICIAL["official_pulsating"]),
    "official_gradual": WaveformPreset("official_gradual", "官方·渐强", "分段逐级加强并回落", "DG-LAB 官方", "#ff9671", _OFFICIAL["official_gradual"]),
    "official_bouncy": WaveformPreset("official_bouncy", "官方·弹跳", "重复弹跳并提高频率", "DG-LAB 官方", "#55e0a3", _OFFICIAL["official_bouncy"]),
    "official_ripple": WaveformPreset("official_ripple", "官方·涟漪", "四拍起伏并持续变频", "DG-LAB 官方", "#78a7ff", _OFFICIAL["official_ripple"]),
    "tap": WaveformPreset("tap", "轻触", "短促、低存在感反馈", "Ricca 共感", "#40e0d0", (
        "0A0A0A0A14141414", "1010101020202020", "0808080810101010")),
    "impact": WaveformPreset("impact", "冲击", "普通受击的快速冲击", "Ricca 共感", "#ff5f78", (
        "1818181830303030", "2020202040404040", "1010101020202020")),
    "damage": WaveformPreset("damage", "伤害回落", "伤害后快速衰减", "Ricca 共感", "#ff6f8a", (
        "1414141428282828", "1C1C1C1C38383838", "161616162C2C2C2C", "0E0E0E0E1C1C1C1C")),
    "drilling": WaveformPreset("drilling", "连续受击", "适合连续伤害的交替节奏", "Ricca 共感", "#a67cff", (
        "1018202810182028", "1820283018202830", "2028303820283038", "1820283018202830")),
    "wall": WaveformPreset("wall", "撞墙反弹", "两次冲击之间快速回落", "Ricca 共感", "#ff8f70", (
        "2020202040404040", "1010101020202020", "2020202040404040", "0808080810101010")),
    "heavy_land": WaveformPreset("heavy_land", "重击倒地", "高起点后分段衰减", "Ricca 共感", "#ff4778", (
        "2828282850505050", "2020202040404040", "1818181830303030", "1010101020202020")),
    "guard": WaveformPreset("guard", "格挡", "三段金属感阶梯", "Ricca 共感", "#f4c95d", (
        "0C1824300C182430", "1824303C1824303C", "0C1824300C182430")),
    "armor_break": WaveformPreset("armor_break", "护甲破碎", "强弱交替的碎裂反馈", "Ricca 共感", "#f4c95d", (
        "2828282850505050", "0808080810101010", "2424242448484848", "060606060C0C0C0C", "1818181830303030")),
    "death_penalty": WaveformPreset("death_penalty", "死亡惩罚", "双通道单次重惩罚包络", "Ricca 共感", "#ff315d", tuple(
        _frame(72, amplitude) for amplitude in (20, 55, 100, 82, 45, 18, 0, 40, 85, 100, 64, 28, 0, 0)
    )),
}

WAVEFORMS: dict[str, tuple[str, ...]] = {
    "idle": (),
    **{key: preset.frames for key, preset in PRESETS.items()},
}


def custom_frames(points: Iterable[int], frequency: int) -> tuple[str, ...]:
    values = tuple(max(0, min(100, int(value))) for value in points)
    if len(values) != 16:
        raise ValueError("custom waveform requires 16 points")
    return tuple(_frame(frequency, value) for value in values)


def frames_for(name: str, custom_catalog: Iterable[dict] = ()) -> tuple[str, ...]:
    key = str(name)
    preset = PRESETS.get(key)
    if preset is not None:
        return preset.frames
    for entry in custom_catalog:
        if entry.get("key") == key:
            return custom_frames(entry.get("points", ()), int(entry.get("frequency", 80)))
    return ()


def waveform_catalog(custom_catalog: Iterable[dict] = ()) -> list[dict]:
    result = [{
        "key": preset.key,
        "name": preset.name,
        "description": preset.description,
        "source": preset.source,
        "color": preset.color,
        "points": list(preset.points),
        "frequency": preset.frequency,
        "group": "official" if preset.key.startswith("official_") else "builtin",
    } for preset in PRESETS.values()]
    result.extend(dict(entry) for entry in custom_catalog)
    return result
