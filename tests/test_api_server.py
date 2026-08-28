"""Unit and integration tests for GTFB local API server and request handler."""

import http.client
import logging
import socket
import unittest
from unittest.mock import MagicMock, patch
import urllib.request

from gtfb.api import APIServer, DEFAULT_PORT, GTFBRequestHandler
from gtfb.ui.tray import TrayApp


def get_free_port() -> int:
    """Find and return an ephemeral open port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestAPIServerInitialization(unittest.TestCase):
    """Test APIServer creation, configuration, and security validations."""

    def test_default_initialization(self):
        server = APIServer()
        self.assertEqual(server.host, "127.0.0.1")
        self.assertEqual(server.port, DEFAULT_PORT)
        self.assertEqual(server.handler_cls, GTFBRequestHandler)
        self.assertFalse(server.is_running)
        self.assertIsNone(server.server)

    def test_valid_loopback_hosts(self):
        # 127.0.0.1
        s1 = APIServer(host="127.0.0.1")
        self.assertEqual(s1.host, "127.0.0.1")

        # localhost
        s2 = APIServer(host="localhost")
        self.assertEqual(s2.host, "localhost")

        # IPv6 loopback
        s3 = APIServer(host="::1")
        self.assertEqual(s3.host, "::1")

    def test_security_violation_on_non_loopback_hosts(self):
        invalid_hosts = ["0.0.0.0", "192.168.1.50", "8.8.8.8", "example.com"]
        for host in invalid_hosts:
            with self.subTest(host=host):
                with self.assertRaises(ValueError) as ctx:
                    APIServer(host=host)
                self.assertIn("Security violation", str(ctx.exception))


class TestAPIServerLifecycleAndCORS(unittest.TestCase):
    """Test starting, stopping, and handling OPTIONS CORS preflight requests."""

    def setUp(self):
        self.port = get_free_port()
        self.server = APIServer(host="127.0.0.1", port=self.port)

    def tearDown(self):
        if self.server.is_running:
            self.server.stop()

    def test_server_start_and_stop_lifecycle(self):
        self.assertFalse(self.server.is_running)
        self.server.start()
        self.assertTrue(self.server.is_running)

        # Calling start again while running should be a no-op
        self.server.start()
        self.assertTrue(self.server.is_running)

        self.server.stop()
        self.assertFalse(self.server.is_running)
        self.assertIsNone(self.server.server)

    def test_options_request_returns_204_with_cors_headers(self):
        self.server.start()

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("OPTIONS", "/health")
            response = conn.getresponse()

            self.assertEqual(response.status, 204)
            headers = dict(response.getheaders())
            self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
            self.assertEqual(headers.get("Access-Control-Allow-Methods"), "GET, POST, OPTIONS")
            self.assertEqual(headers.get("Access-Control-Allow-Headers"), "Content-Type, Authorization")
        finally:
            conn.close()

    def test_handler_log_message_routes_to_debug_logger(self):
        handler = GTFBRequestHandler.__new__(GTFBRequestHandler)
        handler.client_address = ("127.0.0.1", 12345)

        with patch("gtfb.api.handler.logger.debug") as mock_debug:
            handler.log_message("Test message %s %d", "arg1", 42)
            mock_debug.assert_called_once_with("API %s - %s", "127.0.0.1", "Test message arg1 42")


class TestTrayAppAPIServerIntegration(unittest.TestCase):
    """Test that TrayApp manages APIServer lifecycle."""

    @patch("pystray.Icon")
    def test_tray_app_initializes_api_server_by_default(self, mock_icon):
        app = TrayApp()
        self.assertIsNotNone(app.api_server)
        self.assertIsInstance(app.api_server, APIServer)

    @patch("pystray.Icon")
    def test_tray_app_accepts_custom_api_server(self, mock_icon):
        mock_api = MagicMock(spec=APIServer)
        app = TrayApp(api_server=mock_api)
        self.assertEqual(app.api_server, mock_api)

    @patch("pystray.Icon")
    def test_tray_app_run_starts_api_server(self, mock_icon):
        mock_api = MagicMock(spec=APIServer)
        mock_scheduler = MagicMock()
        app = TrayApp(scheduler=mock_scheduler, api_server=mock_api)

        with patch.object(app, "_start_status_updater"):
            app.run()
            mock_api.start.assert_called_once()

    @patch("pystray.Icon")
    def test_tray_app_on_quit_stops_api_server(self, mock_icon):
        mock_api = MagicMock(spec=APIServer)
        mock_scheduler = MagicMock()
        app = TrayApp(scheduler=mock_scheduler, api_server=mock_api)

        with patch.object(app, "_stop_status_updater"):
            app.on_quit()
            mock_api.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
