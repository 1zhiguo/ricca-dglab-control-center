from copy import deepcopy
import unittest
from unittest.mock import MagicMock
import test_channel_backend as fixture
from ricca_dglab.hud import GameViewport, hud_geometry
from ricca_dglab.hud_settings import HUD_DEFAULTS, sanitize_hud_settings
from ricca_dglab.product_config import ProductConfig
from ricca_dglab.ovc_pipeline import OvcOutputPlan


class HudSettingsTests(unittest.TestCase):
    def test_bad_values_are_bounded_and_empty_hud_is_repaired(self):
        result = sanitize_hud_settings({"scale": float("nan"), "x": -3, "y": 500,
                                        "opacity": 1, "anchor": [], "show_pulse": False,
                                        "show_ovc": False, "show_a": False, "show_b": False})
        self.assertEqual(result["scale"], 100)
        self.assertEqual((result["x"], result["y"], result["opacity"]), (0, 100, 20))
        self.assertEqual(result["anchor"], "auto")
        self.assertTrue(result["show_pulse"] and result["show_a"])

    def test_anchors_scaling_and_visible_cells_stay_inside_client(self):
        viewport = GameViewport(-1280, 100, 1280, 720, -1280, 0)
        for anchor in ("auto", "top_left", "top_center", "top_right", "bottom_left", "bottom_center", "bottom_right", "custom"):
            for scale in (60, 100, 180):
                bounds = hud_geometry(viewport, screen_x=-1280, settings={"anchor": anchor, "scale": scale, "x": 100, "y": 100})
                self.assertGreaterEqual(bounds.x(), -1280)
                self.assertGreaterEqual(bounds.y(), 100)
                self.assertLessEqual(bounds.x() + bounds.width(), 0)
                self.assertLessEqual(bounds.y() + bounds.height(), 820)
        full = hud_geometry(viewport, screen_x=-1280)
        single = hud_geometry(viewport, screen_x=-1280, settings={"show_pulse": False, "show_b": False})
        self.assertAlmostEqual(single.width() * 4, full.width(), delta=2)


class HudBackendTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    tearDown = fixture.ChannelBackendTests.tearDown
    setUp = fixture.ChannelBackendTests.setUp

    def test_hud_save_changes_no_output_or_device_preferences(self):
        b = self.backend
        original = deepcopy(b._config.values)
        b._bridge = MagicMock()
        b._ovc_bridge = MagicMock()
        b._v4_hub = MagicMock()
        b._user_output_paused = True
        self.assertTrue(b.saveHudSettings({**HUD_DEFAULTS, "scale": 140, "anchor": "custom", "x": 90}))
        self.assertEqual(b.hudSettings["scale"], 140)
        self.assertEqual(ProductConfig(b._config.path).values["hud_settings"], b.hudSettings)
        self.assertEqual({k: v for k, v in original.items() if k != "hud_settings"},
                         {k: v for k, v in b._config.values.items() if k != "hud_settings"})
        self.assertTrue(b.userOutputPaused)
        b._bridge.assert_not_called()
        self.assertEqual(b._bridge.mock_calls + b._ovc_bridge.mock_calls + b._v4_hub.mock_calls, [])
        saved = deepcopy(b.hudSettings)
        self.assertFalse(b.saveHudSettings({"show_a": False, "show_b": False}))
        self.assertEqual(b.hudSettings, saved)

    def test_ovc_readings_have_five_relative_bars_and_protocol_steps(self):
        b = self.backend
        b._ovc_connected = True
        b._ovc_route_paused = False
        b._stop_latched = b._user_output_paused = False
        b._config.values["ovc_profile"]["hard_cap"] = 200
        b._ovc_plan = OvcOutputPlan(strength_a=89, strength_b=200, hard_cap=200, allowed=True, paused=False)
        reading = b.hudReadings
        self.assertEqual((reading["ovcA"]["strength"], reading["ovcA"]["bars"]), (80, 2))
        self.assertEqual((reading["ovcB"]["strength"], reading["ovcB"]["bars"]), (200, 5))
        b._ovc_route_paused = True
        self.assertEqual(b.hudReadings["ovcA"]["strength"], 0)
        self.assertEqual(b.hudReadings["ovcA"]["status"], "已暂停")
        b._ovc_connected = False
        self.assertEqual(b.hudReadings["ovcA"]["status"], "未连接")
