"""Read Holy Knight Ricca's player HP from the live process.

This is a read-only smoke-test probe for the English 1.4.1 IL2CPP build.  It
uses only Windows' Toolhelp and ReadProcessMemory APIs; no DLL is injected and
no game memory is written.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import struct
import sys
import time


PROCESS_NAME = "HolyKnightRicca.exe"
MODULE_NAME = "GameAssembly.dll"
_preferred_executable_path = ""


def configure_preferred_executable(path: str = "") -> None:
    """Prefer one exact running executable; empty restores automatic detection."""
    global _preferred_executable_path
    value = str(path).strip()
    _preferred_executable_path = os.path.normcase(os.path.abspath(value)) if value else ""

# English build 1.4.1 (metadata v29).  The first value is an RVA and therefore
# remains valid with ASLR.  The remaining values are IL2CPP object offsets.
ACT_CLASS_POINTER_RVA = 0x27DDCD0
IL2CPP_CLASS_STATIC_FIELDS = 0xB8
ACT_CONTROLLER_TYPE_STATIC = 0x80
ACT_CONTROLLER_STATIC = 0x88
ACT_GAME_CONTROLLER_STATIC = 0x90
ACT_ADV_SCENE_CONTROLLER_STATIC = 0xB0
ACT_STAGE_CONTROLLER_STATIC = 0xB8
ACT_GAME_UI_CONTROLLER_STATIC = 0xD0
ACT_ADV_CONTROLLER_STATIC = 0xD8
ACT_GAME_CONTROLLER_PLAYER = 0x1C8
ACT_GAME_CONTROLLER_PLAYER_CONTROLLER = 0x1D8
ACT_CONTROLLER_FIXED_UPDATE_FRAME_COUNT = 0x58
ACT_CONTROLLER_PAUSE_STATE_MASK = 0xA4
ACT_CONTROLLER_MASTER_TIME_SCALE = 0xF0
ACT_CONTROLLER_DIRECTION_TIME_SCALE = 0xF4
CHARACTER_ACTOR_ACTION_INFO = 0x3B0
CHARACTER_ACTOR_STATE = 0x3B8
CHARACTER_ACTOR_ARMOR_BREAKER = 0x458
ACT_GAME_CONTROLLER_UPDATE_FRAME_COUNT = 0x188
ACT_GAME_CONTROLLER_BOSS_BATTLING = 0x1B0
ACT_GAME_CONTROLLER_BOSS_ACTOR_LIST = 0x1B8
ACT_GAME_CONTROLLER_BOSS_HP_MAX = 0x1C0
IL2CPP_LIST_ITEMS = 0x10
IL2CPP_LIST_SIZE = 0x18
IL2CPP_ARRAY_FIRST_ELEMENT = 0x20
CHARACTER_ACTOR_MAX_HP = 0x4F0
CHARACTER_ACTOR_CURRENT_HP = 0x4F4
CHARACTER_ACTOR_MAX_MAGIC = 0x4F8
CHARACTER_ACTOR_CURRENT_MAGIC = 0x4FC
CHARACTER_ACTOR_DEFENCE = 0x500
CHARACTER_ACTOR_INVINCIBLE_TYPE = 0x4E4
CHARACTER_ACTOR_INVINCIBLE_COUNT = 0x4E8
CHARACTER_ACTOR_CONTROL_AI_ENABLED = 0x4EC
CHARACTER_ACTOR_SPEED_SCALE = 0x520
ARMOR_BREAKER_DAMAGE_CONVERT_SCALE = 0x18
ARMOR_BREAKER_ALLOW_LOAD_LEVEL = 0x1C
ARMOR_BREAKER_CURRENT_LEVEL = 0x2C
ARMOR_BREAKER_CURRENT_HP = 0x30
ARMOR_BREAKER_PARENT_ACTOR = 0x38
ARMOR_BREAKER_PROFILE = 0x40
ARMOR_BREAKER_MAX_HP = 0x48
ARMOR_BREAKER_LAST_BREAK_TIME = 0x4C
ARMOR_BREAKER_INITIALIZED = 0x50
COSTUME_PROFILE_ARMOR_LEVELS = 0x20
COSTUME_PROFILE_USE_R15_FALLBACK = 0x28
COSTUME_PROFILE_R15_ARMOR_LEVELS = 0x30
ARMOR_LEVEL_HIT_POINT = 0x10
ARMOR_LEVEL_DAMAGE_RATIO = 0x14
ARMOR_LEVEL_ARMOR_TYPE = 0x20
ARMOR_LEVEL_BREAK_SE = 0x24
ACTION_INFO_ENABLED = 0x10
ACTION_INFO_TIME = 0x28
ACTION_INFO_TRIGGER_ENABLED = 0x2C
ACTION_INFO_TRIGGER_HASH = 0x30
ACTION_INFO_CHECK_TRIGGER_HASH = 0x34

PLAYER_CONTROLLER_ACT_PLAYING = 0x18
PLAYER_CONTROLLER_ADV_PLAYING = 0x19
PLAYER_CONTROLLER_TARGET_ACTOR = 0x20

STAGE_MODE = 0x2C
STAGE_SYSTEM_NAME = 0x30
STAGE_BOSS_SCENE_INDEX = 0x38
STAGE_HAS_SILVER_CRYSTAL = 0x3C
STAGE_GAME_TIME_SCALE = 0x94
STAGE_MASTER_TIME_SCALE = 0xA0
STAGE_ALL_RESOURCE_LOADED = 0xA4
STAGE_PLAYER_COSTUME_LOADED = 0xA5
STAGE_CONTINUE_CRYSTAL_COUNT = 0xA8
STAGE_IS_GAME_OVER = 0x118
STAGE_ACT_SCENE_LOADED = 0x119
STAGE_CURRENT_SCENE_INDEX = 0x150
STAGE_SCENE_CHANGE_PLAYING = 0x155

GAME_UI_IS_RESETED = 0x1E8
GAME_UI_IS_INITIALIZED = 0x1E9
GAME_UI_UPDATE_COUNT = 0x1EC
GAME_UI_USER_PAUSE = 0x1F4

ADV_CURRENT_SCENARIO_LINE_INDEX = 0xF4
ADV_MESSAGE_STATUS = 0x198
ADV_SKIP_MODE = 0x1A0
ADV_SHOW_UI = 0x1A4
ADV_SYSTEM_STATUS = 0x1A8
ADV_SCENE_TYPE = 0x208
ADV_MESSAGE_SPEAKER = 0x18
ADV_MESSAGE_TEXT = 0x20
ADV_MESSAGE_STRIPPED_TEXT = 0x28
ADV_MESSAGE_ORIGINAL_TEXT = 0x58
ADV_SYSTEM_ASSET_NAME = 0x10
ADV_SYSTEM_DISPLAY_STATE = 0x1C
ADV_SYSTEM_WAIT_NEXT = 0x20
ADV_SYSTEM_NEXT_ACTION = 0x24
ADV_SYSTEM_ACT_CUT_MODE = 0x28
ADV_SYSTEM_ACT_SCREEN_PAUSED = 0x2C
ADV_SYSTEM_STATE = 0x3C
ADV_SCENE_SUBSCENE = 0x110
ADV_SCENE_CONTROL_MODE = 0x114
ADV_SCENE_ADV_TYPE = 0x128
ADV_SCENE_NAME = 0x138
ADV_SCENE_NEXT_MODE = 0x140
ADV_SCENE_GAME_TIME_SCALE = 0x144

CHARACTER_STATE_NAMES = {
    0: "Wait",
    1: "Damage",
    2: "DamageGuardBreak",
    3: "StandAttack",
    4: "StandMove",
    5: "StandAction",
    6: "StandBlockAction",
    7: "AirMove",
    8: "AirAttack",
    9: "AirAction",
    10: "SpecialAttack",
}

# Confirmed Animator.StringToHash/CRC32 values captured from live gameplay.
ACTION_TRIGGER_NAMES = {
    -1901219375: "stand_landing",
    -1774877678: "stand_quickTurnDash",
    -1027517838: "stand_runStop",
    -567798552: "stand_guard_start",
    -503375354: "stand_wait",
    -314031182: "stand_damage",
    298341484: "damage",
    487807904: "air_jump",
    605988336: "air_rise",
    872607265: "air_wall_blowOff",
    1000513525: "stand_jump",
    1106281146: "air_fall",
    1219929417: "stand_damage_small",
    1349952704: "run",
    1435546636: "damage_drilling",
    1654698034: "stand_landing_blowOff_back",
    1693688566: "stand_guard_hit",
    1826629811: "stand_landing_blowOff",
    1984685271: "air_zenith_fall",
}

TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * MAX_PATH),
    ]


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * MAX_PATH),
    ]


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.Module32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
kernel32.Module32FirstW.restype = wintypes.BOOL
kernel32.Module32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MODULEENTRY32W)]
kernel32.Module32NextW.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
kernel32.ReadProcessMemory.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL


class ProbeError(RuntimeError):
    pass


def _win_error(action: str) -> ProbeError:
    error = ctypes.get_last_error()
    return ProbeError(f"{action} failed (Windows error {error}: {ctypes.FormatError(error).strip()})")


def _snapshot(flags: int, process_id: int = 0) -> int:
    handle = kernel32.CreateToolhelp32Snapshot(flags, process_id)
    if handle == INVALID_HANDLE_VALUE:
        raise _win_error("CreateToolhelp32Snapshot")
    return handle


def _process_image_path(process_id: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not handle:
        return ""
    try:
        capacity = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(capacity.value)
        if not kernel32.QueryFullProcessImageNameW(
                handle, 0, buffer, ctypes.byref(capacity)):
            return ""
        return os.path.normcase(os.path.abspath(buffer.value))
    finally:
        kernel32.CloseHandle(handle)


def find_process_id(name: str, expected_path: str = "") -> int:
    expected = os.path.normcase(os.path.abspath(expected_path)) if expected_path else ""
    snapshot = _snapshot(TH32CS_SNAPPROCESS)
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.casefold() == name.casefold():
                process_id = int(entry.th32ProcessID)
                if not expected or _process_image_path(process_id) == expected:
                    return process_id
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    if expected:
        raise ProbeError(f"Selected game executable is not running: {expected_path}")
    raise ProbeError(f"{name} is not running")


def find_module_base(process_id: int, name: str) -> int:
    snapshot = _snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, process_id)
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel32.Module32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if entry.szModule.casefold() == name.casefold():
                return int(entry.modBaseAddr)
            ok = kernel32.Module32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    raise ProbeError(f"{name} is not loaded in process {process_id}")


class ProcessReader:
    def __init__(self, process_id: int):
        self.process_id = process_id
        self.handle = kernel32.OpenProcess(
            PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, process_id
        )
        if not self.handle:
            raise _win_error(f"OpenProcess({process_id})")

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "ProcessReader":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def read(self, address: int, size: int) -> bytes:
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(
            self.handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(bytes_read),
        ):
            raise _win_error(f"ReadProcessMemory(0x{address:X})")
        if bytes_read.value != size:
            raise ProbeError(
                f"Short memory read at 0x{address:X}: expected {size}, got {bytes_read.value}"
            )
        return buffer.raw

    def pointer(self, address: int, label: str) -> int:
        value = self.pointer_value(address)
        if value == 0:
            raise ProbeError(
                f"{label} is null; load a save and enter an active gameplay stage"
            )
        return value

    def pointer_value(self, address: int) -> int:
        return struct.unpack("<Q", self.read(address, 8))[0]

    def uint32(self, address: int) -> int:
        return struct.unpack("<I", self.read(address, 4))[0]

    def int32(self, address: int) -> int:
        return struct.unpack("<i", self.read(address, 4))[0]

    def uint8(self, address: int) -> int:
        return self.read(address, 1)[0]

    def float32(self, address: int) -> float:
        return struct.unpack("<f", self.read(address, 4))[0]

    def boolean(self, address: int) -> bool:
        return bool(self.uint8(address))

    def managed_string(self, pointer_address: int, max_chars: int = 4096) -> str:
        """Read a nullable IL2CPP System.String pointer."""
        string_object = self.pointer_value(pointer_address)
        if not string_object:
            return ""
        length = self.int32(string_object + 0x10)
        if length < 0 or length > max_chars:
            raise ProbeError(
                f"Invalid managed string length {length} at 0x{string_object:X}"
            )
        if length == 0:
            return ""
        return self.read(string_object + 0x14, length * 2).decode(
            "utf-16-le", errors="replace"
        )


def read_hp() -> dict[str, int | float | str]:
    selected = _preferred_executable_path
    process_id = find_process_id(Path(selected).name if selected else PROCESS_NAME, selected)
    module_base = find_module_base(process_id, MODULE_NAME)

    with ProcessReader(process_id) as reader:
        act_class = reader.pointer(module_base + ACT_CLASS_POINTER_RVA, "Act class")
        static_fields = reader.pointer(
            act_class + IL2CPP_CLASS_STATIC_FIELDS, "Act static fields"
        )
        controller = reader.pointer(
            static_fields + ACT_GAME_CONTROLLER_STATIC, "ACTGameController"
        )
        player = reader.pointer(
            controller + ACT_GAME_CONTROLLER_PLAYER, "player CharacterActor"
        )
        maximum = reader.float32(player + CHARACTER_ACTOR_MAX_HP)
        current = reader.float32(player + CHARACTER_ACTOR_CURRENT_HP)

    if not (math.isfinite(current) and math.isfinite(maximum)):
        raise ProbeError(f"HP values are not finite: current={current!r}, max={maximum!r}")
    if maximum <= 0 or maximum > 10_000_000 or current < 0 or current > maximum * 1.1:
        raise ProbeError(
            f"HP validation failed: current={current:g}, max={maximum:g}; offsets may not match this build"
        )

    return {
        "status": "ok",
        "build": "Holy Knight Ricca English 1.4.1",
        "process_id": process_id,
        "current_hp": current,
        "max_hp": maximum,
        "hp_ratio": current / maximum,
        "player_address": f"0x{player:X}",
    }


def _read_armor_level_list(
    reader: ProcessReader, list_pointer: int, max_levels: int = 32
) -> list[dict[str, object]]:
    if not list_pointer:
        return []
    count = reader.uint32(list_pointer + IL2CPP_LIST_SIZE)
    if count > max_levels:
        raise ProbeError(f"Invalid armor level count: {count}")
    items = reader.pointer_value(list_pointer + IL2CPP_LIST_ITEMS)
    if not items:
        return []
    levels: list[dict[str, object]] = []
    for index in range(count):
        level = reader.pointer_value(items + IL2CPP_ARRAY_FIRST_ELEMENT + index * 8)
        if not level:
            continue
        armor_type = reader.int32(level + ARMOR_LEVEL_ARMOR_TYPE)
        levels.append(
            {
                "index": index,
                "hit_point": reader.float32(level + ARMOR_LEVEL_HIT_POINT),
                "damage_ratio": reader.float32(level + ARMOR_LEVEL_DAMAGE_RATIO),
                "armor_type": armor_type,
                "armor_type_name": {0: "None", 1: "Armor", 2: "Cloth"}.get(
                    armor_type, "Unknown"
                ),
                "break_se": reader.int32(level + ARMOR_LEVEL_BREAK_SE),
            }
        )
    return levels


def _read_actor_state(reader: ProcessReader, actor: int) -> dict[str, object]:
    """Read the shared player/boss fields from a CharacterActor."""
    maximum = reader.float32(actor + CHARACTER_ACTOR_MAX_HP)
    current = reader.float32(actor + CHARACTER_ACTOR_CURRENT_HP)
    state = reader.uint32(actor + CHARACTER_ACTOR_STATE)
    result: dict[str, object] = {
        "address": f"0x{actor:X}",
        "current_hp": current,
        "max_hp": maximum,
        "hp_ratio": current / maximum if maximum > 0 else 0.0,
        "character_state": state,
        "character_state_name": CHARACTER_STATE_NAMES.get(state, "Unknown"),
        "max_magic": reader.float32(actor + CHARACTER_ACTOR_MAX_MAGIC),
        "current_magic": reader.float32(actor + CHARACTER_ACTOR_CURRENT_MAGIC),
        "defence": reader.float32(actor + CHARACTER_ACTOR_DEFENCE),
        "invincible_type": reader.uint32(actor + CHARACTER_ACTOR_INVINCIBLE_TYPE),
        "invincible_count": reader.uint32(actor + CHARACTER_ACTOR_INVINCIBLE_COUNT),
        "control_ai_enabled": reader.boolean(
            actor + CHARACTER_ACTOR_CONTROL_AI_ENABLED
        ),
        "speed_scale": reader.float32(actor + CHARACTER_ACTOR_SPEED_SCALE),
    }
    action_info = reader.pointer_value(actor + CHARACTER_ACTOR_ACTION_INFO)
    result["action_info_address"] = f"0x{action_info:X}"
    if action_info:
        trigger_hash = reader.int32(action_info + ACTION_INFO_TRIGGER_HASH)
        result.update(
            {
                "action_enabled": reader.boolean(action_info + ACTION_INFO_ENABLED),
                "action_time": reader.float32(action_info + ACTION_INFO_TIME),
                "action_trigger_enabled": reader.boolean(
                    action_info + ACTION_INFO_TRIGGER_ENABLED
                ),
                "action_trigger_hash": trigger_hash,
                "action_trigger_name": ACTION_TRIGGER_NAMES.get(
                    trigger_hash, "Unknown"
                ),
                "action_check_trigger_hash": reader.int32(
                    action_info + ACTION_INFO_CHECK_TRIGGER_HASH
                ),
            }
        )
    armor_breaker = reader.pointer_value(actor + CHARACTER_ACTOR_ARMOR_BREAKER)
    # CharacterActor.CapturringData is an inline struct (verified 1.4.1 layout).
    # Raw diagnostic fields only: not yet a validated trap/pulse signature.
    try:
        capture = actor + 0x498
        info = reader.pointer_value(capture)
        result["capture"] = {
            "info_address": f"0x{info:X}",
            "current_break_off_count": reader.float32(capture + 0x38),
            "break_off_count_max": reader.float32(capture + 0x3C),
            "break_off_acceptance": reader.boolean(capture + 0x40),
        }
        if info:
            result["capture"].update({
                "type_flags": reader.uint32(info + 0x10),
                "damage_kind": reader.int32(info + 0x14),
            })
    except ProbeError as error:
        result["capture_read_error"] = str(error)
    result["armor_breaker_address"] = f"0x{armor_breaker:X}"
    if armor_breaker:
        armor_hp = reader.float32(armor_breaker + ARMOR_BREAKER_CURRENT_HP)
        armor_max_hp = reader.float32(armor_breaker + ARMOR_BREAKER_MAX_HP)
        profile = reader.pointer_value(armor_breaker + ARMOR_BREAKER_PROFILE)
        levels: list[dict[str, object]] = []
        fallback_levels: list[dict[str, object]] = []
        use_r15_fallback = False
        if profile:
            levels = _read_armor_level_list(
                reader,
                reader.pointer_value(profile + COSTUME_PROFILE_ARMOR_LEVELS),
            )
            use_r15_fallback = reader.boolean(
                profile + COSTUME_PROFILE_USE_R15_FALLBACK
            )
            fallback_levels = _read_armor_level_list(
                reader,
                reader.pointer_value(profile + COSTUME_PROFILE_R15_ARMOR_LEVELS),
            )
        result["armor"] = {
            "current_level": reader.int32(armor_breaker + ARMOR_BREAKER_CURRENT_LEVEL),
            "current_hp": armor_hp,
            "max_hp": armor_max_hp,
            "hp_ratio": armor_hp / armor_max_hp if armor_max_hp > 0 else 0.0,
            "last_break_time": reader.float32(
                armor_breaker + ARMOR_BREAKER_LAST_BREAK_TIME
            ),
            "damage_convert_scale": reader.float32(
                armor_breaker + ARMOR_BREAKER_DAMAGE_CONVERT_SCALE
            ),
            "allow_load_level": reader.boolean(
                armor_breaker + ARMOR_BREAKER_ALLOW_LOAD_LEVEL
            ),
            "initialized": reader.boolean(
                armor_breaker + ARMOR_BREAKER_INITIALIZED
            ),
            "parent_actor_address": (
                f"0x{reader.pointer_value(armor_breaker + ARMOR_BREAKER_PARENT_ACTOR):X}"
            ),
            "profile_address": (
                f"0x{profile:X}"
            ),
            "level_count": len(levels),
            "levels": levels,
            "use_r15_fallback": use_r15_fallback,
            "r15_fallback_level_count": len(fallback_levels),
            "r15_fallback_levels": fallback_levels,
        }
    return result


def _prefixed(source: dict[str, object], prefix: str) -> dict[str, object]:
    return {f"{prefix}{key}": value for key, value in source.items()}


def read_state() -> dict[str, object]:
    """Read gameplay, boss, stage and ADV fields for the live dashboard."""
    selected = _preferred_executable_path
    process_id = find_process_id(Path(selected).name if selected else PROCESS_NAME, selected)
    module_base = find_module_base(process_id, MODULE_NAME)

    with ProcessReader(process_id) as reader:
        act_class = reader.pointer(module_base + ACT_CLASS_POINTER_RVA, "Act class")
        static_fields = reader.pointer(
            act_class + IL2CPP_CLASS_STATIC_FIELDS, "Act static fields"
        )
        controller_type = reader.uint32(static_fields + ACT_CONTROLLER_TYPE_STATIC)
        game_controller = reader.pointer_value(
            static_fields + ACT_GAME_CONTROLLER_STATIC
        )
        adv_scene_controller = reader.pointer_value(
            static_fields + ACT_ADV_SCENE_CONTROLLER_STATIC
        )
        stage_controller = reader.pointer_value(
            static_fields + ACT_STAGE_CONTROLLER_STATIC
        )
        game_ui_controller = reader.pointer_value(
            static_fields + ACT_GAME_UI_CONTROLLER_STATIC
        )
        adv_controller = reader.pointer_value(
            static_fields + ACT_ADV_CONTROLLER_STATIC
        )

        result: dict[str, object] = {
            "status": "ok",
            "build": "Holy Knight Ricca English 1.4.1",
            "process_id": process_id,
            "module_base": f"0x{module_base:X}",
            "act_class_address": f"0x{act_class:X}",
            "static_fields_address": f"0x{static_fields:X}",
            "controller_type": controller_type,
            "scene": {
                0: "none",
                1: "gameplay",
                2: "adv",
                3: "atd",
                4: "anv",
                5: "other",
            }.get(controller_type, "unknown"),
            "game_controller_address": f"0x{game_controller:X}",
            "adv_scene_controller_address": f"0x{adv_scene_controller:X}",
            "stage_controller_address": f"0x{stage_controller:X}",
            "game_ui_controller_address": f"0x{game_ui_controller:X}",
            "adv_controller_address": f"0x{adv_controller:X}",
        }

        telemetry_errors: list[str] = []

        # ACTControllerBase exists in ATD too; the gameplay pointer is null there.
        # Offsets below are confirmed against the English 1.4.1 metadata dump.
        try:
            active_controller = reader.pointer_value(static_fields + ACT_CONTROLLER_STATIC)
            result["act_controller_address"] = f"0x{active_controller:X}"
            if active_controller:
                active_pause = reader.uint32(active_controller + ACT_CONTROLLER_PAUSE_STATE_MASK)
                result["active_controller"] = {
                    "pause_mask": active_pause,
                    "master_time_scale": reader.float32(active_controller + ACT_CONTROLLER_MASTER_TIME_SCALE),
                    "direction_time_scale": reader.float32(active_controller + ACT_CONTROLLER_DIRECTION_TIME_SCALE),
                }
                if controller_type == 3:
                    result["pause_mask"] = active_pause
                    result["is_paused"] = bool(active_pause)
                    actor = reader.pointer_value(active_controller + 0x130)
                    atd_ui = reader.pointer_value(active_controller + 0x118)
                    atd = {"animation_speed": reader.float32(active_controller + 0x138)}
                    if actor:
                        atd.update(cut_index=reader.int32(actor + 0xC8),
                                   cut_name=reader.managed_string(actor + 0xD0),
                                   playing_adv_state=reader.int32(actor + 0x198))
                    if atd_ui:
                        atd["ui_start_atd"] = reader.boolean(atd_ui + 0x170)
                        main_group = reader.pointer_value(atd_ui + 0x60)
                        if main_group:
                            atd["auto_cut_enabled"] = reader.boolean(main_group + 0x48)
                    result["atd"] = atd
            if game_ui_controller:
                result["defeat_scene_hint"] = reader.managed_string(game_ui_controller + 0x1D0)
        except ProbeError as error:
            telemetry_errors.append(f"atd/defeat: {error}")

        if stage_controller:
            try:
                result["stage"] = {
                    "mode": reader.uint32(stage_controller + STAGE_MODE),
                    "system_name": reader.managed_string(
                        stage_controller + STAGE_SYSTEM_NAME
                    ),
                    "boss_scene_index": reader.int32(
                        stage_controller + STAGE_BOSS_SCENE_INDEX
                    ),
                    "has_silver_crystal": reader.boolean(
                        stage_controller + STAGE_HAS_SILVER_CRYSTAL
                    ),
                    "game_time_scale": reader.float32(
                        stage_controller + STAGE_GAME_TIME_SCALE
                    ),
                    "master_time_scale": reader.float32(
                        stage_controller + STAGE_MASTER_TIME_SCALE
                    ),
                    "all_resource_loaded": reader.boolean(
                        stage_controller + STAGE_ALL_RESOURCE_LOADED
                    ),
                    "player_costume_loaded": reader.boolean(
                        stage_controller + STAGE_PLAYER_COSTUME_LOADED
                    ),
                    "continue_crystal_count": reader.uint32(
                        stage_controller + STAGE_CONTINUE_CRYSTAL_COUNT
                    ),
                    "is_game_over": reader.boolean(
                        stage_controller + STAGE_IS_GAME_OVER
                    ),
                    "act_scene_loaded": reader.boolean(
                        stage_controller + STAGE_ACT_SCENE_LOADED
                    ),
                    "current_scene_index": reader.int32(
                        stage_controller + STAGE_CURRENT_SCENE_INDEX
                    ),
                    "scene_change_playing": reader.boolean(
                        stage_controller + STAGE_SCENE_CHANGE_PLAYING
                    ),
                }
            except ProbeError as error:
                telemetry_errors.append(f"stage: {error}")

        if game_ui_controller:
            try:
                result["game_ui"] = {
                    "is_reseted": reader.boolean(
                        game_ui_controller + GAME_UI_IS_RESETED
                    ),
                    "is_initialized": reader.boolean(
                        game_ui_controller + GAME_UI_IS_INITIALIZED
                    ),
                    "update_count": reader.uint32(
                        game_ui_controller + GAME_UI_UPDATE_COUNT
                    ),
                    "is_user_pause": reader.boolean(
                        game_ui_controller + GAME_UI_USER_PAUSE
                    ),
                }
            except ProbeError as error:
                telemetry_errors.append(f"game_ui: {error}")

        if game_controller:
            pause_mask = reader.uint32(
                game_controller + ACT_CONTROLLER_PAUSE_STATE_MASK
            )
            player = reader.pointer_value(
                game_controller + ACT_GAME_CONTROLLER_PLAYER
            )
            player_controller = reader.pointer_value(
                game_controller + ACT_GAME_CONTROLLER_PLAYER_CONTROLLER
            )
            result.update(
                {
                    "pause_mask": pause_mask,
                    "is_paused": pause_mask != 0,
                    "fixed_update_frame_count": reader.uint32(
                        game_controller + ACT_CONTROLLER_FIXED_UPDATE_FRAME_COUNT
                    ),
                    "update_frame_count": reader.uint32(
                        game_controller + ACT_GAME_CONTROLLER_UPDATE_FRAME_COUNT
                    ),
                    "master_time_scale": reader.float32(
                        game_controller + ACT_CONTROLLER_MASTER_TIME_SCALE
                    ),
                    "direction_time_scale": reader.float32(
                        game_controller + ACT_CONTROLLER_DIRECTION_TIME_SCALE
                    ),
                    "player_address": f"0x{player:X}",
                    "player_controller_address": f"0x{player_controller:X}",
                }
            )
            if player_controller:
                try:
                    result["player_controller"] = {
                        "is_act_playing": reader.boolean(
                            player_controller + PLAYER_CONTROLLER_ACT_PLAYING
                        ),
                        "is_adv_playing": reader.boolean(
                            player_controller + PLAYER_CONTROLLER_ADV_PLAYING
                        ),
                        "target_actor_address": (
                            f"0x{reader.pointer_value(player_controller + PLAYER_CONTROLLER_TARGET_ACTOR):X}"
                        ),
                    }
                except ProbeError as error:
                    telemetry_errors.append(f"player_controller: {error}")
            if player:
                try:
                    actor = _read_actor_state(reader, player)
                    # Keep the original flat player keys for CLI/backward compatibility.
                    result.update(actor)
                    result["player"] = actor
                except ProbeError as error:
                    telemetry_errors.append(f"player: {error}")

            boss_list = reader.pointer_value(
                game_controller + ACT_GAME_CONTROLLER_BOSS_ACTOR_LIST
            )
            result.update(
                {
                    "boss_battling": bool(
                        reader.uint8(game_controller + ACT_GAME_CONTROLLER_BOSS_BATTLING)
                    ),
                    "boss_hit_point_max_cached": reader.float32(
                        game_controller + ACT_GAME_CONTROLLER_BOSS_HP_MAX
                    ),
                    "boss_count": 0,
                }
            )
            if boss_list:
                boss_count = reader.uint32(boss_list + IL2CPP_LIST_SIZE)
                result["boss_count"] = boss_count
                boss_items = reader.pointer_value(boss_list + IL2CPP_LIST_ITEMS)
                if boss_count > 0 and boss_items:
                    boss = reader.pointer_value(
                        boss_items + IL2CPP_ARRAY_FIRST_ELEMENT
                    )
                    result["boss_address"] = f"0x{boss:X}"
                    if boss:
                        try:
                            boss_actor = _read_actor_state(reader, boss)
                            result["boss"] = boss_actor
                            result.update(_prefixed(boss_actor, "boss_"))
                        except ProbeError as error:
                            telemetry_errors.append(f"boss: {error}")

        if adv_scene_controller:
            try:
                result["adv_scene"] = {
                    "subscene": reader.int32(
                        adv_scene_controller + ADV_SCENE_SUBSCENE
                    ),
                    "control_mode": reader.int32(
                        adv_scene_controller + ADV_SCENE_CONTROL_MODE
                    ),
                    "adv_type": reader.int32(
                        adv_scene_controller + ADV_SCENE_ADV_TYPE
                    ),
                    "scene_name": reader.managed_string(
                        adv_scene_controller + ADV_SCENE_NAME
                    ),
                    "next_scene_mode": reader.int32(
                        adv_scene_controller + ADV_SCENE_NEXT_MODE
                    ),
                    "game_time_scale": reader.float32(
                        adv_scene_controller + ADV_SCENE_GAME_TIME_SCALE
                    ),
                }
            except ProbeError as error:
                telemetry_errors.append(f"adv_scene: {error}")

        if adv_controller:
            try:
                message_status = reader.pointer_value(
                    adv_controller + ADV_MESSAGE_STATUS
                )
                system_status = reader.pointer_value(
                    adv_controller + ADV_SYSTEM_STATUS
                )
                story: dict[str, object] = {
                    "line_index": reader.int32(
                        adv_controller + ADV_CURRENT_SCENARIO_LINE_INDEX
                    ),
                    "skip_mode": reader.int32(adv_controller + ADV_SKIP_MODE),
                    "show_ui": reader.boolean(adv_controller + ADV_SHOW_UI),
                    "scene_type": reader.int32(adv_controller + ADV_SCENE_TYPE),
                    "message_status_address": f"0x{message_status:X}",
                    "system_status_address": f"0x{system_status:X}",
                }
                if message_status:
                    story.update(
                        {
                            "speaker": reader.managed_string(
                                message_status + ADV_MESSAGE_SPEAKER
                            ),
                            "message": reader.managed_string(
                                message_status + ADV_MESSAGE_TEXT
                            ),
                            "stripped_message": reader.managed_string(
                                message_status + ADV_MESSAGE_STRIPPED_TEXT
                            ),
                            "original_message": reader.managed_string(
                                message_status + ADV_MESSAGE_ORIGINAL_TEXT
                            ),
                        }
                    )
                if system_status:
                    story.update(
                        {
                            "asset_name": reader.managed_string(
                                system_status + ADV_SYSTEM_ASSET_NAME
                            ),
                            "display_state": reader.int32(
                                system_status + ADV_SYSTEM_DISPLAY_STATE
                            ),
                            "wait_next": reader.boolean(
                                system_status + ADV_SYSTEM_WAIT_NEXT
                            ),
                            "next_action": reader.int32(
                                system_status + ADV_SYSTEM_NEXT_ACTION
                            ),
                            "act_cut_mode": reader.int32(
                                system_status + ADV_SYSTEM_ACT_CUT_MODE
                            ),
                            "act_screen_paused": reader.boolean(
                                system_status + ADV_SYSTEM_ACT_SCREEN_PAUSED
                            ),
                            "adv_state": reader.int32(
                                system_status + ADV_SYSTEM_STATE
                            ),
                        }
                    )
                result["story"] = story
            except ProbeError as error:
                telemetry_errors.append(f"story: {error}")

        if telemetry_errors:
            result["telemetry_errors"] = telemetry_errors

    return result


def print_result(result: dict[str, int | float | str], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False))
        return
    print(
        f"HP {float(result['current_hp']):g}/{float(result['max_hp']):g} "
        f"({float(result['hp_ratio']) * 100:.1f}%) | "
        f"PID {result['process_id']} | player {result['player_address']}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--watch",
        action="store_true",
        help="keep printing HP when it changes (Ctrl+C to stop)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.2,
        help="watch polling interval in seconds (default: 0.2)",
    )
    parser.add_argument("--json", action="store_true", help="emit one JSON object per reading")
    parser.add_argument(
        "--state",
        action="store_true",
        help="read scene, pause, player, HP and character-state gating fields",
    )
    parser.add_argument(
        "--watch-state",
        action="store_true",
        help="print scene/pause/HP/character-state changes for a limited duration",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="state-watch duration in seconds (default: 10)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval < 0.05:
        raise ProbeError("--interval must be at least 0.05 seconds")

    if args.state:
        print(json.dumps(read_state(), ensure_ascii=False))
        return 0

    if args.watch_state:
        if args.duration <= 0 or args.duration > 60:
            raise ProbeError("--duration must be greater than 0 and at most 60 seconds")
        started = time.monotonic()
        previous_state: tuple[object, ...] | None = None
        samples = 0
        while time.monotonic() - started < args.duration:
            state = read_state()
            signature = (
                state.get("scene"),
                state.get("pause_mask"),
                state.get("player_address"),
                state.get("current_hp"),
                state.get("max_hp"),
                state.get("character_state"),
                state.get("action_trigger_hash"),
            )
            samples += 1
            if signature != previous_state:
                state["elapsed_seconds"] = round(time.monotonic() - started, 4)
                print(json.dumps(state, ensure_ascii=False), flush=True)
                previous_state = signature
            time.sleep(args.interval)
        print(json.dumps({"status": "complete", "samples": samples}), flush=True)
        return 0

    previous: tuple[float, float] | None = None
    while True:
        result = read_hp()
        reading = (float(result["current_hp"]), float(result["max_hp"]))
        if not args.watch or reading != previous:
            print_result(result, args.json)
            sys.stdout.flush()
            previous = reading
        if not args.watch:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except ProbeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
