import asyncio
import json
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from ricca_dglab import audit
from ricca_dglab.dglab_bridge import DGLabBridge


class AuditTests(unittest.TestCase):
    def test_jsonl_is_flushed_and_rotation_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"runtime.jsonl"
            log=audit.AuditLog(path,max_bytes=700,backups=2)
            for index in range(12): log.record("test", index=index, label="死亡记录")
            log.close()
            files=list(Path(directory).glob("runtime.jsonl*"))
            self.assertLessEqual(len(files),3)
            entries=[json.loads(line) for file in files for line in file.read_text(encoding="utf-8").splitlines()]
            self.assertTrue(entries)
            self.assertEqual(max(e["index"] for e in entries),11)
            self.assertTrue(all("session" in e and "sequence" in e and "monotonic" in e for e in entries))
            self.assertEqual(log.error,"")

    def test_only_known_commands_are_retained_not_pairing_or_dialogue(self):
        self.assertEqual(audit.command_fields('ws://private/secret-id'),{"kind":"other"})
        self.assertEqual(audit.command_fields('strength-2+2+25')["strength"],25)
        frame='0A0A0A0A14141414'
        self.assertEqual(audit.command_fields('pulse-A:'+json.dumps([frame]))["frames"],[frame])
        self.assertEqual(audit.command_fields('pulse-A:["not-a-frame"]'),{"kind":"other"})
        self.assertNotIn("story",audit.state_fields({"story":{"message":"private dialogue"}}))

    def test_bridge_logs_block_controller_write_and_phone_forward_separately(self):
        async def scenario():
            bridge=DGLabBridge(queue.Queue(),port=0)
            bridge.connected=True
            bridge.controller_id='controller-secret'
            bridge.target_id='phone-secret'
            bridge._controller_ws=AsyncMock()
            with tempfile.TemporaryDirectory() as directory:
                log=audit.AuditLog(Path(directory)/"runtime.jsonl")
                with patch.object(audit,"_sink",log):
                    bridge._paused=True
                    self.assertFalse(await bridge._send_message('strength-1+2+25'))
                    bridge._paused=False
                    self.assertTrue(await bridge._send_message('strength-1+2+25'))
                    target=AsyncMock()
                    bridge._clients[bridge.target_id]=target
                    bridge._relations[bridge.controller_id]=bridge.target_id
                    await bridge._forward_message(bridge.controller_id,{
                        'type':'msg','clientId':bridge.controller_id,
                        'targetId':bridge.target_id,'message':'strength-1+2+25'})
                log.close()
                text=log.path.read_text(encoding="utf-8")
                entries=[json.loads(line) for line in text.splitlines()]
                self.assertEqual(entries[0]['reason'],'bridge-paused')
                self.assertEqual(entries[1]['outcome'],'written-to-controller-websocket')
                self.assertEqual(entries[2]['outcome'],'written-to-phone-websocket')
                self.assertNotIn('controller-secret',text)
                self.assertNotIn('phone-secret',text)
        asyncio.run(scenario())

    def test_full_queue_and_writer_failure_cannot_block_the_output_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            log=audit.AuditLog(Path(directory)/"runtime.jsonl")
            with patch.object(log._queue,'put_nowait',side_effect=queue.Full):
                log.record('dropped')
            self.assertEqual(log.dropped,1)
            with patch.object(log._handler,'shouldRollover',side_effect=OSError('disk full')):
                log.record('failure')
                log._queue.join()
            self.assertEqual(log.error,'OSError')
            log.record('recovered')
            log.close()
            self.assertIn('recovered',log.path.read_text(encoding='utf-8'))
