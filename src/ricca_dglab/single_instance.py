"""Windows session-wide single instance guard, shared across Python runtimes."""
import ctypes
from ctypes import wintypes
import sys


class SingleInstance:
    def __init__(self, name=r"Local\RiccaDGLab.ControlCenter.1"):
        self.name = name
        self.handle = None
        self.api = ctypes.WinDLL("kernel32", use_last_error=True) if sys.platform == "win32" else None
        if self.api:
            self.api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
            self.api.CreateMutexW.restype = wintypes.HANDLE
            self.api.CloseHandle.argtypes = [wintypes.HANDLE]
            self.api.CloseHandle.restype = wintypes.BOOL

    def acquire(self) -> bool:
        if self.handle is not None or self.api is None:
            return True
        ctypes.set_last_error(0)
        handle = self.api.CreateMutexW(None, False, self.name)
        error = ctypes.get_last_error()
        if not handle:
            raise OSError(error, "无法建立 Ricca 单实例保护")
        if error == 183:  # ERROR_ALREADY_EXISTS
            self.api.CloseHandle(handle)
            return False
        self.handle = handle
        return True

    def close(self):
        if self.handle is not None:
            self.api.CloseHandle(self.handle)
            self.handle = None


def show_existing_instance():
    if sys.platform != "win32":
        return
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    api.FindWindowW.restype = wintypes.HWND
    api.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    api.SetForegroundWindow.argtypes = [wintypes.HWND]
    api.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
    handle = api.FindWindowW(None, "Ricca × DG-LAB Control Center")
    if handle:
        api.ShowWindow(handle, 9)  # Restore a minimized existing window.
        api.SetForegroundWindow(handle)
    else:
        api.MessageBoxW(None, "Ricca × DG-LAB 已在启动或运行中，请勿重复打开。", "Ricca × DG-LAB", 0x40)
