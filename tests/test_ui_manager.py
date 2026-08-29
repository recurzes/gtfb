"""Tests for thread-safe UIManager and Tkinter event loop coordination."""

import time
import unittest
from unittest.mock import MagicMock, patch

from gtfb.config.models import ConfigProfile
from gtfb.ui.manager import UIManager


class TestUIManager(unittest.TestCase):
    """Test suite verifying UIManager lifecycle and thread-safety."""

    def tearDown(self) -> None:
        mgr = UIManager._instance
        if mgr is not None:
            mgr.close_all_windows()


    def test_singleton_instance(self) -> None:
        mgr1 = UIManager.get_instance()
        mgr2 = UIManager.get_instance()
        self.assertIs(mgr1, mgr2)

    def test_run_on_ui_thread_synchronous(self) -> None:
        mgr = UIManager.get_instance()
        result = mgr.run_on_ui_thread(lambda x, y: x + y, 10, 20)
        self.assertEqual(result, 30)

    def test_post_to_ui_thread_asynchronous(self) -> None:
        mgr = UIManager.get_instance()
        executed = []

        def task():
            executed.append(True)

        mgr.post_to_ui_thread(task)
        time.sleep(0.2)
        self.assertEqual(executed, [True])

    def test_open_settings(self) -> None:
        mgr = UIManager.get_instance()
        mgr.open_settings(config=ConfigProfile())
        time.sleep(0.1)
        self.assertIsNotNone(mgr._settings_window)
        mgr.close_all_windows()

    def test_open_extension_setup(self) -> None:
        mgr = UIManager.get_instance()
        mgr.open_extension_setup()
        time.sleep(0.1)
        self.assertIsNotNone(mgr._extension_setup_window)
        mgr.close_all_windows()

    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_prompt_extension_consent(self, mock_askyesno: MagicMock) -> None:
        mgr = UIManager.get_instance()
        res = mgr.prompt_extension_consent()
        self.assertTrue(res)
        self.assertTrue(mock_askyesno.called)

    def test_close_all_windows(self) -> None:
        mgr = UIManager.get_instance()
        mgr.open_settings()
        self.assertTrue(mgr.is_running)
        mgr.open_extension_setup()
        mgr.close_all_windows()
        self.assertIsNone(mgr._settings_window)
        self.assertIsNone(mgr._extension_setup_window)



if __name__ == "__main__":
    unittest.main()

