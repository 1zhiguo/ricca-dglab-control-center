"""Display-only UI state must never change the existing output/config state."""
from copy import deepcopy
import unittest
from unittest.mock import MagicMock

import test_channel_backend as fixture


class WorkbenchDisplayStateTests(unittest.TestCase):
    setUpClass = classmethod(fixture.ChannelBackendTests.setUpClass.__func__)
    setUp = fixture.ChannelBackendTests.setUp
    tearDown = fixture.ChannelBackendTests.tearDown

    def test_emergency_status_is_a_read_only_view_of_the_existing_latch(self):
        backend = self.backend
        original = deepcopy(backend._config.values)
        backend._bridge = MagicMock()
        backend._v4_hub = MagicMock()
        for stopped, user_paused in ((False, False), (True, True), (False, True)):
            backend._stop_latched = stopped
            backend._user_output_paused = user_paused
            for _ in range(20):
                self.assertIs(backend.emergencyStopped, stopped)
                self.assertIs(backend.userOutputPaused, user_paused)
            self.assertIs(backend._stop_latched, stopped)
            self.assertIs(backend._user_output_paused, user_paused)
        self.assertEqual(backend._config.values, original)
        self.assertEqual(backend._bridge.mock_calls, [])
        self.assertEqual(backend._v4_hub.mock_calls, [])

    def test_workbench_paths_remain_display_only_until_explicit_save(self):
        from pathlib import Path
        qml = Path(__file__).resolve().parents[1] / "src/ricca_dglab/qml"
        source = (qml / "DeviceWorkbench.qml").read_text(encoding="utf-8")
        self.assertIn("refreshSavedView();loadSaved()", source)
        # Navigation never changes output. The newly visible route button
        # may call the existing toggle only from an explicit click handler.
        for line in source.splitlines():
            if "togglePulseOutput(" in line or "toggleOvcOutput(" in line:
                self.assertTrue(line.lstrip().startswith("onClicked:"), line)
        navigation = "\n".join(line for line in source.splitlines()
                               if not line.lstrip().startswith("onClicked:"))
        for disallowed in ("setOutputProfile(", "togglePulseOutput(",
                           "toggleOvcOutput(", "toggleOutputPause("):
            self.assertNotIn(disallowed, navigation)
        wrapper = (qml / "OvcWorkbench.qml").read_text(encoding="utf-8")
        self.assertIn("DeviceWorkbench", wrapper)
        self.assertIn("vibration: true", wrapper)
