"""Unit tests for SettingsWindow UI component."""

import threading
import unittest
from unittest.mock import MagicMock, patch

from gtfb.ui.settings_window import SettingsWindow


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
        window = SettingsWindow(on_save_callback=callback)
        self.assertEqual(window.on_save_callback, callback)
        self.assertIsNone(window.root)
        self.assertIsNone(SettingsWindow.get_instance())

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


if __name__ == "__main__":
    unittest.main()
