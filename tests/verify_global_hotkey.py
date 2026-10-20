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
    print("Win32 global registration, conflict detection, Qt-independent MOCK zero and unregister: OK")
finally:
    first.close(); second.close()
