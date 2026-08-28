"""Bedtime countdown, delay calculation, and scheduling loop."""

import time
from datetime import datetime, timedelta
from typing import Optional, Tuple

from gtfb.config import DEFAULT_TARGET_HOUR, DEFAULT_TARGET_MINUTE
from gtfb.core.closer import check_privileges, close_gui_applications, get_running_gui_apps, shutdown_system
from gtfb.core.platform_utils import CURRENT_OS, PYWIN32_AVAILABLE


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
