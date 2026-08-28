"""Unit tests for SettingsWindow UI component and BedtimeSection."""

import threading
import tkinter as tk
import unittest
from unittest.mock import MagicMock, patch

from gtfb.config.models import AppCloseSchedule, ConfigProfile
from gtfb.ui.settings_window import BedtimeSection, SettingsWindow


class TestBedtimeSection(unittest.TestCase):
    """Test suite for BedtimeSection widget form binding, formatting, and validation."""

    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_bedtime_section_default_pre_population(self):
        default_config = ConfigProfile()
        section = BedtimeSection(self.root, config=default_config)

        self.assertTrue(section.var_enabled.get())
        self.assertEqual(int(section.var_hour.get()), 22)
        self.assertEqual(int(section.var_minute.get()), 0)
        self.assertEqual(section.spin_hour.get(), "22")
        self.assertEqual(section.spin_minute.get(), "00")
        self.assertEqual(section.var_grace_period.get(), 15)

        data = section.validate_and_get()
        self.assertEqual(
            data,
            {
                "enabled": True,
                "target_hour": 22,
                "target_minute": 0,
                "grace_period_seconds": 15,
            },
        )

    def test_bedtime_section_custom_config_pre_population(self):
        custom_schedule = AppCloseSchedule(
            target_hour=8,
            target_minute=5,
            enabled=False,
            grace_period_seconds=30,
        )
        custom_config = ConfigProfile(app_close_schedule=custom_schedule)
        section = BedtimeSection(self.root, config=custom_config)

        self.assertFalse(section.var_enabled.get())
        self.assertEqual(int(section.var_hour.get()), 8)
        self.assertEqual(int(section.var_minute.get()), 5)
        self.assertEqual(section.spin_hour.get(), "08")
        self.assertEqual(section.spin_minute.get(), "05")
        self.assertEqual(section.var_grace_period.get(), 30)

        data = section.validate_and_get()
        self.assertEqual(
            data,
            {
                "enabled": False,
                "target_hour": 8,
                "target_minute": 5,
                "grace_period_seconds": 30,
            },
        )

    def test_bedtime_section_value_modification(self):
        section = BedtimeSection(self.root, config=ConfigProfile())
        section.var_enabled.set(False)
        section.var_hour.set(23)
        section.spin_hour.set("23")
        section.var_minute.set(45)
        section.spin_minute.set("45")
        section.var_grace_period.set(60)
        section.spin_grace.set("60")

        data = section.validate_and_get()
        self.assertEqual(
            data,
            {
                "enabled": False,
                "target_hour": 23,
                "target_minute": 45,
                "grace_period_seconds": 60,
            },
        )

    def test_validation_invalid_hour_bounds(self):
        section = BedtimeSection(self.root, config=ConfigProfile())

        # Test hour > 23
        section.spin_hour.set("24")
        section.var_hour.set(24)
        with self.assertRaises(ValueError) as ctx:
            section.validate_and_get()
        self.assertIn("Hour must be between 0 and 23", str(ctx.exception))

        # Test hour < 0
        section.spin_hour.set("-1")
        section.var_hour.set(-1)
        with self.assertRaises(ValueError) as ctx:
            section.validate_and_get()
        self.assertIn("Hour must be between 0 and 23", str(ctx.exception))

    def test_validation_invalid_minute_bounds(self):
        section = BedtimeSection(self.root, config=ConfigProfile())

        # Test minute > 59
        section.spin_minute.set("60")
        section.var_minute.set(60)
        with self.assertRaises(ValueError) as ctx:
            section.validate_and_get()
        self.assertIn("Minute must be between 0 and 59", str(ctx.exception))

        # Test minute < 0
        section.spin_minute.set("-5")
        section.var_minute.set(-5)
        with self.assertRaises(ValueError) as ctx:
            section.validate_and_get()
        self.assertIn("Minute must be between 0 and 59", str(ctx.exception))

    def test_validation_non_integer_inputs(self):
        section = BedtimeSection(self.root, config=ConfigProfile())

        section.spin_hour.set("invalid")
        with self.assertRaises(ValueError) as ctx:
            section.validate_and_get()
        self.assertIn("Hour must be an integer", str(ctx.exception))

        section.spin_hour.set("22")
        section.spin_minute.set("not_a_num")
        with self.assertRaises(ValueError) as ctx:
            section.validate_and_get()
        self.assertIn("Minute must be an integer", str(ctx.exception))

    def test_validation_invalid_grace_period(self):
        section = BedtimeSection(self.root, config=ConfigProfile())

        section.spin_grace.set("-10")
        with self.assertRaises(ValueError) as ctx:
            section.validate_and_get()
        self.assertIn("Grace period must be 0 or greater", str(ctx.exception))

        section.spin_grace.set("bad_val")
        with self.assertRaises(ValueError) as ctx:
            section.validate_and_get()
        self.assertIn("Grace period must be a non-negative integer", str(ctx.exception))


class TestSettingsWindow(unittest.TestCase):
    """Test suite for SettingsWindow lifecycle, singleton pattern, and events."""

    def setUp(self):
        # Ensure clean singleton state before each test
        SettingsWindow._instance = None

    def tearDown(self):
        # Clean up any lingering instance
        if SettingsWindow._instance:
            try:
                SettingsWindow._instance.close()
            except Exception:
                pass
        SettingsWindow._instance = None

    def test_settings_window_initialization(self):
        callback = MagicMock()
        custom_config = ConfigProfile(
            app_close_schedule=AppCloseSchedule(target_hour=21, target_minute=15)
        )
        window = SettingsWindow(config=custom_config, on_save_callback=callback)
        self.assertEqual(window.on_save_callback, callback)
        self.assertEqual(window.config, custom_config)
        self.assertIsNone(window.root)
        self.assertIsNone(SettingsWindow.get_instance())

    def test_settings_window_initialization_defaults_load_config(self):
        with patch("gtfb.ui.settings_window.load_config") as mock_load:
            mock_profile = ConfigProfile()
            mock_load.return_value = mock_profile
            window = SettingsWindow()
            mock_load.assert_called_once()
            self.assertEqual(window.config, mock_profile)

    def test_open_or_focus_creates_new_instance(self):
        with patch.object(SettingsWindow, "_create_window") as mock_create:
            instance = SettingsWindow.open_or_focus()
            self.assertIsNotNone(instance)
            self.assertEqual(SettingsWindow.get_instance(), instance)
            mock_create.assert_called_once()

    def test_open_or_focus_focuses_existing_instance(self):
        # Simulate an already running instance with existing root
        mock_root = MagicMock()
        mock_root.winfo_exists.return_value = True

        first_instance = SettingsWindow()
        first_instance.root = mock_root
        SettingsWindow._instance = first_instance

        with patch.object(first_instance, "_bring_to_front") as mock_bring_to_front, \
             patch.object(SettingsWindow, "_create_window") as mock_create:
            result = SettingsWindow.open_or_focus()

            self.assertEqual(result, first_instance)
            mock_bring_to_front.assert_called_once()
            mock_create.assert_not_called()

    def test_bring_to_front_lifts_and_focuses(self):
        mock_root = MagicMock()
        mock_root.winfo_exists.return_value = True

        window = SettingsWindow()
        window.root = mock_root

        window._bring_to_front()
        mock_root.deiconify.assert_called_once()
        mock_root.lift.assert_called_once()
        mock_root.focus_force.assert_called_once()

    def test_bring_to_front_noop_without_root(self):
        window = SettingsWindow()
        window.root = None
        # Should not raise exception
        window._bring_to_front()

    def test_on_close_destroys_root_and_clears_singleton(self):
        mock_root = MagicMock()
        mock_root.winfo_exists.return_value = True

        window = SettingsWindow()
        window.root = mock_root
        SettingsWindow._instance = window

        window._on_close()
        mock_root.destroy.assert_called_once()
        self.assertIsNone(window.root)
        self.assertIsNone(SettingsWindow.get_instance())

    def test_close_invokes_on_close(self):
        window = SettingsWindow()
        with patch.object(window, "_on_close") as mock_on_close:
            window.close()
            mock_on_close.assert_called_once()

    def test_center_window_eval_success(self):
        mock_root = MagicMock()
        window = SettingsWindow()
        window.root = mock_root

        window._center_window(480, 420)
        mock_root.eval.assert_called_once_with("tk::PlaceWindow . center")

    def test_center_window_eval_fallback(self):
        mock_root = MagicMock()
        mock_root.eval.side_effect = Exception("PlaceWindow not supported")
        mock_root.winfo_screenwidth.return_value = 1920
        mock_root.winfo_screenheight.return_value = 1080

        window = SettingsWindow()
        window.root = mock_root

        window._center_window(480, 420)
        mock_root.update_idletasks.assert_called_once()
        # x = (1920-480)/2 = 720, y = (1080-420)/2 = 330
        mock_root.geometry.assert_called_once_with("480x420+720+330")

    def test_set_window_icon_with_mocked_asset(self):
        mock_root = MagicMock()
        window = SettingsWindow()
        window.root = mock_root

        with patch("pathlib.Path.exists", return_value=True), \
             patch("tkinter.PhotoImage", return_value=MagicMock()) as mock_photo:
            window._set_window_icon()
            mock_photo.assert_called_once()
            mock_root.iconphoto.assert_called_once()

    def test_set_window_icon_fails_gracefully(self):
        mock_root = MagicMock()
        mock_root.iconphoto.side_effect = Exception("Icon error")
        window = SettingsWindow()
        window.root = mock_root

        with patch("pathlib.Path.exists", return_value=True), \
             patch("tkinter.PhotoImage", side_effect=Exception("Failed to read image")):
            # Should not raise exception
            window._set_window_icon()

    def test_open_or_focus_passes_custom_config(self):
        custom_config = ConfigProfile(
            app_close_schedule=AppCloseSchedule(target_hour=19, target_minute=45)
        )
        with patch.object(SettingsWindow, "_create_window"):
            instance = SettingsWindow.open_or_focus(config=custom_config)
            self.assertEqual(instance.config, custom_config)

    def test_create_window_creates_bedtime_section(self):
        custom_config = ConfigProfile(
            app_close_schedule=AppCloseSchedule(target_hour=23, target_minute=30)
        )
        window = SettingsWindow(config=custom_config)
        with patch.object(tk.Tk, "mainloop"):
            window._create_window()
            try:
                self.assertIsNotNone(window.bedtime_section)
                self.assertEqual(int(window.bedtime_section.var_hour.get()), 23)
                self.assertEqual(int(window.bedtime_section.var_minute.get()), 30)
            finally:
                window._on_close()


if __name__ == "__main__":
    unittest.main()

