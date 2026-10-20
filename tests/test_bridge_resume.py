"""Deterministic scene-resume races; no server, phone or physical device."""
import asyncio
from contextlib import suppress
import queue
import time
import unittest
from unittest.mock import AsyncMock, patch

from ricca_dglab.dglab_bridge import DGLabBridge


class BridgeResumeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        with patch("ricca_dglab.dglab_bridge.ipv4_interfaces", return_value=[{"address":"127.0.0.1"}]):
            self.bridge = DGLabBridge(queue.Queue())
        self.bridge.connected = True
        self.bridge._safe_zero_async = AsyncMock()
        self.bridge._send_message = AsyncMock(return_value=True)

    def snapshot(self, strength=8):
        self.bridge._set_desired_outputs_in_loop(strength, ("1818181830303030",), "official_tide",
                                                0, (), "idle", 10)

    async def settle(self):
        for _ in range(3): await asyncio.sleep(0)

    async def test_dropped_first_scene_frame_cannot_arm_or_trigger_false_watchdog(self):
        bridge = self.bridge
        for _ in range(50):
            bridge._set_paused_in_loop(True)
            await self.settle()
            bridge._set_paused_in_loop(False)
            self.snapshot()  # Dropped while the asynchronous resume is pending.
            await self.settle()
            bridge._set_auto_enabled_in_loop(True)
            self.assertFalse(bridge._auto_enabled)
            self.assertEqual(bridge._desired_updated_at,0)
            self.snapshot()  # Next UI frame is fresh; no extra sleep/timeout.
            bridge._set_auto_enabled_in_loop(True)
            self.assertTrue(bridge._auto_enabled)
            self.assertEqual(bridge._desired_strength["A"],8)
        self.assertTrue(bridge.events.empty())

    async def test_older_resume_cannot_bypass_newer_zero_clear_barrier(self):
        bridge = self.bridge
        first, second = asyncio.Event(), asyncio.Event()
        barriers = iter((first,second))
        async def zero(): await next(barriers).wait()
        bridge._safe_zero_async = zero
        bridge._set_paused_in_loop(True)
        bridge._set_paused_in_loop(False)
        await self.settle()
        bridge._set_paused_in_loop(True)
        bridge._set_paused_in_loop(False)
        await self.settle()
        first.set()
        await self.settle()
        self.assertTrue(bridge._paused)
        self.snapshot()
        bridge._set_auto_enabled_in_loop(True)
        self.assertFalse(bridge._auto_enabled)
        second.set()
        await self.settle()
        self.assertFalse(bridge._paused)
        self.snapshot()
        bridge._set_auto_enabled_in_loop(True)
        self.assertTrue(bridge._auto_enabled)

    async def test_disable_clear_must_finish_before_new_wave_is_authorized(self):
        bridge = self.bridge
        self.snapshot()
        bridge._set_auto_enabled_in_loop(True)
        done = asyncio.Event()
        async def zero(): await done.wait()
        bridge._safe_zero_async = zero
        bridge._set_auto_enabled_in_loop(False)
        self.snapshot(9)
        bridge._set_auto_enabled_in_loop(True)
        self.assertFalse(bridge._auto_enabled)
        done.set()
        await self.settle()
        self.snapshot(9)
        bridge._set_auto_enabled_in_loop(True)
        self.assertTrue(bridge._auto_enabled)

    async def test_stale_future_and_emergency_snapshots_cannot_rearm(self):
        bridge = self.bridge
        for timestamp in (0, time.monotonic()-1, time.monotonic()+1):
            bridge._desired_updated_at = timestamp
            bridge._set_auto_enabled_in_loop(True)
            self.assertFalse(bridge._auto_enabled)
        self.snapshot()
        bridge._set_auto_enabled_in_loop(True)
        bridge._request_emergency_in_loop()
        await self.settle()
        bridge._set_auto_enabled_in_loop(True)
        self.assertFalse(bridge._auto_enabled)
        self.assertEqual(bridge._desired_updated_at,0)

    async def test_real_stall_still_triggers_the_500ms_watchdog(self):
        bridge = self.bridge
        self.snapshot()
        bridge._set_auto_enabled_in_loop(True)
        bridge._desired_updated_at = time.monotonic()-0.501
        output = asyncio.create_task(bridge._output_loop())
        try:
            await asyncio.sleep(.07)
            self.assertFalse(bridge._auto_enabled)
            self.assertTrue(any(payload.get("event")=="output_timeout"
                                for _,payload in bridge.events.queue))
            bridge._safe_zero_async.assert_awaited()
        finally:
            output.cancel()
            with suppress(asyncio.CancelledError): await output

    async def test_global_hotkey_latch_blocks_old_ui_frames_until_explicit_resume(self):
        bridge=self.bridge
        self.snapshot()
        bridge._set_auto_enabled_in_loop(True)
        bridge.latch_global_emergency_stop()
        for _ in range(5):
            self.snapshot(9)
            bridge._set_auto_enabled_in_loop(True)
            self.assertFalse(bridge._auto_enabled)
        bridge.clear_global_emergency_stop()
        bridge._set_auto_enabled_in_loop(True)
        self.assertFalse(bridge._auto_enabled), "Resume requires a fresh snapshot"
        self.snapshot(9)
        bridge._set_auto_enabled_in_loop(True)
        self.assertTrue(bridge._auto_enabled)

    async def test_zero_strength_audio_stays_authorized_with_fresh_frames(self):
        bridge = self.bridge
        self.snapshot(0)
        bridge._set_auto_enabled_in_loop(True)
        output = asyncio.create_task(bridge._output_loop())
        try:
            for _ in range(20):
                self.snapshot(0)
                await asyncio.sleep(.033)
            self.assertTrue(bridge._auto_enabled)
            self.assertFalse(any(payload.get("event")=="output_timeout"
                                 for _,payload in bridge.events.queue))
        finally:
            output.cancel()
            with suppress(asyncio.CancelledError): await output
