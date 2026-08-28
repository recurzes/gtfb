"""Tests for BedtimeScheduler background worker thread and execution logic."""

from datetime import datetime, timedelta
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from gtfb.core.scheduler import BedtimeScheduler, calculate_delay


class TestBedtimeScheduler(unittest.TestCase):
    """Test suite for BedtimeScheduler class."""

    def test_default_initialization(self):
        scheduler = BedtimeScheduler()
        self.assertEqual(scheduler.target_hour, 22)
        self.assertEqual(scheduler.target_minute, 0)
        self.assertFalse(scheduler.dry_run)
        self.assertFalse(scheduler.shutdown)
        self.assertEqual(scheduler.check_interval, 1.0)
        self.assertFalse(scheduler.is_running())

    def test_custom_initialization(self):
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(
            target_hour=23,
            target_minute=30,
            dry_run=True,
            shutdown=True,
            check_interval=0.1,
            closer_fn=mock_closer,
        )
        self.assertEqual(scheduler.target_hour, 23)
        self.assertEqual(scheduler.target_minute, 30)
        self.assertTrue(scheduler.dry_run)
        self.assertTrue(scheduler.shutdown)
        self.assertEqual(scheduler.check_interval, 0.1)
        self.assertEqual(scheduler.closer_fn, mock_closer)

    def test_get_next_target_future(self):
        now = datetime.now()
        future_dt = now + timedelta(hours=3)
        scheduler = BedtimeScheduler(target_hour=future_dt.hour, target_minute=future_dt.minute)
        target = scheduler.get_next_target()
        self.assertEqual(target.hour, future_dt.hour)
        self.assertEqual(target.minute, future_dt.minute)
        self.assertEqual(target.date(), now.date())

    def test_get_next_target_past_wraps_tomorrow(self):
        now = datetime.now()
        past_dt = now - timedelta(hours=3)
        scheduler = BedtimeScheduler(target_hour=past_dt.hour, target_minute=past_dt.minute)
        target = scheduler.get_next_target()
        self.assertEqual(target.hour, past_dt.hour)
        self.assertEqual(target.minute, past_dt.minute)
        self.assertEqual(target.date(), (now + timedelta(days=1)).date())

    def test_start_and_stop_lifecycle(self):
        scheduler = BedtimeScheduler(check_interval=0.05)
        self.assertFalse(scheduler.is_running())

        scheduler.start()
        self.assertTrue(scheduler.is_running())
        self.assertIsNotNone(scheduler._thread)
        self.assertTrue(scheduler._thread.daemon)
        self.assertEqual(scheduler._thread.name, "SchedulerWorker")

        # Idempotent start
        first_thread = scheduler._thread
        scheduler.start()
        self.assertEqual(scheduler._thread, first_thread)

        scheduler.stop(timeout=1.0)
        self.assertFalse(scheduler.is_running())
        self.assertFalse(scheduler._thread.is_alive())

        # Idempotent stop
        scheduler.stop()

    def test_scheduler_triggers_closer_fn_when_time_reached(self):
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(
            dry_run=True,
            check_interval=0.01,
            closer_fn=mock_closer,
        )

        # Mock get_next_target to return a time in the past so it triggers immediately
        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time):
            scheduler.start()
            # Wait briefly for worker thread to execute
            time.sleep(0.1)
            scheduler.stop()

        mock_closer.assert_called_once_with(dry_run=True)

    def test_scheduler_triggers_shutdown_when_configured(self):
        mock_closer = MagicMock()
        mock_shutdown = MagicMock()

        scheduler = BedtimeScheduler(
            target_hour=23,
            target_minute=15,
            dry_run=False,
            shutdown=True,
            check_interval=0.01,
            closer_fn=mock_closer,
        )

        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time), \
             patch("gtfb.core.scheduler.shutdown_system", mock_shutdown):
            scheduler.start()
            time.sleep(0.1)
            scheduler.stop()

        mock_closer.assert_called_once_with(dry_run=False)
        mock_shutdown.assert_called_once_with(target_hour=23, target_minute=15)

    def test_scheduler_handles_closer_exception_gracefully(self):
        def failing_closer(dry_run=False):
            raise RuntimeError("Closer error simulation")

        scheduler = BedtimeScheduler(
            dry_run=False,
            check_interval=0.01,
            closer_fn=failing_closer,
        )

        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time):
            scheduler.start()
            time.sleep(0.1)
            scheduler.stop()

        self.assertFalse(scheduler.is_running())


if __name__ == "__main__":
    unittest.main()
