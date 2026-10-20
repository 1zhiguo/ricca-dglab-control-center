"""Real Win32 registration/dispatch with mock zero only; never drives a device."""
import ctypes
import threading
from PySide6.QtCore import QCoreApplication
from ricca_dglab.hotkey import EmergencyHotkey

app=QCoreApplication([])
stopped=threading.Event()
first=EmergencyHotkey(stopped.set)
second=EmergencyHotkey(lambda:None)
try:
    chord="Ctrl+Alt+Shift+F11"
    assert first.configure(chord)[0], "QA chord occupied; no existing registration was replaced"
    assert not second.configure(chord)[0], "Conflict must not silently succeed"
    # No Qt event pumping: immediate zero must arrive on its own native thread.
    assert ctypes.windll.user32.PostThreadMessageW(first._thread.native_id,0x0312,0x6A01,0)
    assert stopped.wait(.3), "Emergency path waited for the Qt thread"
    first.close()
    assert second.configure(chord)[0], "Closing must release registration"
    # F12 must use the observer, not the debugger-reserved RegisterHotKey API.
    assert second.configure("Ctrl+F12")[0], "F12 observer installation failed"
    assert second._hook_handle, "F12 was incorrectly passed to RegisterHotKey"
    assert second.configure("Ctrl+Alt+Shift+F10")[0]
    assert second._hook_handle is None, "Switching must remove the old F12 observer"
    assert second.configure("Pause")[0], "Single-key pause registration failed"
    second.close()
    assert second._hook_handle is None
    print("Win32 global registration, conflicts, Qt-independent MOCK zero, F12 observer, single key and cleanup: OK")
finally:
    first.close(); second.close()
