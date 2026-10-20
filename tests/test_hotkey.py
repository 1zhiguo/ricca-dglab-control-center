import unittest
from unittest.mock import MagicMock, Mock, patch
from ricca_dglab.hotkey import parse_hotkey, DEFAULT_HOTKEY
from ricca_dglab.backend import AppBackend
import test_channel_backend as fixture

class HotkeyParserTests(unittest.TestCase):
    def test_default_and_layout_independent_chords(self):
        self.assertEqual(parse_hotkey(DEFAULT_HOTKEY),(DEFAULT_HOTKEY,3,0x79))
        self.assertEqual(parse_hotkey(" shift + CTRL + f9 "),("Ctrl+Shift+F9",6,0x78))
        for bad in ("F10","Ctrl+F10","Ctrl+Alt+F12","Win+Ctrl+A","Ctrl+Alt+Delete","Ctrl+Ctrl+A","Ctrl+Alt+不存在"):
            with self.assertRaises(ValueError): parse_hotkey(bad)

class HotkeyBackendTests(unittest.TestCase):
    setUpClass=classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    setUp=fixture.ChannelBackendTests.setUp
    tearDown=fixture.ChannelBackendTests.tearDown

    def test_conflict_keeps_old_chord_and_success_stays_emergency_paused(self):
        backend=self.backend
        service=MagicMock()
        backend._hotkey_service=service
        service.configure.return_value=(False,"occupied")
        self.assertFalse(backend.saveEmergencyHotkey("Ctrl+Shift+F9"))
        self.assertEqual(backend.emergencyHotkey,DEFAULT_HOTKEY)
        service.configure.return_value=(True,"")
        self.assertTrue(backend.saveEmergencyHotkey("Ctrl+Shift+F9"))
        self.assertEqual(backend.emergencyHotkey,"Ctrl+Shift+F9")
        self.assertTrue(backend._stop_latched and backend.userOutputPaused)
        with patch.object(backend._config,"save",side_effect=OSError("blocked")):
            self.assertFalse(backend.saveEmergencyHotkey(DEFAULT_HOTKEY))
        service.configure.assert_called_with("Ctrl+Shift+F9")
        self.assertEqual(backend.emergencyHotkey,"Ctrl+Shift+F9")

    def test_shutdown_zero_precedes_any_worker_wait(self):
        backend=self.backend
        order=[]
        backend._bridge=MagicMock()
        backend._bridge.emergency_stop.side_effect=lambda:order.append("zero")
        backend._bridge.stop.side_effect=lambda:order.append("bridge-stop")
        with patch.object(backend,"_stop_audio_capture",side_effect=lambda:order.append("audio-wait")):
            backend.shutdown()
        self.assertLess(order.index("zero"),order.index("audio-wait"))
        self.assertLess(order.index("bridge-stop"),order.index("audio-wait"))
