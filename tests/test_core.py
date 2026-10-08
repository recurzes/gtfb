"""Tests for GTFB core modules and packaging structure."""

import os
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import psutil

import gtfb
from gtfb.app import build_parser
from gtfb.config import (
    DEFAULT_GRACE_PERIOD_SECONDS,
    DEFAULT_SHUTDOWN_DELAY_SECONDS,
    DEFAULT_TARGET_HOUR,
    DEFAULT_TARGET_MINUTE,
)
from gtfb.core.closer import get_running_gui_apps
from gtfb.core.platform_utils import CURRENT_OS, is_gui_application
from gtfb.core.scheduler import calculate_delay


class TestPackageStructure(unittest.TestCase):
    """Test package versioning and modular imports."""

    def test_version_defined(self):
        self.assertTrue(hasattr(gtfb, "__version__"))
        self.assertIsInstance(gtfb.__version__, str)
        self.assertEqual(gtfb.__version__, "0.1.0")

    def test_config_defaults(self):
        self.assertEqual(DEFAULT_TARGET_HOUR, 22)
        self.assertEqual(DEFAULT_TARGET_MINUTE, 0)
        self.assertGreater(DEFAULT_GRACE_PERIOD_SECONDS, 0)
        self.assertGreater(DEFAULT_SHUTDOWN_DELAY_SECONDS, 0)

    def test_closer_dry_run_returns_list(self):
        from gtfb.core.closer import close_gui_apps
        apps = close_gui_apps(dry_run=True)
        self.assertIsInstance(apps, list)



class TestSchedulerLogic(unittest.TestCase):
    """Test scheduler delay calculation."""

    def test_calculate_delay_future_today(self):
        fixed_now = datetime(2026, 8, 29, 14, 0, 0)
        future_time = fixed_now + timedelta(hours=2)
        with unittest.mock.patch("gtfb.core.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            delay, target_dt = calculate_delay(future_time.hour, future_time.minute)
            self.assertGreater(delay, 0)
            self.assertLessEqual(delay, 2 * 3600 + 60)
            self.assertEqual(target_dt.hour, future_time.hour)
            self.assertEqual(target_dt.minute, future_time.minute)
            self.assertEqual(target_dt.date(), fixed_now.date())

    def test_calculate_delay_past_today_wraps_to_tomorrow(self):
        fixed_now = datetime(2026, 8, 29, 14, 0, 0)
        past_time = fixed_now - timedelta(hours=2)
        with unittest.mock.patch("gtfb.core.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            delay, target_dt = calculate_delay(past_time.hour, past_time.minute)
            # Should wrap to next day, delay should be between 20h and 24h
            self.assertGreater(delay, 20 * 3600)
            self.assertLessEqual(delay, 24 * 3600)
            self.assertEqual(target_dt.date(), (fixed_now + timedelta(days=1)).date())


class TestPlatformAndProcessUtils(unittest.TestCase):
    """Test cross-platform window detection and process enumeration."""

    def test_current_os_detected(self):
        self.assertIn(CURRENT_OS, ["Windows", "Linux", "Darwin"])

    def test_current_python_process_excluded_from_gui(self):
        current_proc = psutil.Process(os.getpid())
        self.assertFalse(is_gui_application(current_proc))

    def test_get_running_gui_apps_runs_without_error(self):
        apps = get_running_gui_apps()
        self.assertIsInstance(apps, list)
        for item in apps:
            self.assertIsInstance(item, tuple)
            self.assertEqual(len(item), 2)
            self.assertIsInstance(item[0], psutil.Process)
            self.assertIsInstance(item[1], str)


class TestCloserSafety(unittest.TestCase):
    """Test that the closer protects itself and honours the grace period."""

    def test_protected_pids_include_self_and_parent(self):
        from gtfb.core.closer import _protected_pids

        protected = _protected_pids()
        self.assertIn(os.getpid(), protected)
        self.assertIn(os.getppid(), protected)

    def test_get_running_gui_apps_skips_own_and_parent_windows(self):
        own_pid, parent_pid, other_pid = 111, 222, 333
        windows = {own_pid: "GTFB — Settings", parent_pid: "Terminal", other_pid: "Notepad"}

        def fake_process(pid):
            proc = MagicMock()
            proc.pid = pid
            proc.name.return_value = "notepad.exe"
            return proc

        with patch("gtfb.core.closer.platform_utils.CURRENT_OS", "Windows"), \
             patch("gtfb.core.closer.platform_utils.PYWIN32_AVAILABLE", True), \
             patch("gtfb.core.closer.get_gui_windows_pywin32", return_value=windows), \
             patch("gtfb.core.closer._protected_pids", return_value={own_pid, parent_pid}), \
             patch("gtfb.core.closer.psutil.Process", side_effect=fake_process):
            apps = get_running_gui_apps()

        self.assertEqual([(proc.pid, title) for proc, title in apps], [(other_pid, "Notepad")])

    def _run_close(self, **kwargs):
        from gtfb.core.closer import close_gui_applications

        quick = MagicMock()
        quick.pid = 1
        quick.name.return_value = "quick.exe"
        stubborn = MagicMock()
        stubborn.pid = 2
        stubborn.name.return_value = "stubborn.exe"

        with patch("gtfb.core.closer.get_running_gui_apps", return_value=[(quick, "Quick"), (stubborn, "Stubborn")]), \
             patch("gtfb.core.closer._request_close") as mock_request, \
             patch("gtfb.core.closer.psutil.wait_procs", return_value=([quick], [stubborn])) as mock_wait:
            closed = close_gui_applications(**kwargs)

        return closed, quick, stubborn, mock_request, mock_wait

    def test_close_waits_one_shared_grace_period_then_force_kills(self):
        closed, quick, stubborn, mock_request, mock_wait = self._run_close(grace_period=20)

        self.assertEqual(mock_request.call_count, 2)
        mock_wait.assert_called_once()
        self.assertEqual(mock_wait.call_args.kwargs["timeout"], 20)
        quick.kill.assert_not_called()
        stubborn.kill.assert_called_once()
        self.assertEqual(closed, ["quick.exe", "stubborn.exe"])

    def test_close_leaves_survivors_running_when_force_kill_disabled(self):
        closed, _, stubborn, _, _ = self._run_close(grace_period=20, force_kill=False)

        stubborn.kill.assert_not_called()
        self.assertEqual(closed, ["quick.exe"])


class TestAppCliParser(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_default_args(self):
        parser = build_parser()
        args = parser.parse_args([])
        # Unset by default so the saved configuration decides the bedtime
        self.assertIsNone(args.hour)
        self.assertIsNone(args.minute)
        self.assertFalse(args.no_shutdown)
        self.assertFalse(args.dry_run)

    def test_custom_args(self):
        parser = build_parser()
        args = parser.parse_args(["--hour", "23", "--minute", "45", "--no-shutdown", "--dry-run"])
        self.assertEqual(args.hour, 23)
        self.assertEqual(args.minute, 45)
        self.assertTrue(args.no_shutdown)
        self.assertTrue(args.dry_run)


if __name__ == "__main__":
    unittest.main()
