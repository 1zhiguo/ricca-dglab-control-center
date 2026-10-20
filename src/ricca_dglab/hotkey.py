"""One registered emergency chord, on its own Win32 message thread."""
import ctypes
from ctypes import wintypes
import queue
import re
import sys
import threading

from PySide6.QtCore import QObject, Signal, Qt

DEFAULT_HOTKEY = "Ctrl+F12"


def parse_hotkey(value):
    parts = [p.strip().upper() for p in str(value).split("+")]
    mods, key = set(parts[:-1]), parts[-1]
    if len(mods) != len(parts)-1 or not mods <= {"CTRL","ALT","SHIFT"}:
        raise ValueError("请选择单键，或 Ctrl、Alt、Shift 与一个按键的组合")
    keys = {"SPACE":0x20,"HOME":0x24,"END":0x23,"INSERT":0x2D,"DELETE":0x2E,"PAUSE":0x13}
    if re.fullmatch(r"F(?:[1-9]|10|11|12)",key): vk = 0x70+int(key[1:])-1
    elif re.fullmatch(r"[A-Z0-9]",key): vk = ord(key)
    elif key in keys: vk = keys[key]
    else: raise ValueError("请选择 F1–F12、字母、数字、Space、Home、End、Insert、Delete 或 Pause")
    if key == "DELETE" and {"CTRL","ALT"} <= mods:
        raise ValueError("Ctrl+Alt+Delete 是系统保留组合，不能使用")
    mask = sum({"CTRL":2,"ALT":1,"SHIFT":4}[m] for m in mods)
    names = {"CTRL":"Ctrl","ALT":"Alt","SHIFT":"Shift"}
    return "+".join([names[m] for m in ("CTRL","ALT","SHIFT") if m in mods]+[key.title() if len(key)>1 and not key.startswith("F") else key]), mask, vk


def chord_from_qt(key, modifiers):
    """Convert a captured key event, never localized/IME text, to a Win32 chord."""
    if modifiers & Qt.MetaModifier.value:
        raise ValueError("不支持 Win 键或系统保留组合")
    if int(Qt.Key_F1) <= key <= int(Qt.Key_F12): name = "F"+str(key-int(Qt.Key_F1)+1)
    elif ord("A") <= key <= ord("Z") or ord("0") <= key <= ord("9"): name = chr(key)
    else:
        name = {int(Qt.Key_Space):"Space",int(Qt.Key_Home):"Home",int(Qt.Key_End):"End",
                int(Qt.Key_Insert):"Insert",int(Qt.Key_Delete):"Delete",int(Qt.Key_Pause):"Pause"}.get(key,"")
    prefix = [name for flag,name in ((Qt.ControlModifier,"Ctrl"),(Qt.AltModifier,"Alt"),(Qt.ShiftModifier,"Shift"))
              if modifiers & flag.value]
    return parse_hotkey("+".join(prefix+[name]))[0]


class HookChordState:
    """Track only modifiers and the target key; no typing or key history stored."""
    MOD_KEYS = {0x10:4,0xA0:4,0xA1:4,0x11:2,0xA2:2,0xA3:2,0x12:1,0xA4:1,0xA5:1,0x5B:8,0x5C:8}

    def __init__(self, mask, key, held=()):
        self.mask, self.key, self.held, self.down = mask,key,set(held),False

    def feed(self, key, is_down):
        if key in self.MOD_KEYS:
            if is_down: self.held.add(key)
            else: self.held.discard(key)
        if key != self.key: return False
        was_down, self.down = self.down,is_down
        current = 0
        for modifier in self.held: current |= self.MOD_KEYS[modifier]
        return is_down and not was_down and current == self.mask


class EmergencyHotkey(QObject):
    triggered = Signal()

    def __init__(self, immediate_stop, parent=None):
        super().__init__(parent)
        self._immediate_stop = immediate_stop
        self._commands = queue.Queue()
        self._stop = threading.Event()
        self._hook_handle = None
        self._thread = threading.Thread(target=self._run,name="RiccaEmergencyHotkey",daemon=True)
        self._thread.start()

    def configure(self, chord):
        normalized, mask, key = parse_hotkey(chord)
        done, cancelled, result = threading.Event(), threading.Event(), []
        self._commands.put((normalized,mask,key,done,cancelled,result))
        # Registration runs on the message thread; configuration changes are
        # explicitly emergency-paused by the caller before this wait.
        if not done.wait(1):
            cancelled.set()
            return False,"快捷键注册超时，请重试"
        return result[0]

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)

    def _run(self):
        api = ctypes.WinDLL("user32",use_last_error=True) if sys.platform=="win32" else None
        if api:
            api.RegisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int,wintypes.UINT,wintypes.UINT]
            api.RegisterHotKey.restype=wintypes.BOOL
            api.UnregisterHotKey.argtypes=[wintypes.HWND,ctypes.c_int]
            api.PeekMessageW.argtypes=[ctypes.POINTER(wintypes.MSG),wintypes.HWND,wintypes.UINT,wintypes.UINT,wintypes.UINT]
            api.SetWindowsHookExW.argtypes=[ctypes.c_int,ctypes.c_void_p,wintypes.HINSTANCE,wintypes.DWORD]
            api.SetWindowsHookExW.restype=ctypes.c_void_p
            api.CallNextHookEx.argtypes=[ctypes.c_void_p,ctypes.c_int,wintypes.WPARAM,wintypes.LPARAM]
            api.CallNextHookEx.restype=ctypes.c_ssize_t
            api.UnhookWindowsHookEx.argtypes=[ctypes.c_void_p]
            kernel = ctypes.WinDLL("kernel32",use_last_error=True)
            kernel.GetModuleHandleW.argtypes=[wintypes.LPCWSTR]
            kernel.GetModuleHandleW.restype=wintypes.HMODULE
        hook_state = None
        class KeyboardData(ctypes.Structure):
            _fields_=[("vkCode",wintypes.DWORD),("scanCode",wintypes.DWORD),("flags",wintypes.DWORD),
                      ("time",wintypes.DWORD),("extra",ctypes.c_size_t)]
        def keyboard_callback(code,message,pointer):
            if code >= 0 and hook_state is not None:
                data = ctypes.cast(pointer,ctypes.POINTER(KeyboardData)).contents
                # Ignore injected events and always pass the key to the game.
                if not data.flags & 0x10 and message in (0x100,0x101,0x104,0x105):
                    if hook_state.feed(data.vkCode,message in (0x100,0x104)):
                        self._immediate_stop()
                        self.triggered.emit()
            return api.CallNextHookEx(self._hook_handle,code,message,pointer)
        callback = ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,wintypes.WPARAM,wintypes.LPARAM)(keyboard_callback) if api else None
        active_id, active_chord = None, ""
        try:
            while not self._stop.is_set():
                try:
                    chord,mask,key,done,cancelled,result = self._commands.get_nowait()
                except queue.Empty: pass
                else:
                    next_id = 0x6A02 if active_id==0x6A01 else 0x6A01
                    if cancelled.is_set():
                        result.append((False,"快捷键注册超时，请重试"))
                    elif chord == active_chord:
                        result.append((True,""))
                    elif api and key == 0x7B:
                        # F12 is debugger-reserved in RegisterHotKey. Observe it
                        # instead, on this same dedicated native message thread.
                        handle = self._hook_handle or api.SetWindowsHookExW(13,callback,kernel.GetModuleHandleW(None),0)
                        if not handle:
                            result.append((False,"快捷键被占用或无法注册，请更换组合"))
                        elif cancelled.is_set():
                            if not self._hook_handle: api.UnhookWindowsHookEx(handle)
                            result.append((False,"快捷键注册超时，请重试"))
                        else:
                            held = [vk for vk in HookChordState.MOD_KEYS if (vk >= 0xA0 or vk in (0x5B,0x5C)) and api.GetAsyncKeyState(vk) & 0x8000]
                            hook_state = HookChordState(mask,key,held)
                            self._hook_handle = handle
                            if active_id is not None: api.UnregisterHotKey(None,active_id)
                            active_id, active_chord = None,chord
                            result.append((True,""))
                    elif api and api.RegisterHotKey(None,next_id,mask|0x4000,key):
                        if cancelled.is_set():
                            api.UnregisterHotKey(None,next_id)
                            result.append((False,"快捷键注册超时，请重试"))
                        else:
                            if active_id is not None: api.UnregisterHotKey(None,active_id)
                            if self._hook_handle:
                                api.UnhookWindowsHookEx(self._hook_handle)
                                self._hook_handle, hook_state = None,None
                            active_id, active_chord = next_id,chord
                            result.append((True,""))
                    else:
                        result.append((False,"快捷键被占用或无法注册，请更换组合"))
                    done.set()
                if api:
                    msg = wintypes.MSG()
                    while api.PeekMessageW(ctypes.byref(msg),None,0,0,1):
                        if msg.message == 0x0312 and active_id is not None and msg.wParam == active_id:
                            # Never wait for Qt to regain focus or process its
                            # queue before asking the Socket thread to zero.
                            self._immediate_stop()
                            self.triggered.emit()
                self._stop.wait(.01)
        finally:
            if api and active_id is not None: api.UnregisterHotKey(None,active_id)
            if api and self._hook_handle:
                api.UnhookWindowsHookEx(self._hook_handle)
                self._hook_handle = None
