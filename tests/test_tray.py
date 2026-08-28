"""Tests for GTFB system tray module and UI components."""

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
import pystray

from gtfb.app import build_parser
from gtfb.ui.tray import TrayApp, create_menu, generate_fallback_icon, load_tray_icon


class TestTrayIconGeneration(unittest.TestCase):
    """Test icon loading and dynamic fallback generation."""

    def test_generate_fallback_icon(self):
        icon = generate_fallback_icon(64, 64)
        self.assertIsInstance(icon, Image.Image)
        self.assertEqual(icon.size, (64, 64))
        self.assertEqual(icon.mode, "RGBA")

    def test_load_tray_icon_with_existing_asset(self):
        # Using package asset
        asset_path = Path(__file__).resolve().parent.parent / "src" / "gtfb" / "assets" / "icon.png"
        icon = load_tray_icon(asset_path)
        self.assertIsInstance(icon, Image.Image)
        self.assertEqual(icon.mode, "RGBA")

    def test_load_tray_icon_with_nonexistent_path_falls_back(self):
        # With an invalid path, it should still succeed by falling back
        icon = load_tray_icon("non_existent_directory_12345/non_existent_icon.png")
        self.assertIsInstance(icon, Image.Image)
        self.assertEqual(icon.mode, "RGBA")


class TestTrayMenuAndApp(unittest.TestCase):
    """Test TrayApp lifecycle and menu structure."""

    def test_menu_structure(self):
        mock_app = MagicMock(spec=TrayApp)
        mock_app.on_quit = MagicMock()

        menu = create_menu(mock_app)
        self.assertIsInstance(menu, pystray.Menu)
        
        items = list(menu.items)
        self.assertEqual(len(items), 2)

        # First item: 'GTFB — Idle' (disabled)
        idle_item = items[0]
        self.assertEqual(idle_item.text, "GTFB — Idle")
        self.assertFalse(idle_item.enabled)

        # Second item: 'Quit' (enabled, wired to on_quit)
        quit_item = items[1]
        self.assertEqual(quit_item.text, "Quit")
        self.assertTrue(quit_item.enabled)

    def test_tray_app_initialization(self):
        app = TrayApp()
        self.assertIsNotNone(app.icon)
        self.assertEqual(app.icon.title, "GTFB - Anti-Distraction Suite")
        self.assertEqual(app.icon.name, "gtfb")

    def test_tray_app_on_quit_calls_callback_and_stops_icon(self):
        quit_callback = MagicMock()
        app = TrayApp(on_quit=quit_callback)
        
        with patch.object(app.icon, "stop") as mock_stop:
            app.on_quit()
            quit_callback.assert_called_once()
            mock_stop.assert_called_once()

    def test_tray_app_stop_invokes_on_quit(self):
        quit_callback = MagicMock()
        app = TrayApp(on_quit=quit_callback)
        with patch.object(app, "on_quit") as mock_on_quit:
            app.stop()
            mock_on_quit.assert_called_once()


class TestAppParserCliFlag(unittest.TestCase):
    """Test updated argument parser including --cli flag."""

    def test_cli_flag_parsing(self):
        parser = build_parser()
        args = parser.parse_args(["--cli"])
        self.assertTrue(args.cli)

    def test_default_cli_flag_is_false(self):
        parser = build_parser()
        args = parser.parse_args([])
        self.assertFalse(args.cli)


if __name__ == "__main__":
    unittest.main()
