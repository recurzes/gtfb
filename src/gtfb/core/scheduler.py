"""Bedtime countdown, delay calculation, and scheduling loop."""

from enum import Enum
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Tuple

from gtfb.config import DEFAULT_TARGET_HOUR, DEFAULT_TARGET_MINUTE
from gtfb.core.closer import (
    check_privileges,
    close_gui_applications,
    close_gui_apps,
    get_running_gui_apps,
    shutdown_system,
)
from gtfb.core.platform_utils import CURRENT_OS, PYWIN32_AVAILABLE

logger = logging.getLogger("gtfb.core.scheduler")


class SchedulerState(str, Enum):
    """Application scheduler operational states."""

    STOPPED = "STOPPED"
    COUNTING_DOWN = "COUNTING_DOWN"
    ENFORCING = "ENFORCING"


def calculate_delay(target_hour: int = DEFAULT_TARGET_HOUR, target_minute: int = DEFAULT_TARGET_MINUTE) -> Tuple[float, datetime]:
    """Calculate the remaining seconds and target datetime until the specified bedtime.

    If target time is earlier today than current time, targets the next calendar day.
    """
    now = datetime.now()
    target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

    if now >= target_time:
        target_time += timedelta(days=1)

    time_difference = (target_time - now).total_seconds()
    return time_difference, target_time


class BedtimeScheduler:
    """Controllable background bedtime scheduler and application closer worker."""

    def __init__(
        self,
        target_hour: int = DEFAULT_TARGET_HOUR,
        target_minute: int = DEFAULT_TARGET_MINUTE,
        dry_run: bool = False,
        shutdown: bool = False,
        check_interval: float = 1.0,
        closer_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.target_hour = target_hour
        self.target_minute = target_minute
        self.dry_run = dry_run
        self.shutdown = shutdown
        self.check_interval = check_interval
        self.closer_fn = closer_fn or close_gui_apps
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._state: SchedulerState = SchedulerState.STOPPED

    @property
    def state(self) -> SchedulerState:
        """Return the current scheduler state."""
        if self._stop_event.is_set():
            return SchedulerState.STOPPED
        if self._state == SchedulerState.ENFORCING:
            return SchedulerState.ENFORCING
        if self.is_running():
            return SchedulerState.COUNTING_DOWN
        return SchedulerState.STOPPED

    def get_time_remaining(self) -> float:
        """Return remaining seconds until next bedtime target if counting down, otherwise 0.0."""
        if self.is_running() and self.state == SchedulerState.COUNTING_DOWN:
            target = self.get_next_target()
            diff = (target - datetime.now()).total_seconds()
            return max(0.0, diff)
        return 0.0

    def get_formatted_remaining(self) -> str:
        """Format the remaining countdown duration into human-readable text."""
        rem = self.get_time_remaining()
        if rem <= 0:
            return "0s remaining"
        hours = int(rem // 3600)
        minutes = int((rem % 3600) // 60)
        seconds = int(rem % 60)
        if hours > 0:
            return f"{hours}h {minutes}m remaining"
        elif minutes > 0:
            return f"{minutes}m remaining"
        else:
            return f"{seconds}s remaining"

    def get_status_detail(self) -> str:
        """Return a descriptive status string suitable for tray tooltips or status displays."""
        current_state = self.state
        if current_state == SchedulerState.COUNTING_DOWN:
            return f"Bedtime at {self.target_hour:02d}:{self.target_minute:02d} — {self.get_formatted_remaining()}"
        elif current_state == SchedulerState.ENFORCING:
            return "Bedtime enforcement active"
        return ""

    def get_next_target(self) -> datetime:
        """Calculate the next target datetime based on target_hour and target_minute."""
        now = datetime.now()
        target = now.replace(hour=self.target_hour, minute=self.target_minute, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        return target

    def is_running(self) -> bool:
        """Return True if the scheduler worker thread is alive and active."""
        return self._thread is not None and self._thread.is_alive() and not self._stop_event.is_set()

    def start(self) -> None:
        """Start the scheduler background worker thread if not already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.debug("Bedtime scheduler already running.")
                return

            self._stop_event.clear()
            self._state = SchedulerState.COUNTING_DOWN
            self._thread = threading.Thread(target=self._run_loop, name="SchedulerWorker", daemon=True)
            self._thread.start()
            logger.info(
                "Bedtime scheduler worker started (target: %02d:%02d, dry_run=%s, shutdown=%s).",
                self.target_hour,
                self.target_minute,
                self.dry_run,
                self.shutdown,
            )

    def stop(self, timeout: float = 2.0) -> None:
        """Signal the worker thread to stop and wait for it to join."""
        with self._lock:
            self._stop_event.set()
            self._state = SchedulerState.STOPPED
            if self._thread is not None and self._thread.is_alive():
                self._thread.join(timeout=timeout)
                logger.info("Bedtime scheduler worker stopped.")

    def _run_loop(self) -> None:
        """Worker loop executing the bedtime countdown."""
        logger.info("Bedtime scheduler worker loop running.")
        target_time = self.get_next_target()
        logger.info("Next scheduled bedtime target: %s", target_time.strftime("%Y-%m-%d %H:%M:%S"))

        while not self._stop_event.is_set():
            now = datetime.now()
            time_remaining = (target_time - now).total_seconds()

            if time_remaining <= 0:
                self._state = SchedulerState.ENFORCING
                logger.warning("Bedtime reached! Executing application closing routine.")
                try:
                    self.closer_fn(dry_run=self.dry_run)
                except TypeError:
                    self.closer_fn()
                except Exception as err:
                    logger.exception("Error executing bedtime closer routine: %s", err)

                if self.shutdown and not self.dry_run:
                    logger.info("Initiating scheduled system shutdown...")
                    shutdown_system(target_hour=self.target_hour, target_minute=self.target_minute)
                break

            self._stop_event.wait(timeout=self.check_interval)




def wait_until_shutdown_time(
    target_hour: int = DEFAULT_TARGET_HOUR,
    target_minute: int = DEFAULT_TARGET_MINUTE,
    check_interval: float = 300.0,
    stop_event: Optional[object] = None,
) -> bool:
    """Block execution until the target bedtime arrives, printing periodic status updates.

    Args:
        target_hour: Target bedtime hour (0-23)
        target_minute: Target bedtime minute (0-59)
        check_interval: Interval in seconds between progress logs
        stop_event: Optional threading.Event instance to cancel waiting early

    Returns:
        bool: True if target time reached, False if cancelled
    """
    now = datetime.now()
    time_difference, target_time = calculate_delay(target_hour, target_minute)

    print(f"\n{'=' * 70}")
    print(f"Scheduled Shutdown System - {CURRENT_OS}")
    if CURRENT_OS == "Windows" and PYWIN32_AVAILABLE:
        print("Using pywin32 for accurate GUI detection")
    print(f"{'=' * 70}")
    print(f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Shutdown scheduled for: {target_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(
        f"Time until shutdown: {int(time_difference // 3600)}h "
        f"{int((time_difference % 3600) // 60)}m {int(time_difference % 60)}s"
    )
    print(f"{'=' * 70}")

    print("Script is now running in the foreground")
    print(f"It will wait until {target_hour:02d}:{target_minute:02d} to close GUI apps and shutdown")
    print("Press Ctrl+C to cancel\n")

    try:
        remaining = time_difference
        last_update = time.time()

        while remaining > 0:
            if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
                print("\nShutdown cancelled via stop event.")
                return False

            sleep_time = min(5.0 if stop_event else check_interval, remaining)
            time.sleep(sleep_time)
            remaining -= sleep_time

            if remaining > 60 and time.time() - last_update >= check_interval:
                hours = int(remaining // 3600)
                minutes = int((remaining % 3600) // 60)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Still waiting... {hours}h {minutes}m remaining")
                last_update = time.time()

        return True

    except KeyboardInterrupt:
        print("\n\nShutdown cancelled by user")
        return False


def run_scheduler_cli(
    target_hour: int = DEFAULT_TARGET_HOUR,
    target_minute: int = DEFAULT_TARGET_MINUTE,
    shutdown: bool = True,
    dry_run: bool = False,
) -> None:
    """CLI runner executing the complete bedtime automation routine."""
    print(f"\nDetected Operating System: {CURRENT_OS}")
    print("Target: Close GUI applications only (Apps tab equivalent)\n")

    if CURRENT_OS == "Windows":
        if PYWIN32_AVAILABLE:
            print("pywin32 detected - Using accurate Windows GUI detection")
        else:
            print("pywin32 not installed")
            print("Install for better accuracy: pip install pywin32")
        print()

    check_privileges()

    if dry_run:
        print("[DRY RUN] Scanning currently running GUI applications:")
        apps = get_running_gui_apps()
        for proc, title in apps:
            print(f"  - PID {proc.pid}: {proc.name()} | Window: '{title}'")
        print(f"\nTotal detectable GUI apps: {len(apps)}")
        return

    completed = wait_until_shutdown_time(target_hour=target_hour, target_minute=target_minute)
    if not completed:
        return

    close_gui_applications()

    if shutdown:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Preparing for system shutdown...")
        time.sleep(5)
        shutdown_system(target_hour=target_hour, target_minute=target_minute)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Shutdown initiated successfully.")
        print("\nYou can now close this window or wait for shutdown to complete.")
    else:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] System shutdown skipped (no-shutdown mode).")


if __name__ == "__main__":
    try:
        run_scheduler_cli()
    except KeyboardInterrupt:
        print("\n\nScript terminated by user")
    except Exception as e:
        print(f"\nError occurred: {e}")
        import traceback

        traceback.print_exc()
