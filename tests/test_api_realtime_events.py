"""Unit tests for APIServer realtime SSE /events endpoint and config broadcasting."""

import http.client
import json
import time
import unittest
from pathlib import Path
import tempfile
import threading

import socket

from gtfb.api.server import APIServer
from gtfb.config.models import BlockRule, ConfigProfile


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestAPIServerRealtimeEvents(unittest.TestCase):
    """Test suite verifying realtime SSE broadcasting on /events."""

    def setUp(self) -> None:
        self.port = get_free_port()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_dir = Path(self.temp_dir.name)
        self.profile = ConfigProfile()
        self.server = APIServer(
            port=self.port,
            start_port=self.port,
            max_port=self.port,
            config_provider=lambda: self.profile,
            config_dir=self.config_dir,
        )
        self.server.start()


    def tearDown(self) -> None:
        self.server.stop()
        self.temp_dir.cleanup()

    def test_events_stream_initial_payload_and_broadcast(self) -> None:
        """Verify that connecting to /events yields initial config and receives updates when notified."""
        conn = http.client.HTTPConnection("127.0.0.1", self.server.bound_port, timeout=5.0)
        conn.request("GET", "/events", headers={"Accept": "text/event-stream"})
        resp = conn.getresponse()

        self.assertEqual(resp.status, 200)
        self.assertIn("text/event-stream", resp.getheader("Content-Type", ""))

        # Read first event (init event)
        line1 = resp.fp.readline().decode("utf-8")
        self.assertTrue(line1.startswith("data:"))
        data1 = json.loads(line1[5:].strip())
        self.assertEqual(data1.get("type"), "init")
        self.assertIn("config", data1)

        # Skip separator
        resp.fp.readline()

        # Trigger config update broadcast
        new_profile = ConfigProfile()
        new_profile.block_rules = [BlockRule(domains=["newdomain.org", "test.io"])]
        self.profile = new_profile
        self.server.notify_config_changed(new_profile)

        # Read broadcast event
        line2 = resp.fp.readline().decode("utf-8")
        self.assertTrue(line2.startswith("data:"))
        data2 = json.loads(line2[5:].strip())
        self.assertEqual(data2.get("type"), "config_updated")
        self.assertEqual(
            data2["config"]["block_rules"][0]["domains"],
            ["newdomain.org", "test.io"],
        )

        conn.close()


if __name__ == "__main__":
    unittest.main()
