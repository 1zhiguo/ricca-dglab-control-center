import os
import socket
import sys
import subprocess
import unittest
import uuid
from unittest.mock import patch

from ricca_dglab.network import ipv4_interfaces, port_listeners
from ricca_dglab.single_instance import SingleInstance


@unittest.skipUnless(sys.platform == "win32", "Windows-only native integration")
class NativeConnectionTests(unittest.TestCase):
    def test_single_instance_is_exclusive_and_releases_cleanly(self):
        name = "Local\\RiccaDGLab.Test." + uuid.uuid4().hex
        first, second = SingleInstance(name), SingleInstance(name)
        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            child = subprocess.run([sys.executable, "-c",
                                    "from ricca_dglab.single_instance import SingleInstance; "
                                    f"instance=SingleInstance({name!r}); print(instance.acquire())"],
                                   capture_output=True, text=True, timeout=5,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(child.returncode, 0, child.stderr)
            self.assertEqual(child.stdout.strip(), "False")
            first.close()
            self.assertTrue(second.acquire())
        finally:
            first.close()
            second.close()

    def test_port_diagnostic_identifies_owned_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            rows = port_listeners(listener.getsockname()[1])
            self.assertTrue(any(row["pid"] == os.getpid() and row["ours"] for row in rows))

    def test_interface_inventory_contains_valid_unique_ipv4(self):
        import ipaddress
        rows = ipv4_interfaces()
        self.assertEqual(len(rows), len({row["address"] for row in rows}))
        for row in rows:
            self.assertIsInstance(ipaddress.ip_address(row["address"]), ipaddress.IPv4Address)
            self.assertIn(row["address"], row["label"])
