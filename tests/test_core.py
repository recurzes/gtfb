"""Tests for GTFB core modules and packaging structure."""

import os
import unittest
from datetime import datetime, timedelta

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
        now = datetime.now()
        # Set target 2 hours ahead
        future_time = now + timedelta(hours=2)
        delay, target_dt = calculate_delay(future_time.hour, future_time.minute)
        self.assertGreater(delay, 0)
        self.assertLessEqual(delay, 2 * 3600 + 60)
        self.assertEqual(target_dt.hour, future_time.hour)
        self.assertEqual(target_dt.minute, future_time.minute)

    def test_calculate_delay_past_today_wraps_to_tomorrow(self):
        now = datetime.now()
        # Set target 2 hours in the past
        past_time = now - timedelta(hours=2)
        delay, target_dt = calculate_delay(past_time.hour, past_time.minute)
        # Should wrap to next day, delay should be between 20h and 24h
        self.assertGreater(delay, 20 * 3600)
        self.assertLessEqual(delay, 24 * 3600)
        self.assertEqual(target_dt.date(), (now + timedelta(days=1)).date())


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


class TestAppCliParser(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_default_args(self):
        parser = build_parser()
        args = parser.parse_args([])
        self.assertEqual(args.hour, 22)
        self.assertEqual(args.minute, 0)
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
