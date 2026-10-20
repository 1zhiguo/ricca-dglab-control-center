"""One registered emergency chord, on its own Win32 message thread."""
import ctypes
from ctypes import wintypes
import queue
import re
import sys
import threading

from PySide6.QtCore import QObject, Signal

DEFAULT_HOTKEY = "Ctrl+Alt+F10"


def parse_hotkey(value):
    parts = [p.strip().upper() for p in str(value).split("+")]
    mods, key = set(parts[:-1]), parts[-1]
    if len(mods) != len(parts)-1 or not mods <= {"CTRL","ALT","SHIFT"} or len(mods) < 2:
        raise ValueError("快捷键需包含至少两个修饰键（Ctrl、Alt、Shift）和一个按键")
    keys = {"SPACE":0x20,"HOME":0x24,"END":0x23,"INSERT":0x2D,"DELETE":0x2E,"PAUSE":0x13}
    if re.fullmatch(r"F(?:[1-9]|10|11)",key): vk = 0x70+int(key[1:])-1
    elif re.fullmatch(r"[A-Z0-9]",key): vk = ord(key)
    elif key in keys: vk = keys[key]
    else: raise ValueError("请选择 F1–F11、字母、数字、Space、Home、End、Insert、Delete 或 Pause")
    if key == "DELETE" and {"CTRL","ALT"} <= mods:
        raise ValueError("Ctrl+Alt+Delete 是系统保留组合，不能使用")
    mask = sum({"CTRL":2,"ALT":1,"SHIFT":4}[m] for m in mods)
    names = {"CTRL":"Ctrl","ALT":"Alt","SHIFT":"Shift"}
    return "+".join([names[m] for m in ("CTRL","ALT","SHIFT") if m in mods]+[key.title() if len(key)>1 and not key.startswith("F") else key]), mask, vk


class EmergencyHotkey(QObject):
    triggered = Signal()

    def __init__(self, immediate_stop, parent=None):
        super().__init__(parent)
        self._immediate_stop = immediate_stop
        self._commands = queue.Queue()
        self._stop = threading.Event()
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
                    elif api and api.RegisterHotKey(None,next_id,mask|0x4000,key):
                        if cancelled.is_set():
                            api.UnregisterHotKey(None,next_id)
                            result.append((False,"快捷键注册超时，请重试"))
                        else:
                            if active_id is not None: api.UnregisterHotKey(None,active_id)
                            active_id, active_chord = next_id,chord
                            result.append((True,""))
                    else:
                        result.append((False,"快捷键被占用或无法注册，请更换组合"))
                    done.set()
                if api:
                    msg = wintypes.MSG()
                    while api.PeekMessageW(ctypes.byref(msg),None,0x0312,0x0312,1):
                        if msg.wParam == active_id:
                            # Never wait for Qt to regain focus or process its
                            # queue before asking the Socket thread to zero.
                            self._immediate_stop()
                            self.triggered.emit()
                self._stop.wait(.01)
        finally:
            if api and active_id is not None: api.UnregisterHotKey(None,active_id)
