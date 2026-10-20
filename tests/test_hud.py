from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QObject, QCoreApplication, QRect, Signal

from ricca_dglab.hud import GameViewport, HudController, hud_geometry, screen_for_viewport
from ricca_dglab.product_config import ProductConfig


class FakeWindow(QObject):
    def __init__(self):
        super().__init__()
        self.shown = False
        self.bounds = QRect()
        self.display = None

    def show(self):
        self.shown = True

    def hide(self):
        self.shown = False

    def geometry(self):
        return self.bounds

    def setGeometry(self, value):
        self.bounds = value

    def screen(self):
        return self.display

    def setScreen(self, value):
        self.display = value


class FakeBackend(QObject):
    changed = Signal()
    gameHudEnabled = True
    telemetryOnline = True
    gameScene = "gameplay"
    story = {}
    @property
    def _state(self):
        return {"scene": self.gameScene, "story": self.story}
    processId = 123
    previewA = 15
    previewB = 20
    hardCap = 30
    waveA = "impact"
    waveB = "wall"
    waveAPoints = [100]
    waveBPoints = [75]
    _mapping = SimpleNamespace(pulse_token=lambda channel: "1")


class HudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_reference_geometry_matches_manaka(self):
        self.assertEqual(hud_geometry(GameViewport(0, 0, 1920, 1080)), QRect(403, 988, 730, 68))
        self.assertEqual(hud_geometry(GameViewport(100, 200, 1280, 720)), QRect(369, 859, 486, 45))

    def test_mixed_dpi_and_negative_monitor_origins(self):
        viewport = GameViewport(2000, 100, 1920, 1080, 1920, 0, "second")
        self.assertEqual(hud_geometry(viewport, dpr=1.5, screen_x=1920), QRect(2242, 725, 486, 45))
        negative = GameViewport(-1920, 0, 1920, 1080, -1920, 0, "left")
        self.assertEqual(hud_geometry(negative, dpr=1.5, screen_x=-1280), QRect(-1011, 659, 486, 45))

    def test_story_top_geometry(self):
        self.assertEqual(hud_geometry(GameViewport(0, 0, 1920, 1080), top_aligned=True),
                         QRect(403, 24, 730, 68))
        viewport = GameViewport(2000, 100, 1920, 1080, 1920, 0, "second")
        self.assertEqual(hud_geometry(viewport, dpr=1.5, screen_x=1920, top_aligned=True),
                         QRect(2242, 83, 486, 45))

    def test_scene_visibility_and_story_placement(self):
        backend, window = FakeBackend(), FakeWindow()
        viewport = GameViewport(0, 0, 1920, 1080, monitor_name="test")
        screen = SimpleNamespace(name=lambda: "test", devicePixelRatio=lambda: 1,
                                 geometry=lambda: QRect(0, 0, 1920, 1080))
        hud = HudController(backend, window, viewport_reader=lambda pid: viewport)
        hud.timer.stop()
        try:
            with patch("ricca_dglab.hud.QGuiApplication.screens", return_value=[screen]):
                hud.tick()
                self.assertTrue(window.shown)
                self.assertEqual(window.bounds.y(), 988)
                backend.gameScene = "adv"
                backend.changed.emit()
                hud.tick()
                self.assertTrue(window.shown)
                self.assertEqual(window.bounds.y(), 24)
                backend.gameScene = "atd"
                backend.story = {"asset_name": "ADV/Scene3D_RiccaHellplant/Scene3D_RiccaHellplant.csv"}
                hud.tick()
                self.assertTrue(window.shown)
                self.assertEqual(window.bounds.y(), 24)
                backend.story = {}
                backend.gameScene = "gameplay"
                hud.tick()
                self.assertEqual(window.bounds.y(), 988)
                for scene in ("none", "other", "unknown", "atd", "anv", "—"):
                    backend.gameScene = scene
                    backend.changed.emit()
                    self.assertFalse(window.shown)
                    hud.tick()
                    self.assertFalse(window.shown)
                    backend.gameScene = "gameplay"
                    hud.tick()
                    self.assertTrue(window.shown)
        finally:
            hud.shutdown()

    def test_friendly_screen_names_match_physical_monitor_instead_of_hiding(self):
        first = SimpleNamespace(name=lambda: "LG ULTRAGEAR", devicePixelRatio=lambda: 1.25,
                                geometry=lambda: QRect(0, 0, 2048, 1152))
        second = SimpleNamespace(name=lambda: "Q27G2SG4B+", devicePixelRatio=lambda: 1.0,
                                 geometry=lambda: QRect(2560, 0, 1920, 1080))
        viewport = GameViewport(0, 0, 2560, 1440, 0, 0, r"\\.\DISPLAY1", 2560, 1440)
        self.assertIs(screen_for_viewport(viewport, [second, first]), first)
        other = GameViewport(2560, 0, 1920, 1080, 2560, 0, r"\\.\DISPLAY2", 1920, 1080)
        self.assertIs(screen_for_viewport(other, [first, second]), second)

    def test_tracks_client_and_hides_when_focus_or_telemetry_is_lost(self):
        backend, window = FakeBackend(), FakeWindow()
        viewport = [GameViewport(0, 0, 1920, 1080, monitor_name="test")]
        screen = SimpleNamespace(name=lambda: "test", devicePixelRatio=lambda: 1,
                                 geometry=lambda: QRect(0, 0, 1920, 1080))
        hud = HudController(backend, window, viewport_reader=lambda pid: viewport[0])
        hud.timer.stop()
        try:
            with patch("ricca_dglab.hud.QGuiApplication.screens", return_value=[screen]):
                hud.tick()
                self.assertTrue(window.shown)
                self.assertEqual(window.bounds, QRect(403, 988, 730, 68))
                self.assertAlmostEqual(hud.historyA[-1], 0.5)
                self.assertAlmostEqual(hud.historyB[-1], 0.5)
                viewport[0] = GameViewport(100, 200, 1280, 720, monitor_name="test")
                hud.tick()
                self.assertEqual(window.bounds, QRect(369, 859, 486, 45))
                viewport[0] = None  # Alt-tab, minimization or game exit.
                hud.tick()
                self.assertFalse(window.shown)
                self.assertEqual(hud.historyA, [0.0] * 32)
                viewport[0] = GameViewport(0, 0, 1920, 1080, monitor_name="test")
                hud.tick()
                backend.telemetryOnline = False
                backend.changed.emit()
                self.assertFalse(window.shown)
                backend.telemetryOnline = True
                hud.tick()
                backend.gameHudEnabled = False
                backend.changed.emit()
                self.assertFalse(window.shown)
        finally:
            hud.shutdown()

    def test_switch_is_independent_of_output_and_persists(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temporary:
            config = ProductConfig(Path(temporary) / "settings.json")
            self.assertTrue(config.values["game_hud_enabled"])
            config.update({"game_hud_enabled": False})
            self.assertFalse(ProductConfig(config.path).values["game_hud_enabled"])
            self.assertEqual(config.values["hard_cap"], 30)


if __name__ == "__main__":
    unittest.main()
