"""Tests for GTFB system tray module and UI components."""

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from PIL import Image
import pystray

from gtfb.app import build_parser
from gtfb.config.models import ConfigProfile
from gtfb.ui.settings_window import SettingsWindow
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
        mock_scheduler = MagicMock()
        mock_scheduler.is_running.return_value = False
        app = TrayApp(scheduler=mock_scheduler)

        menu = create_menu(app)
        self.assertIsInstance(menu, pystray.Menu)

        items = list(menu.items)
        # Expected: Status, Separator, Settings..., Start Scheduler, Stop Scheduler, Separator, Quit
        self.assertEqual(len(items), 7)

        # Item 0: Status label (disabled)
        status_item = items[0]
        self.assertEqual(str(status_item), "Status: Stopped")
        self.assertFalse(status_item.enabled)

        # Item 1: Separator
        self.assertEqual(str(items[1]), "- - - -")

        # Item 2: Settings...
        settings_item = items[2]
        self.assertEqual(settings_item.text, "Settings...")
        self.assertTrue(settings_item.enabled)
        self.assertEqual(settings_item._action, app.on_open_settings)

        # Item 3: Start Scheduler
        start_item = items[3]
        self.assertEqual(start_item.text, "Start Scheduler")
        self.assertTrue(start_item.visible)
        self.assertEqual(start_item._action, app.on_start)

        # Item 4: Stop Scheduler
        stop_item = items[4]
        self.assertEqual(stop_item.text, "Stop Scheduler")
        self.assertFalse(stop_item.visible)
        self.assertEqual(stop_item._action, app.on_stop)

        # Item 5: Separator
        self.assertEqual(str(items[5]), "- - - -")

        # Item 6: Quit
        quit_item = items[6]
        self.assertEqual(quit_item.text, "Quit")
        self.assertTrue(quit_item.enabled)
        self.assertEqual(quit_item._action, app.on_quit)

    def test_menu_dynamic_state_when_running(self):
        mock_scheduler = MagicMock()
        mock_scheduler.is_running.return_value = True
        app = TrayApp(scheduler=mock_scheduler)

        menu = app.build_menu()
        items = list(menu.items)

        # When running: Status is 'Status: Running', Start is hidden, Stop is visible
        status_item = items[0]
        self.assertEqual(str(status_item), "Status: Running")

        settings_item = items[2]
        self.assertEqual(settings_item.text, "Settings...")
        self.assertTrue(settings_item.enabled)

        start_item = items[3]
        self.assertFalse(start_item.visible)

        stop_item = items[4]
        self.assertTrue(stop_item.visible)

    def test_on_open_settings_starts_thread(self):
        app = TrayApp()
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            app.on_open_settings()

            mock_thread_cls.assert_called_once()
            _, kwargs = mock_thread_cls.call_args
            self.assertTrue(kwargs.get("daemon"))
            mock_thread.start.assert_called_once()

    def test_is_scheduler_running_and_stopped(self):
        mock_scheduler = MagicMock()
        app = TrayApp(scheduler=mock_scheduler)

        mock_scheduler.is_running.return_value = True
        self.assertTrue(app.is_scheduler_running())
        self.assertFalse(app.is_scheduler_stopped())

        mock_scheduler.is_running.return_value = False
        self.assertFalse(app.is_scheduler_running())
        self.assertTrue(app.is_scheduler_stopped())

        app.scheduler = None
        self.assertFalse(app.is_scheduler_running())
        self.assertTrue(app.is_scheduler_stopped())

    def test_on_start_invokes_scheduler_start_and_updates_menu(self):
        mock_scheduler = MagicMock()
        mock_scheduler.state = "COUNTING_DOWN"
        mock_scheduler.get_status_detail.return_value = "Bedtime at 22:00 — 30m remaining"
        app = TrayApp(scheduler=mock_scheduler)
        app.icon.update_menu = MagicMock()

        app.on_start()
        mock_scheduler.start.assert_called_once()
        self.assertEqual(app.current_state, "COUNTING_DOWN")
        self.assertEqual(app.icon.title, "GTFB: Counting Down (Bedtime at 22:00 — 30m remaining)")
        app.icon.update_menu.assert_called_once()

    def test_on_stop_invokes_scheduler_stop_and_updates_menu(self):
        mock_scheduler = MagicMock()
        mock_scheduler.state = "STOPPED"
        mock_scheduler.get_status_detail.return_value = ""
        app = TrayApp(scheduler=mock_scheduler)
        app.icon.update_menu = MagicMock()

        app.on_stop()
        mock_scheduler.stop.assert_called_once()
        self.assertEqual(app.current_state, "STOPPED")
        self.assertEqual(app.icon.title, "GTFB: Stopped")
        app.icon.update_menu.assert_called_once()


    def test_tray_app_initialization(self):
        app = TrayApp()
        self.assertIsNotNone(app.icon)
        self.assertIsNotNone(app.scheduler)
        self.assertEqual(app.icon.title, "GTFB: Stopped")
        self.assertEqual(app.icon.name, "gtfb")

    def test_tray_app_initialization_with_custom_scheduler(self):
        mock_scheduler = MagicMock()
        mock_scheduler.state = "STOPPED"
        mock_scheduler.get_status_detail.return_value = ""
        app = TrayApp(scheduler=mock_scheduler)
        self.assertEqual(app.scheduler, mock_scheduler)

    def test_update_tray_state_changes_icon_and_title(self):
        app = TrayApp()
        
        # Test counting down with detail
        app.update_tray_state("COUNTING_DOWN", "Bedtime at 22:00 — 42m remaining")
        self.assertEqual(app.current_state, "COUNTING_DOWN")
        self.assertEqual(app.icon.title, "GTFB: Counting Down (Bedtime at 22:00 — 42m remaining)")
        self.assertIsInstance(app.icon.icon, Image.Image)

        # Test stopped without detail
        app.update_tray_state("STOPPED", "")
        self.assertEqual(app.current_state, "STOPPED")
        self.assertEqual(app.icon.title, "GTFB: Stopped")

        # Test enforcing
        app.update_tray_state("ENFORCING", "Bedtime enforcement active")
        self.assertEqual(app.current_state, "ENFORCING")
        self.assertEqual(app.icon.title, "GTFB: Enforcing (Bedtime enforcement active)")

    def test_status_updater_thread_lifecycle(self):
        app = TrayApp()
        self.assertIsNone(app._updater_thread)

        app._start_status_updater()
        self.assertIsNotNone(app._updater_thread)
        self.assertTrue(app._updater_thread.is_alive())

        # Idempotent start
        thread_ref = app._updater_thread
        app._start_status_updater()
        self.assertEqual(app._updater_thread, thread_ref)

        app._stop_status_updater()
        self.assertFalse(app._updater_thread.is_alive())

    def test_tray_app_run_starts_scheduler_and_status_updater(self):
        mock_scheduler = MagicMock()
        mock_scheduler.state = "COUNTING_DOWN"
        mock_scheduler.get_status_detail.return_value = "Bedtime at 22:00 — 45m remaining"
        mock_api = MagicMock()
        app = TrayApp(scheduler=mock_scheduler, api_server=mock_api)
        with patch.object(app.icon, "run") as mock_run, \
             patch.object(app, "_start_status_updater") as mock_updater:
            app.run()
            mock_scheduler.start.assert_called_once()
            mock_api.start.assert_called_once()
            mock_updater.assert_called_once()
            mock_run.assert_called_once()

    def test_tray_app_on_quit_calls_callback_and_stops_icon(self):
        quit_callback = MagicMock()
        mock_scheduler = MagicMock()
        mock_api = MagicMock()
        app = TrayApp(scheduler=mock_scheduler, on_quit=quit_callback, api_server=mock_api)

        with patch.object(app.icon, "stop") as mock_stop:
            app.on_quit()
            mock_scheduler.stop.assert_called_once()
            mock_api.stop.assert_called_once()
            quit_callback.assert_called_once()
            mock_stop.assert_called_once()

    def test_tray_app_on_quit_closes_active_settings_window(self):
        mock_settings = MagicMock()
        with patch("gtfb.ui.settings_window.SettingsWindow.get_instance", return_value=mock_settings), \
             patch.object(TrayApp, "_stop_status_updater"):
            app = TrayApp()
            with patch.object(app.icon, "stop"):
                app.on_quit()
                mock_settings.close.assert_called_once()

    def test_tray_app_on_open_settings_spawns_thread_with_save_callback(self):
        app = TrayApp()
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            app.on_open_settings()

            mock_thread_cls.assert_called_once_with(
                target=SettingsWindow.open_or_focus,
                kwargs={"on_save_callback": app.on_settings_saved},
                name="GTFBSettingsWindowThread",
                daemon=True,
            )
            mock_thread.start.assert_called_once()

    def test_tray_app_on_settings_saved_updates_scheduler_and_tray(self):
        mock_scheduler = MagicMock()
        app = TrayApp(scheduler=mock_scheduler)

        new_config = ConfigProfile()
        with patch.object(app, "update_tray_state") as mock_update_tray:
            app.on_settings_saved(new_config)

            mock_scheduler.update_config.assert_called_once_with(new_config)
            mock_update_tray.assert_called_once()




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
