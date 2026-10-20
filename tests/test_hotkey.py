import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import MagicMock, Mock, patch
from ricca_dglab.hotkey import parse_hotkey, DEFAULT_HOTKEY, chord_from_qt, HookChordState
from PySide6.QtCore import Qt
from ricca_dglab.product_config import ProductConfig
from ricca_dglab.backend import AppBackend
import test_channel_backend as fixture

class HotkeyParserTests(unittest.TestCase):
    def test_upgrade_preserves_previously_saved_shortcuts(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"settings.json"
            self.assertEqual(ProductConfig(path).values["emergency_hotkey"],"Ctrl+F12")
            for value in ("Ctrl+Alt+F10","Ctrl+Shift+F9","Pause"):
                path.write_text(json.dumps({"emergency_hotkey":value}),encoding="utf-8")
                self.assertEqual(ProductConfig(path).values["emergency_hotkey"],value)

    def test_default_and_layout_independent_chords(self):
        self.assertEqual(parse_hotkey(DEFAULT_HOTKEY),(DEFAULT_HOTKEY,2,0x7B))
        self.assertEqual(parse_hotkey(" shift + CTRL + f9 "),("Ctrl+Shift+F9",6,0x78))
        for bad in ("","Ctrl","Ctrl+","Win+Ctrl+A","Ctrl+Alt+Delete","Ctrl+Ctrl+A","Ctrl+Alt+不存在"):
            with self.assertRaises(ValueError): parse_hotkey(bad)

    def test_single_key_and_single_modifier(self):
        self.assertEqual(parse_hotkey("Pause"),("Pause",0,0x13))
        self.assertEqual(parse_hotkey("F10"),("F10",0,0x79))
        self.assertEqual(parse_hotkey("Ctrl+F10"),("Ctrl+F10",2,0x79))
        self.assertEqual(parse_hotkey("Ctrl+Alt+F10"),("Ctrl+Alt+F10",3,0x79))

    def test_qt_capture_uses_key_codes_not_translated_text(self):
        self.assertEqual(chord_from_qt(int(Qt.Key_F12),Qt.ControlModifier.value),"Ctrl+F12")
        self.assertEqual(chord_from_qt(int(Qt.Key_Pause),0),"Pause")
        self.assertEqual(chord_from_qt(int(Qt.Key_A),Qt.ShiftModifier.value),"Shift+A")
        with self.assertRaises(ValueError): chord_from_qt(int(Qt.Key_F12),Qt.MetaModifier.value)

    def test_f12_observer_matches_exact_modifiers_and_no_repeat(self):
        state = HookChordState(2,0x7B)
        self.assertFalse(state.feed(0x7B,True))
        state.feed(0x7B,False)
        state.feed(0xA2,True)
        self.assertTrue(state.feed(0x7B,True))
        self.assertFalse(state.feed(0x7B,True))
        state.feed(0x7B,False); state.feed(0xA4,True)
        self.assertFalse(state.feed(0x7B,True))
        state.feed(0x7B,False); state.feed(0xA4,False)
        self.assertTrue(state.feed(0x7B,True))
        state.feed(0x7B,False); state.feed(0xA2,False); state.feed(0xA3,True)
        self.assertTrue(state.feed(0x7B,True))

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
