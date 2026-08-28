"""Unit and integration tests for GET /config API endpoint."""

import http.client
import json
import socket
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from gtfb.api import APIServer, GTFBRequestHandler
from gtfb.config.models import AppCloseSchedule, BlockRule, ConfigProfile, OverridePolicy
from gtfb.config.storage import save_config_atomic
from gtfb.ui.tray import TrayApp


def get_free_port() -> int:
    """Find and return an ephemeral open port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestAPIConfigEndpoint(unittest.TestCase):
    """Test GET /config endpoint routing, serialization, and CORS headers."""

    def setUp(self):
        self.port = get_free_port()
        self.server: APIServer | None = None

    def tearDown(self):
        if self.server and self.server.is_running:
            self.server.stop()

    def test_get_config_default_fallback(self):
        """Test GET /config fallback when no provider is passed."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/config"
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

            self.assertIn("version", data)
            self.assertIn("profile_name", data)
            self.assertIn("app_close_schedule", data)
            self.assertIn("block_rules", data)
            self.assertIn("override_policy", data)
            self.assertIsInstance(data["block_rules"], list)
            self.assertIsInstance(data["app_close_schedule"], dict)

    def test_get_config_with_custom_provider_profile(self):
        """Test GET /config with custom ConfigProfile provider."""
        test_profile = ConfigProfile(
            profile_name="FocusMode",
            app_close_schedule=AppCloseSchedule(
                target_hour=23,
                target_minute=30,
                enabled=True,
                grace_period_seconds=20,
                force_kill_after_grace=True,
            ),
            block_rules=[
                BlockRule(
                    domains=["reddit.com", "youtube.com", "customsite.org"],
                    trigger_type="recurring",
                    start_hour=23,
                    start_minute=30,
                    end_hour=7,
                    end_minute=0,
                    active=True,
                )
            ],
            override_policy=OverridePolicy(
                friction_type="typing",
                cooldown_minutes=15,
            ),
        )

        self.server = APIServer(
            host="127.0.0.1",
            port=self.port,
            config_provider=lambda: test_profile,
        )
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/config"
        req = urllib.request.Request(url, method="GET")

        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))

            self.assertEqual(data["profile_name"], "FocusMode")
            self.assertEqual(data["app_close_schedule"]["target_hour"], 23)
            self.assertEqual(data["app_close_schedule"]["target_minute"], 30)
            self.assertEqual(data["app_close_schedule"]["grace_period_seconds"], 20)
            self.assertTrue(data["app_close_schedule"]["enabled"])
            self.assertEqual(len(data["block_rules"]), 1)
            self.assertEqual(
                data["block_rules"][0]["domains"],
                ["reddit.com", "youtube.com", "customsite.org"],
            )
            self.assertEqual(data["override_policy"]["friction_type"], "typing")
            self.assertEqual(data["override_policy"]["cooldown_minutes"], 15)

    def test_get_config_with_dict_provider(self):
        """Test GET /config when config_provider returns a plain dict."""
        raw_dict = {
            "version": 1,
            "profile_name": "DictProfile",
            "app_close_schedule": {"target_hour": 21, "target_minute": 15, "enabled": True},
            "block_rules": [],
            "override_policy": {"friction_type": "none", "cooldown_minutes": 0},
        }

        self.server = APIServer(
            host="127.0.0.1",
            port=self.port,
            config_provider=lambda: raw_dict,
        )
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/config"
        req = urllib.request.Request(url, method="GET")

        with urllib.request.urlopen(req, timeout=5) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertEqual(data["profile_name"], "DictProfile")
            self.assertEqual(data["app_close_schedule"]["target_hour"], 21)

    def test_get_config_dynamic_mutation(self):
        """Test that updates to the config profile are immediately reflected in subsequent GET calls."""
        live_profile = ConfigProfile(
            profile_name="DynamicProfile",
            block_rules=[BlockRule(domains=["initial.com"])],
        )

        self.server = APIServer(
            host="127.0.0.1",
            port=self.port,
            config_provider=lambda: live_profile,
        )
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/config"

        # Request 1
        with urllib.request.urlopen(url, timeout=5) as res1:
            data1 = json.loads(res1.read().decode("utf-8"))
            self.assertEqual(data1["block_rules"][0]["domains"], ["initial.com"])

        # Mutate live config
        live_profile.block_rules[0].domains = ["initial.com", "updated.org", "news.ycombinator.com"]
        live_profile.app_close_schedule.target_hour = 1

        # Request 2
        with urllib.request.urlopen(url, timeout=5) as res2:
            data2 = json.loads(res2.read().decode("utf-8"))
            self.assertEqual(
                data2["block_rules"][0]["domains"],
                ["initial.com", "updated.org", "news.ycombinator.com"],
            )
            self.assertEqual(data2["app_close_schedule"]["target_hour"], 1)

    def test_get_config_with_query_params(self):
        """Test GET /config with query parameters attached."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/config?client=ext&v=1.2.3"
        with urllib.request.urlopen(url, timeout=5) as response:
            self.assertEqual(response.status, 200)
            data = json.loads(response.read().decode("utf-8"))
            self.assertIn("version", data)

    def test_options_preflight_for_config(self):
        """Test OPTIONS /config returns 204 with CORS headers."""
        self.server = APIServer(host="127.0.0.1", port=self.port)
        self.server.start()

        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("OPTIONS", "/config")
            res = conn.getresponse()
            self.assertEqual(res.status, 204)
            self.assertEqual(res.getheader("Access-Control-Allow-Origin"), "*")
            self.assertEqual(res.getheader("Access-Control-Allow-Methods"), "GET, POST, OPTIONS")
        finally:
            conn.close()

    def test_get_config_error_handling(self):
        """Test error handling when provider raises an exception returns 500 JSON."""
        def bad_provider():
            raise RuntimeError("Database/Disk read failure simulated")

        self.server = APIServer(
            host="127.0.0.1",
            port=self.port,
            config_provider=bad_provider,
        )
        self.server.start()

        url = f"http://127.0.0.1:{self.port}/config"
        req = urllib.request.Request(url, method="GET")

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)

        err_res = ctx.exception
        self.assertEqual(err_res.code, 500)
        self.assertEqual(err_res.headers.get("Content-Type"), "application/json")
        self.assertEqual(err_res.headers.get("Access-Control-Allow-Origin"), "*")

        data = json.loads(err_res.read().decode("utf-8"))
        self.assertEqual(data.get("error"), "Internal Server Error")
        self.assertIn("Database/Disk read failure simulated", data.get("message", ""))


class TestTrayAppConfigProviderIntegration(unittest.TestCase):
    """Test TrayApp integration with APIServer config provider."""

    @patch("pystray.Icon")
    def test_tray_app_passes_config_provider_to_api_server(self, mock_icon):
        initial_cfg = ConfigProfile(profile_name="TrayInitial")
        app = TrayApp(config=initial_cfg)

        self.assertEqual(app.get_active_config(), initial_cfg)
        self.assertEqual(app.api_server.config_provider, app.get_active_config)

        # Simulate settings saved
        updated_cfg = ConfigProfile(profile_name="TrayUpdated")
        app.on_settings_saved(updated_cfg)

        self.assertEqual(app.get_active_config(), updated_cfg)
        self.assertEqual(app.api_server.config_provider(), updated_cfg)


if __name__ == "__main__":
    unittest.main()
