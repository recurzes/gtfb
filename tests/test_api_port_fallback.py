"""Unit and integration tests for dynamic local API port binding and fallback."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from gtfb.api import APIServer, DEFAULT_PORT, MAX_PORT, START_PORT
from gtfb.config import get_app_dir, get_config_dir


def get_free_port_block(count: int = 6) -> int:
    """Find a block of consecutive ports that are free on localhost."""
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as start_sock:
            start_sock.bind(("127.0.0.1", 0))
            base_port = start_sock.getsockname()[1]

        # Verify consecutive range is free
        sockets = []
        try:
            for p in range(base_port, base_port + count):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", p))
                sockets.append(s)
            return base_port
        except OSError:
            continue
        finally:
            for s in sockets:
                s.close()


class TestAPIPortFallback(unittest.TestCase):
    """Test dynamic port fallback and discovery file lifecycle."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.server: APIServer | None = None
        self.occupied_sockets: list[socket.socket] = []

    def tearDown(self):
        if self.server and self.server.is_running:
            self.server.stop()
        for sock in self.occupied_sockets:
            try:
                sock.close()
            except OSError:
                pass
        self.occupied_sockets.clear()
        self.temp_dir.cleanup()

    def _occupy_port(self, port: int) -> socket.socket:
        """Bind and listen on a port with a dummy socket to simulate conflict."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
        self.occupied_sockets.append(sock)
        return sock

    def test_constants_and_aliases(self):
        """Verify default port constants and storage alias."""
        self.assertEqual(START_PORT, 8765)
        self.assertEqual(MAX_PORT, 8775)
        self.assertEqual(DEFAULT_PORT, 8765)
        self.assertEqual(get_app_dir(), get_config_dir())

    def test_successful_binding_to_start_port(self):
        """Test binding to start_port when free and check api_port.json content."""
        base_port = get_free_port_block()
        self.server = APIServer(
            host="127.0.0.1",
            start_port=base_port,
            max_port=base_port + 5,
            config_dir=self.config_dir,
        )
        self.assertIsNone(self.server.bound_port)

        self.server.start()

        self.assertTrue(self.server.is_running)
        self.assertEqual(self.server.bound_port, base_port)
        self.assertEqual(self.server.port, base_port)

        # Verify discovery file
        port_file = self.config_dir / "api_port.json"
        self.assertTrue(port_file.exists())

        with open(port_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("port"), base_port)
        self.assertEqual(data.get("host"), "127.0.0.1")
        self.assertEqual(data.get("pid"), os.getpid())

        updated_at = data.get("updated_at")
        self.assertIsNotNone(updated_at)
        parsed_dt = datetime.fromisoformat(updated_at)
        self.assertIsNotNone(parsed_dt.tzinfo)

    def test_single_port_conflict_fallback(self):
        """Test that when start_port is occupied, APIServer falls back to start_port + 1."""
        base_port = get_free_port_block()
        self._occupy_port(base_port)

        self.server = APIServer(
            host="127.0.0.1",
            start_port=base_port,
            max_port=base_port + 5,
            config_dir=self.config_dir,
        )
        self.server.start()

        self.assertTrue(self.server.is_running)
        self.assertEqual(self.server.bound_port, base_port + 1)
        self.assertEqual(self.server.port, base_port + 1)

        port_file = self.config_dir / "api_port.json"
        self.assertTrue(port_file.exists())
        with open(port_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("port"), base_port + 1)

    def test_multi_port_conflict_fallback(self):
        """Test fallback across multiple occupied ports."""
        base_port = get_free_port_block()
        self._occupy_port(base_port)
        self._occupy_port(base_port + 1)
        self._occupy_port(base_port + 2)

        self.server = APIServer(
            host="127.0.0.1",
            start_port=base_port,
            max_port=base_port + 5,
            config_dir=self.config_dir,
        )
        self.server.start()

        self.assertTrue(self.server.is_running)
        self.assertEqual(self.server.bound_port, base_port + 3)

        port_file = self.config_dir / "api_port.json"
        with open(port_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data.get("port"), base_port + 3)

    def test_all_ports_exhausted_raises_runtime_error(self):
        """Test that exhausting all ports in range raises a descriptive RuntimeError."""
        base_port = get_free_port_block()
        max_port = base_port + 2
        for p in range(base_port, max_port + 1):
            self._occupy_port(p)

        self.server = APIServer(
            host="127.0.0.1",
            start_port=base_port,
            max_port=max_port,
            config_dir=self.config_dir,
        )

        expected_msg = f"Could not bind local API server to any port in range {base_port}-{max_port}"
        with self.assertRaises(RuntimeError) as ctx:
            self.server.start()

        self.assertIn(expected_msg, str(ctx.exception))
        self.assertFalse(self.server.is_running)
        self.assertIsNone(self.server.bound_port)

        port_file = self.config_dir / "api_port.json"
        self.assertFalse(port_file.exists())

    def test_port_file_cleaned_up_on_stop(self):
        """Test that api_port.json is cleanly unlinked on stop()."""
        base_port = get_free_port_block()
        self.server = APIServer(
            host="127.0.0.1",
            start_port=base_port,
            max_port=base_port + 5,
            config_dir=self.config_dir,
        )
        self.server.start()

        port_file = self.config_dir / "api_port.json"
        self.assertTrue(port_file.exists())

        self.server.stop()
        self.assertFalse(port_file.exists())
        self.assertIsNone(self.server.bound_port)

        # Second call to stop should be a graceful no-op
        self.server.stop()
        self.assertFalse(port_file.exists())

    def test_port_parameter_compatibility(self):
        """Test backward compatibility when port is explicitly provided."""
        base_port = get_free_port_block()
        # Single fixed port specified via port=
        self.server = APIServer(
            host="127.0.0.1",
            port=base_port,
            config_dir=self.config_dir,
        )
        self.assertEqual(self.server.start_port, base_port)
        self.assertEqual(self.server.max_port, base_port)

        self.server.start()
        self.assertEqual(self.server.bound_port, base_port)

    def test_default_config_dir_usage(self):
        """Test using default get_config_dir() when config_dir is None."""
        with tempfile.TemporaryDirectory() as default_tmp:
            tmp_path = Path(default_tmp)
            with patch("gtfb.api.server.get_config_dir", return_value=tmp_path):
                base_port = get_free_port_block()
                self.server = APIServer(
                    host="127.0.0.1",
                    start_port=base_port,
                    max_port=base_port + 5,
                )
                self.server.start()

                port_file = tmp_path / "api_port.json"
                self.assertTrue(port_file.exists())

                self.server.stop()
                self.assertFalse(port_file.exists())


if __name__ == "__main__":
    unittest.main()
