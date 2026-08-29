"""Unit and integration tests for POST /status API endpoint and ExtensionStatusStore."""

from datetime import datetime, timedelta, timezone
import http.client
import json
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from gtfb.api import APIServer, ExtensionStatusStore, GTFBRequestHandler
from gtfb.ui.tray import TrayApp


def get_free_port() -> int:
    """Find and return an ephemeral open port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestExtensionStatusStore(unittest.TestCase):
    """Unit tests for ExtensionStatusStore thread-safe operations."""

    def test_initial_state(self):
        store = ExtensionStatusStore()
        self.assertIsNone(store.get_status())
        self.assertFalse(store.is_connected())

    def test_update_status_and_get_status(self):
        store = ExtensionStatusStore()
        payload = {
            "browser": "chrome",
            "version": "1.0.0",
            "blocking_active": True,
            "rules_count": 5,
        }
        store.update_status(payload)

        status = store.get_status()
        self.assertIsNotNone(status)
        self.assertEqual(status["browser"], "chrome")
        self.assertEqual(status["version"], "1.0.0")
        self.assertTrue(status["blocking_active"])
        self.assertEqual(status["rules_count"], 5)
        self.assertIn("_received_at", status)

        # Verify timestamp is valid ISO format
        received_at = datetime.fromisoformat(status["_received_at"])
        self.assertIsNotNone(received_at)

    def test_is_connected_timeout(self):
        store = ExtensionStatusStore()
        self.assertFalse(store.is_connected(timeout_seconds=60))

        store.update_status({"browser": "firefox"})
        self.assertTrue(store.is_connected(timeout_seconds=60))

        # Simulate past timestamp
        with store._lock:
            store._last_received_at = datetime.now(timezone.utc) - timedelta(seconds=70)

        self.assertFalse(store.is_connected(timeout_seconds=60))
        self.assertTrue(store.is_connected(timeout_seconds=80))

    def test_clear(self):
        store = ExtensionStatusStore()
        store.update_status({"browser": "edge", "blocking_active": False})
        self.assertIsNotNone(store.get_status())
        self.assertTrue(store.is_connected())

        store.clear()
        self.assertIsNone(store.get_status())
        self.assertFalse(store.is_connected())

    def test_concurrent_updates_and_reads(self):
        store = ExtensionStatusStore()
        threads = []
        errors = []

        def worker(idx: int):
            try:
                for i in range(50):
                    store.update_status({"thread": idx, "iteration": i})
                    s = store.get_status()
                    if s is not None:
                        self.assertIn("_received_at", s)
                    _ = store.is_connected()
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        for i in range(8):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=5.0)

        self.assertEqual(errors, [])
        self.assertIsNotNone(store.get_status())
        self.assertTrue(store.is_connected())


class TestAPIStatusEndpoint(unittest.TestCase):
    """Integration tests for POST /status endpoint."""

    def setUp(self):
        self.port = get_free_port()
        self.server: APIServer | None = None

    def tearDown(self):
        if self.server and self.server.is_running:
            self.server.stop()

    def test_post_status_valid_payload(self):
        """Test sending a valid POST payload updates store and returns 200 JSON."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        payload = {
            "browser": "chrome",
            "version": "1.0.0",
            "blocking_active": True,
            "rules_count": 7,
            "timestamp": "2026-08-28T12:05:00Z",
        }
        body_bytes = json.dumps(payload).encode("utf-8")

        url = f"http://127.0.0.1:{self.port}/status"
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Content-Type"), "application/json")
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Methods"),
                "GET, POST, OPTIONS",
            )

            res_body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(res_body, {"status": "received"})

        # Inspect server status_store
        stored = self.server.status_store.get_status()
        self.assertIsNotNone(stored)
        self.assertEqual(stored["browser"], "chrome")
        self.assertEqual(stored["version"], "1.0.0")
        self.assertTrue(stored["blocking_active"])
        self.assertEqual(stored["rules_count"], 7)
        self.assertEqual(stored["timestamp"], "2026-08-28T12:05:00Z")
        self.assertIn("_received_at", stored)
        self.assertTrue(self.server.status_store.is_connected(timeout_seconds=60))

    def test_post_status_multiple_updates(self):
        """Test consecutive POST updates reflect latest status in store."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/status"

        # Update 1
        pulse1 = {"browser": "firefox", "blocking_active": False, "rules_count": 2}
        req1 = urllib.request.Request(
            url,
            data=json.dumps(pulse1).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req1, timeout=5) as res1:
            self.assertEqual(res1.status, 200)

        s1 = self.server.status_store.get_status()
        self.assertEqual(s1["browser"], "firefox")
        self.assertFalse(s1["blocking_active"])
        self.assertEqual(s1["rules_count"], 2)

        # Update 2
        pulse2 = {"browser": "firefox", "blocking_active": True, "rules_count": 10}
        req2 = urllib.request.Request(
            url,
            data=json.dumps(pulse2).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5) as res2:
            self.assertEqual(res2.status, 200)

        s2 = self.server.status_store.get_status()
        self.assertEqual(s2["browser"], "firefox")
        self.assertTrue(s2["blocking_active"])
        self.assertEqual(s2["rules_count"], 10)

    def test_post_status_custom_store_instance(self):
        """Test APIServer uses provided ExtensionStatusStore instance."""
        custom_store = ExtensionStatusStore()
        self.server = APIServer(
            host="127.0.0.1", port=self.port, status_store=custom_store
        )
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/status"
        payload = {"browser": "brave", "blocking_active": True}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)

        self.assertIs(self.server.status_store, custom_store)
        self.assertEqual(custom_store.get_status()["browser"], "brave")

    def test_post_status_query_params(self):
        """Test POST /status with URL query parameters."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/status?client=extension&v=2.0"
        payload = {"browser": "edge", "blocking_active": True}
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data, {"status": "received"})

    def test_options_preflight_for_status(self):
        """Test OPTIONS /status returns 204 with CORS headers."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("OPTIONS", "/status")
            res = conn.getresponse()
            self.assertEqual(res.status, 204)
            self.assertEqual(res.getheader("Access-Control-Allow-Origin"), "*")
            self.assertEqual(
                res.getheader("Access-Control-Allow-Methods"),
                "GET, POST, OPTIONS",
            )
            self.assertEqual(
                res.getheader("Access-Control-Allow-Headers"),
                "Content-Type, Authorization",
            )
        finally:
            conn.close()

    def test_post_status_malformed_json_returns_400(self):
        """Test sending malformed JSON returns HTTP 400 Bad Request."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/status"
        bad_json = b"{\"browser\": \"chrome\", unclosed"

        req = urllib.request.Request(
            url,
            data=bad_json,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)

        self.assertEqual(ctx.exception.code, 400)
        data = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(data.get("error"), "Invalid JSON")

    def test_post_status_non_object_json_returns_400(self):
        """Test sending non-object JSON (array, number, string) returns HTTP 400."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/status"

        for non_object in [b"[1, 2, 3]", b"\"just a string\"", b"12345", b"true"]:
            req = urllib.request.Request(
                url,
                data=non_object,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=5)

            self.assertEqual(ctx.exception.code, 400)
            data = json.loads(ctx.exception.read().decode("utf-8"))
            self.assertIn("error", data)

    def test_post_status_payload_too_large_returns_413(self):
        """Test sending payload > 64KB returns HTTP 413 Payload Too Large."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/status"
        large_data = {"browser": "chrome", "huge_field": "X" * 70000}
        large_bytes = json.dumps(large_data).encode("utf-8")
        self.assertGreater(len(large_bytes), 65536)

        req = urllib.request.Request(
            url,
            data=large_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)

        self.assertEqual(ctx.exception.code, 413)
        data = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(data.get("error"), "Payload too large")

    def test_post_unknown_endpoint_returns_404(self):
        """Test sending POST to unrecognized path returns HTTP 404 Not Found."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/nonexistent"
        req = urllib.request.Request(
            url,
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)

        self.assertEqual(ctx.exception.code, 404)
        data = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(data.get("error"), "Not Found")
        self.assertEqual(data.get("path"), "/nonexistent")


class TestTrayAppStatusStoreIntegration(unittest.TestCase):
    """Integration tests for TrayApp and status_store."""

    @patch("pystray.Icon")
    def test_tray_app_initializes_and_shares_status_store(self, mock_icon):
        custom_store = ExtensionStatusStore()
        app = TrayApp(status_store=custom_store)

        self.assertIs(app.status_store, custom_store)
        self.assertIs(app.api_server.status_store, custom_store)

    @patch("pystray.Icon")
    def test_tray_app_reflects_post_status_endpoint_updates(self, mock_icon):
        port = get_free_port()
        custom_store = ExtensionStatusStore()
        server = APIServer(host="127.0.0.1", port=port, status_store=custom_store)
        app = TrayApp(api_server=server, status_store=custom_store)

        self.assertEqual(app.get_extension_status_text(), "○ Extension: Not Connected")

        try:
            server.start()

            # 1. Send active blocking heartbeat
            payload1 = {
                "browser": "chrome",
                "version": "1.0.0",
                "blocking_active": True,
                "rules_count": 8,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            req1 = urllib.request.Request(
                f"http://127.0.0.1:{port}/status",
                data=json.dumps(payload1).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req1, timeout=5) as res1:
                self.assertEqual(res1.status, 200)

            self.assertEqual(
                app.get_extension_status_text(),
                "● Extension: Connected (Chrome — Active)",
            )

            # 2. Send inactive blocking heartbeat (e.g. user toggled off)
            payload2 = {
                "browser": "chrome",
                "version": "1.0.0",
                "blocking_active": False,
                "rules_count": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            req2 = urllib.request.Request(
                f"http://127.0.0.1:{port}/status",
                data=json.dumps(payload2).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req2, timeout=5) as res2:
                self.assertEqual(res2.status, 200)

            self.assertEqual(
                app.get_extension_status_text(),
                "● Extension: Connected (Chrome — Inactive)",
            )

            # 3. Simulate heartbeat timeout (> 90s)
            custom_store._last_received_at = datetime.now(timezone.utc) - timedelta(seconds=95)
            self.assertEqual(
                app.get_extension_status_text(),
                "○ Extension: Not Connected",
            )

            # 4. Resume heartbeat
            with urllib.request.urlopen(req1, timeout=5) as res3:
                self.assertEqual(res3.status, 200)

            self.assertEqual(
                app.get_extension_status_text(),
                "● Extension: Connected (Chrome — Active)",
            )
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
