"""Unit and integration tests for GET /health API endpoint."""

from datetime import datetime, timezone
import http.client
import json
import socket
import unittest
import urllib.error
import urllib.request

from gtfb.api import APIServer


def get_free_port() -> int:
    """Find and return an ephemeral open port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestAPIHealthEndpoint(unittest.TestCase):
    """Test GET /health liveness check endpoint and error responses."""

    def setUp(self):
        self.port = get_free_port()
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

    def tearDown(self):
        if self.server.is_running:
            self.server.stop()

    def test_get_health_success(self):
        url = f"http://127.0.0.1:{self.port}/health"
        req = urllib.request.Request(url, method="GET")

        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get("Content-Type"), "application/json")
            self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "*")
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Methods"),
                "GET, POST, OPTIONS",
            )
            self.assertEqual(
                response.headers.get("Access-Control-Allow-Headers"),
                "Content-Type, Authorization",
            )

            raw_body = response.read().decode("utf-8")
            data = json.loads(raw_body)

            self.assertEqual(data.get("status"), "ok")
            self.assertEqual(data.get("app"), "gtfb")
            self.assertEqual(data.get("version"), "1.0.0")

            # Validate timestamp parsing and UTC timezone
            ts_str = data.get("timestamp")
            self.assertIsNotNone(ts_str)
            parsed_ts = datetime.fromisoformat(ts_str)
            now = datetime.now(timezone.utc)
            self.assertLessEqual(abs((now - parsed_ts).total_seconds()), 5.0)

    def test_get_health_with_query_params(self):
        url = f"http://127.0.0.1:{self.port}/health?check=1&client=ext"
        req = urllib.request.Request(url, method="GET")

        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")

    def test_get_invalid_route_returns_404_json(self):
        url = f"http://127.0.0.1:{self.port}/invalid-endpoint"
        req = urllib.request.Request(url, method="GET")

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)

        err_response = ctx.exception
        self.assertEqual(err_response.code, 404)
        self.assertEqual(err_response.headers.get("Content-Type"), "application/json")
        self.assertEqual(err_response.headers.get("Access-Control-Allow-Origin"), "*")

        raw_body = err_response.read().decode("utf-8")
        data = json.loads(raw_body)
        self.assertEqual(data.get("error"), "Not Found")
        self.assertEqual(data.get("path"), "/invalid-endpoint")

    def test_http_client_connection(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/health")
            res = conn.getresponse()
            self.assertEqual(res.status, 200)
            self.assertEqual(res.getheader("Content-Type"), "application/json")
            data = json.loads(res.read().decode("utf-8"))
            self.assertEqual(data.get("status"), "ok")
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
