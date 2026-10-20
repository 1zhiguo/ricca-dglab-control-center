"""Bounded, read-only defeat-CG recording. No device bridge or audio capture."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ricca_hp_smoke_test import read_state, ProcessReader
from ricca_dglab.backend import BuildVerifier
from ricca_dglab.safety import SafetyGovernor


def read_defeat_fields(state):
    """1.4.1 dump.cs fields: candidates, NOT proof of an active CG."""
    result = {}
    game = int(state.get("game_controller_address", "0"), 16)
    ui = int(state.get("game_ui_controller_address", "0"), 16)
    with ProcessReader(state["process_id"]) as reader:
        adv = int(state.get("adv_controller_address", "0"), 16)
        if adv:
            result["dialogue_control"] = {
                "auto_enabled": reader.boolean(adv + 0x188),
                "skip_mode": reader.int32(adv + 0x1A0),
                "initialized": reader.boolean(adv + 0x200),
            }
        static = int(state["static_fields_address"], 16)
        active = reader.pointer_value(static + 0x88)
        if active:
            result["active_controller"] = {
                "address": hex(active),
                "pause_mask": reader.int32(active + 0xA4),
                "master_time_scale": reader.float32(active + 0xF0),
                "direction_time_scale": reader.float32(active + 0xF4),
                "fixed_frame": reader.int32(active + 0x58),
            }
            if state.get("controller_type") == 3:
                # ATD.ProgressController, ATD.ActorController and ATD.UIController.
                result["atd"] = {
                    "first_adv_started": reader.boolean(active + 0x110),
                    "animation_speed": reader.float32(active + 0x138),
                }
                atd_actor = reader.pointer_value(active + 0x130)
                atd_ui = reader.pointer_value(active + 0x118)
                if atd_actor:
                    result["atd"].update(
                        cut_index=reader.int32(atd_actor + 0xC8),
                        cut_name=reader.managed_string(atd_actor + 0xD0),
                        playing_adv_state=reader.int32(atd_actor + 0x198),
                        first_adv=reader.boolean(atd_actor + 0x131),
                    )
                if atd_ui:
                    result["atd"].update(
                        ui_visible=reader.boolean(atd_ui + 0x13C),
                        ui_start_atd=reader.boolean(atd_ui + 0x170),
                    )
                    main_group = reader.pointer_value(atd_ui + 0x60)
                    if main_group:
                        result["atd"]["auto_cut_enabled"] = reader.boolean(main_group + 0x48)
        if game:
            result.update(finish_act_state=reader.int32(game + 0x190),
                          adv_with_pause=reader.boolean(game + 0x18C),
                          game_adv_playing=reader.boolean(game + 0x195))
            events = reader.pointer_value(game + 0x180)
            if events:
                count = reader.int32(events + 0x18)
                if not 0 <= count <= 64:
                    raise ValueError("Invalid death event list count")
                items = reader.pointer_value(events + 0x10)
                result["configured_death_events_not_active_events"] = []
                if items:
                    for index in range(count):
                        event = reader.pointer_value(items + 0x20 + 8 * index)
                        if event:
                            result["configured_death_events_not_active_events"].append({
                                "name": reader.managed_string(event + 0x10),
                                "enabled": reader.boolean(event + 0x18),
                                "condition": reader.int32(event + 0x1C),
                                "next_action": reader.int32(event + 0x3C),
                                "next_adv_scene": reader.managed_string(event + 0x40),
                                "dummy_adv_scene": reader.managed_string(event + 0x60),
                            })
        if ui:
            result["capture_adv_scene_candidate"] = reader.managed_string(ui + 0x1D0)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=45)
    args = parser.parse_args()
    if not 0 < args.duration <= 60:
        parser.error("duration must be in (0, 60]")
    target = Path(__file__).resolve().parents[1] / "artifacts" / ("defeat-cg-" + time.strftime("%Y%m%d-%H%M%S") + ".jsonl")
    governor = SafetyGovernor()
    verifier = BuildVerifier()
    start = time.monotonic()
    previous = None
    count = 0
    print(str(target), flush=True)
    with target.open("x", encoding="utf-8") as stream:
        while time.monotonic() - start < args.duration:
            elapsed = round(time.monotonic() - start, 3)
            try:
                state = read_state()
                supported, digest, _ = verifier.verify(state["process_id"])
                state.update(build_supported=supported, gameassembly_sha256=digest)
                if supported:
                    try:
                        state["defeat_diagnostics"] = read_defeat_fields(state)
                    except Exception as error:
                        state["defeat_diagnostics_error"] = str(error)
                decision = governor.observe({**state, "connected": True})
                record = {"elapsed": elapsed, "timestamp": time.time(), "state": state,
                          "safety_reason": decision.reason}
                stage = state.get("stage") or {}
                story = state.get("story") or {}
                summary = {key: state.get(key) for key in (
                    "scene", "controller_type", "current_hp", "action_trigger_hash", "pause_mask", "is_paused", "player_controller")}
                diagnostics = json.loads(json.dumps(state.get("defeat_diagnostics")))
                if diagnostics and diagnostics.get("active_controller"):
                    diagnostics["active_controller"].pop("fixed_frame", None)
                summary.update(stage=stage.get("system_name"), game_over=stage.get("is_game_over"),
                               loading=stage.get("scene_change_playing"), adv_scene=state.get("adv_scene"),
                               asset=story.get("asset_name"), line=story.get("line_index"),
                               defeat_diagnostics=diagnostics,
                               safety_reason=decision.reason)
                signature = json.dumps(summary, sort_keys=True)
                if signature != previous:
                    print(json.dumps({"elapsed": elapsed, **summary}, ensure_ascii=True), flush=True)
                    previous = signature
                count += 1
            except Exception as error:
                record = {"elapsed": elapsed, "error": str(error)}
                print(json.dumps(record), flush=True)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            time.sleep(0.15)
    print(f"Recorded {count} snapshots. No output commands sent.", flush=True)


if __name__ == "__main__":
    main()
