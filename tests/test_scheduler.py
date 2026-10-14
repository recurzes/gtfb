"""Tests for BedtimeScheduler background worker thread and execution logic."""

from datetime import datetime, timedelta
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from gtfb.config.models import AppCloseSchedule, ConfigProfile
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
        fixed_now = datetime(2026, 8, 29, 10, 0, 0)
        future_dt = fixed_now + timedelta(hours=3)
        scheduler = BedtimeScheduler(target_hour=future_dt.hour, target_minute=future_dt.minute)
        with patch("gtfb.core.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.combine = datetime.combine
            mock_dt.min = datetime.min
            target = scheduler.get_next_target()
            self.assertEqual(target.hour, future_dt.hour)
            self.assertEqual(target.minute, future_dt.minute)
            self.assertEqual(target.date(), fixed_now.date())

    def test_get_next_target_past_wraps_tomorrow(self):
        fixed_now = datetime(2026, 8, 29, 15, 0, 0)
        past_dt = fixed_now - timedelta(hours=3)
        scheduler = BedtimeScheduler(target_hour=past_dt.hour, target_minute=past_dt.minute)
        with patch("gtfb.core.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.combine = datetime.combine
            mock_dt.min = datetime.min
            target = scheduler.get_next_target()
            self.assertEqual(target.hour, past_dt.hour)
            self.assertEqual(target.minute, past_dt.minute)
            self.assertEqual(target.date(), (fixed_now + timedelta(days=1)).date())


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

    def test_rapid_start_stop_toggling_thread_safety(self):
        """Test rapid start and stop toggling without thread leaks or crashes."""
        scheduler = BedtimeScheduler(check_interval=0.01)

        for _ in range(20):
            scheduler.start()
            self.assertTrue(scheduler.is_running())
            scheduler.stop(timeout=0.5)
            self.assertFalse(scheduler.is_running())

        # Test concurrent start/stop calls from multiple threads
        def toggle():
            for _ in range(10):
                scheduler.start()
                time.sleep(0.005)
                scheduler.stop(timeout=0.5)

        threads = [threading.Thread(target=toggle) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        scheduler.stop(timeout=0.5)
        self.assertFalse(scheduler.is_running())

    def test_stopped_scheduler_prevents_closer_execution(self):
        """Test that stopping the scheduler halts countdown and prevents closer execution."""
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(check_interval=0.01, closer_fn=mock_closer)

        scheduler.start()
        self.assertTrue(scheduler.is_running())
        scheduler.stop(timeout=0.5)
        self.assertFalse(scheduler.is_running())

        # Wait to ensure closer is not invoked after stopping
        time.sleep(0.05)
        mock_closer.assert_not_called()

    def test_restart_scheduler_rearms_countdown(self):
        """Test restarting a stopped scheduler successfully spawns a new worker thread."""
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(check_interval=0.01, closer_fn=mock_closer)

        scheduler.start()
        self.assertTrue(scheduler.is_running())
        first_thread = scheduler._thread

        scheduler.stop(timeout=0.5)
        self.assertFalse(scheduler.is_running())

        scheduler.start()
        self.assertTrue(scheduler.is_running())
        self.assertIsNot(scheduler._thread, first_thread)

        scheduler.stop(timeout=0.5)
        self.assertFalse(scheduler.is_running())

    def test_scheduler_state_transitions(self):
        """Test state property through STOPPED, COUNTING_DOWN, and ENFORCING states."""
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(check_interval=0.01, closer_fn=mock_closer)
        self.assertEqual(scheduler.state, "STOPPED")

        # Start countdown
        scheduler.start()
        self.assertEqual(scheduler.state, "COUNTING_DOWN")
        scheduler.stop(timeout=0.5)
        self.assertEqual(scheduler.state, "STOPPED")

        # Trigger bedtime to enter ENFORCING
        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time):
            scheduler.start()
            time.sleep(0.1)
            self.assertEqual(scheduler.state, "ENFORCING")
            scheduler.stop()
            self.assertEqual(scheduler.state, "STOPPED")

    def test_get_time_remaining_and_formatted_remaining(self):
        scheduler = BedtimeScheduler(target_hour=22, target_minute=0)
        # When stopped
        self.assertEqual(scheduler.get_time_remaining(), 0.0)
        self.assertEqual(scheduler.get_formatted_remaining(), "0s remaining")
        self.assertEqual(scheduler.get_status_detail(), "")

        # Mock target time in future while running
        mock_target = datetime.now() + timedelta(hours=2, minutes=15, seconds=30)
        with patch.object(scheduler, "is_running", return_value=True), \
             patch.object(scheduler, "get_next_target", return_value=mock_target):
            # Hours remaining format
            self.assertGreater(scheduler.get_time_remaining(), 0)
            self.assertEqual(scheduler.get_formatted_remaining(), "2h 15m remaining")
            self.assertIn("Bedtime at 22:00 — 2h 15m remaining", scheduler.get_status_detail())

        # Minutes remaining format (<1 hour)
        mock_target_mins = datetime.now() + timedelta(minutes=42, seconds=10)
        with patch.object(scheduler, "is_running", return_value=True), \
             patch.object(scheduler, "get_next_target", return_value=mock_target_mins):
            self.assertEqual(scheduler.get_formatted_remaining(), "42m remaining")
            self.assertEqual(scheduler.get_status_detail(), "Bedtime at 22:00 — 42m remaining")

        # Seconds remaining format (<1 minute)
        mock_target_secs = datetime.now() + timedelta(seconds=45)
        with patch.object(scheduler, "is_running", return_value=True), \
             patch.object(scheduler, "get_next_target", return_value=mock_target_secs):
            self.assertIn("s remaining", scheduler.get_formatted_remaining())

        # Detail when enforcing
        scheduler._state = "ENFORCING"
        scheduler._stop_event.clear()
        self.assertEqual(scheduler.get_status_detail(), "Bedtime enforcement active")

    def test_update_config_updates_scheduler_in_memory(self):
        scheduler = BedtimeScheduler(target_hour=22, target_minute=0)
        self.assertEqual(scheduler.target_hour, 22)
        self.assertEqual(scheduler.target_minute, 0)
        self.assertTrue(scheduler.enabled)

        new_config = ConfigProfile(
            app_close_schedule=AppCloseSchedule(
                target_hour=23,
                target_minute=30,
                enabled=False,
            )
        )
        scheduler.update_config(new_config)

        self.assertEqual(scheduler.target_hour, 23)
        self.assertEqual(scheduler.target_minute, 30)
        self.assertFalse(scheduler.enabled)

    def test_update_config_dynamically_updates_countdown_during_active_run(self):
        scheduler = BedtimeScheduler(target_hour=22, target_minute=0, check_interval=0.01)
        scheduler.start()
        try:
            self.assertTrue(scheduler.is_running())
            self.assertIn("Bedtime at 22:00", scheduler.get_status_detail())

            # Update bedtime config to 23:30 while running
            new_config = ConfigProfile(
                app_close_schedule=AppCloseSchedule(target_hour=23, target_minute=30, enabled=True)
            )
            scheduler.update_config(new_config)

            self.assertIn("Bedtime at 23:30", scheduler.get_status_detail())
        finally:
            scheduler.stop()

    def test_scheduler_disabled_skips_closer_fn(self):
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(
            target_hour=22,
            target_minute=0,
            check_interval=0.01,
            closer_fn=mock_closer,
            enabled=False,
        )

        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time):
            scheduler.start()
            time.sleep(0.1)
            scheduler.stop()

        mock_closer.assert_not_called()
        self.assertFalse(scheduler.is_running())

    def test_update_config_applies_grace_period_and_force_kill(self):
        scheduler = BedtimeScheduler()
        self.assertIsNone(scheduler.grace_period_seconds)
        self.assertIsNone(scheduler.force_kill)

        scheduler.update_config(
            ConfigProfile(
                app_close_schedule=AppCloseSchedule(
                    grace_period_seconds=45,
                    force_kill_after_grace=False,
                )
            )
        )

        self.assertEqual(scheduler.grace_period_seconds, 45)
        self.assertFalse(scheduler.force_kill)

    def test_scheduler_passes_grace_settings_to_closer(self):
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(
            check_interval=0.01,
            closer_fn=mock_closer,
            grace_period_seconds=45,
            force_kill=False,
        )

        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time):
            scheduler.start()
            time.sleep(0.1)
            scheduler.stop()

        mock_closer.assert_called_once_with(dry_run=False, grace_period=45, force_kill=False)

    def test_missed_bedtime_beyond_tolerance_is_skipped(self):
        """A target passed long ago (system asleep through bedtime) must not close apps on wake."""
        mock_closer = MagicMock()
        mock_shutdown = MagicMock()
        scheduler = BedtimeScheduler(
            shutdown=True,
            check_interval=0.01,
            closer_fn=mock_closer,
            late_tolerance=300.0,
        )

        stale_target = datetime.now() - timedelta(hours=2)
        with patch.object(scheduler, "get_next_target", return_value=stale_target), \
             patch("gtfb.core.scheduler.shutdown_system", mock_shutdown):
            scheduler.start()
            time.sleep(0.1)
            try:
                mock_closer.assert_not_called()
                mock_shutdown.assert_not_called()
                # Still armed for the next day
                self.assertTrue(scheduler.is_running())
                self.assertEqual(scheduler.state, "COUNTING_DOWN")
            finally:
                scheduler.stop()

    def test_scheduler_rearms_after_trigger_without_refiring(self):
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(dry_run=True, check_interval=0.01, closer_fn=mock_closer)

        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time):
            scheduler.start()
            time.sleep(0.15)
            try:
                # Worker thread stays alive for the next day and does not fire again
                self.assertTrue(scheduler.is_running())
                mock_closer.assert_called_once_with(dry_run=True)
            finally:
                scheduler.stop()

    def test_state_returns_to_counting_down_after_enforcing_hold(self):
        scheduler = BedtimeScheduler(
            dry_run=True,
            check_interval=0.01,
            closer_fn=MagicMock(),
            enforcing_hold=0.05,
        )

        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time):
            scheduler.start()
            try:
                time.sleep(0.02)
                self.assertEqual(scheduler.state, "ENFORCING")
                time.sleep(0.2)
                self.assertEqual(scheduler.state, "COUNTING_DOWN")
            finally:
                scheduler.stop()

    def test_disabled_scheduler_keeps_running_for_next_day(self):
        mock_closer = MagicMock()
        scheduler = BedtimeScheduler(check_interval=0.01, closer_fn=mock_closer, enabled=False)

        past_time = datetime.now() - timedelta(seconds=1)
        with patch.object(scheduler, "get_next_target", return_value=past_time):
            scheduler.start()
            time.sleep(0.1)
            try:
                mock_closer.assert_not_called()
                self.assertTrue(scheduler.is_running())
            finally:
                scheduler.stop()


if __name__ == "__main__":
    unittest.main()



