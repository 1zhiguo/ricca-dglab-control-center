"""Display-only HUD preferences; independent of device/output settings."""
from copy import deepcopy
import math

HUD_DEFAULTS = {
    "scale": 100, "opacity": 80, "anchor": "auto", "x": 50, "y": 92,
    "show_pulse": True, "show_ovc": True, "show_a": True, "show_b": True,
    "show_numbers": True, "show_waveforms": True, "show_status": True,
}
HUD_ANCHORS = {"auto", "top_left", "top_center", "top_right",
               "bottom_left", "bottom_center", "bottom_right", "custom"}


def sanitize_hud_settings(raw):
    result = deepcopy(HUD_DEFAULTS)
    if not isinstance(raw, dict):
        return result
    for key, low, high in (("scale", 60, 180), ("opacity", 20, 100), ("x", 0, 100), ("y", 0, 100)):
        value = raw.get(key, result[key])
        if type(value) in (int, float) and math.isfinite(value):
            result[key] = round(max(low, min(high, value)))
    if isinstance(raw.get("anchor"), str) and raw["anchor"] in HUD_ANCHORS:
        result["anchor"] = raw["anchor"]
    for key in ("show_pulse", "show_ovc", "show_a", "show_b", "show_numbers", "show_waveforms", "show_status"):
        if type(raw.get(key)) is bool:
            result[key] = raw[key]
    if not (result["show_pulse"] or result["show_ovc"]):
        result["show_pulse"] = True
    if not (result["show_a"] or result["show_b"]):
        result["show_a"] = True
    return result
