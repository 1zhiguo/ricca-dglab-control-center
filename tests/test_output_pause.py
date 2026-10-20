import asyncio
import json
import queue
import socket
import unittest
from unittest.mock import patch

from ricca_dglab.dglab_bridge import DGLabBridge


class BridgePauseTests(unittest.IsolatedAsyncioTestCase):
    async def test_occupied_socket_reports_server_error_without_qr(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("0.0.0.0", 0))
            listener.listen(1)
            self.bridge.requested_port = listener.getsockname()[1]
            await self.bridge._run()
        events = list(self.bridge.events.queue)
        self.assertTrue(any(item.get("event") == "server_error" and "占用" in item["detail"] for _, item in events))
        self.assertFalse(self.bridge.server_ready)

    async def asyncSetUp(self):
        with patch("ricca_dglab.dglab_bridge.discover_lan_ips", return_value=()):
            self.bridge = DGLabBridge(queue.Queue(), port=0)
        self.bridge._loop = asyncio.get_running_loop()
        self.bridge.connected = True
        self.bridge.target_id = "fake-phone"
        self.messages = []
        owner = self

        class FakeSocket:
            async def send(self, value):
                owner.messages.append(json.loads(value)["message"])

        self.bridge._controller_ws = FakeSocket()

    async def test_master_pause_cancels_manual_test_even_when_auto_already_off(self):
        bridge = self.bridge
        task = asyncio.create_task(bridge._manual_test("A", 5, ("1818181830303030",)))
        await asyncio.sleep(.01)
        self.assertIn("strength-1+2+5", self.messages)
        bridge.set_paused(True)
        await asyncio.sleep(.01)
        self.assertEqual(self.messages[-4:], ["strength-1+2+0", "strength-2+2+0", "clear-1", "clear-2"])
        self.assertFalse(await bridge._send_message("pulse-A:[\"1818181830303030\"]"))
        self.assertFalse(bridge.manual_test(5, ("1818181830303030",), hard_cap=10))
        await asyncio.wait_for(task, .5)
        self.assertFalse(any(message.startswith("pulse-") for message in self.messages))
        self.assertFalse(any(payload.get("event") == "test_finished" for _, payload in list(bridge.events.queue)))

    async def test_resume_waits_for_zero_completion_and_does_not_reuse_old_outputs(self):
        bridge = self.bridge
        bridge._set_desired_outputs_in_loop(9, ("1818181830303030",), "old", 8, ("1818181830303030",), "old", 30)
        entered, release = asyncio.Event(), asyncio.Event()
        original = bridge._controller_ws.send

        async def delayed_send(packet):
            if json.loads(packet)["message"] == "strength-2+2+0":
                entered.set()
                await release.wait()
            await original(packet)

        bridge._controller_ws.send = delayed_send
        bridge._set_paused_in_loop(True)
        await asyncio.wait_for(entered.wait(), .5)
        bridge._set_paused_in_loop(False)
        bridge._set_auto_enabled_in_loop(True)
        bridge._set_desired_outputs_in_loop(20, (), "ignored", 20, (), "ignored", 30)
        self.assertTrue(bridge._paused)
        self.assertFalse(bridge._auto_enabled)
        self.assertEqual(bridge._desired_strength, {"A": 0, "B": 0})
        release.set()
        await asyncio.sleep(.01)
        self.assertFalse(bridge._paused)
        self.assertFalse(bridge._auto_enabled)
        self.assertEqual(self.messages[-2:], ["clear-1", "clear-2"])
        bridge._set_desired_outputs_in_loop(7, (), "fresh", 6, (), "fresh", 30)
        bridge._set_auto_enabled_in_loop(True)
        self.assertTrue(bridge._auto_enabled)
        self.assertEqual(bridge._desired_strength, {"A": 7, "B": 6})
