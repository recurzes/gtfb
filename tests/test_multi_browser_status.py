"""Unit tests for multi-browser telemetry tracking and status store."""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock

from gtfb.api.status_store import ExtensionStatusStore
from gtfb.ui.tray import TrayApp


class TestMultiBrowserStatus(unittest.TestCase):
    """Test suite verifying tracking of multiple browsers simultaneously."""

    def setUp(self) -> None:
        self.store = ExtensionStatusStore()

    def test_multi_browser_tracking(self) -> None:
        chrome_payload = {
            "browser": "chrome",
            "version": "1.0.0",
            "blocking_active": True,
            "rules_count": 5,
        }
        edge_payload = {
            "browser": "edge",
            "version": "1.0.0",
            "blocking_active": True,
            "rules_count": 5,
        }

        self.store.update_status(chrome_payload)
        self.store.update_status(edge_payload)

        self.assertTrue(self.store.is_connected(browser="chrome"))
        self.assertTrue(self.store.is_connected(browser="edge"))
        self.assertFalse(self.store.is_connected(browser="firefox"))

        active = self.store.get_connected_browsers(timeout_seconds=60.0)
        self.assertEqual(len(active), 2)
        browsers = [b["browser"] for b in active]
        self.assertIn("chrome", browsers)
        self.assertIn("edge", browsers)

    def test_tray_menu_multi_browser_status_text(self) -> None:
        app = TrayApp(status_store=self.store, api_server=MagicMock())

        # No connection
        self.assertEqual(app.get_extension_status_text(), "○ Extension: Not Connected")

        # Chrome connected
        self.store.update_status({"browser": "chrome", "blocking_active": True})
        self.assertEqual(app.get_extension_status_text(), "● Extension: Connected (Chrome — Active)")

        # Chrome + Edge connected
        self.store.update_status({"browser": "edge", "blocking_active": True})
        status_text = app.get_extension_status_text()
        self.assertIn("Chrome", status_text)
        self.assertIn("Edge", status_text)
        self.assertIn("Active", status_text)

        # Chrome + Brave connected
        self.store.clear()
        self.store.update_status({"browser": "chrome", "blocking_active": True})
        self.store.update_status({"browser": "brave", "blocking_active": True})
        status_text_brave = app.get_extension_status_text()
        self.assertEqual(status_text_brave, "● Extension: Connected (Chrome, Brave — Active)")


if __name__ == "__main__":
    unittest.main()

