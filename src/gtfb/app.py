"""Application entry point for GTFB desktop application and CLI runner."""

import argparse
import logging
import sys

from gtfb import __version__
from gtfb.config import (
    DEFAULT_TARGET_HOUR,
    DEFAULT_TARGET_MINUTE,
    ConfigProfile,
    load_config_resilient,
    setup_logging,
)
from gtfb.core.scheduler import BedtimeScheduler, run_scheduler_cli
from gtfb.ui.tray import TrayApp

logger = logging.getLogger("gtfb.app")


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="gtfb",
        description="GTFB: Get The F*** to Bed - Anti-distraction bedtime automation tool",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"gtfb {__version__}",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in foreground CLI mode instead of system tray application.",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=None,
        help=f"Target shutdown hour (0-23, default: saved setting, else {DEFAULT_TARGET_HOUR})",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=None,
        help=f"Target shutdown minute (0-59, default: saved setting, else {DEFAULT_TARGET_MINUTE})",
    )
    parser.add_argument(
        "--no-shutdown",
        action="store_true",
        help="Close GUI applications when target time arrives, but do not shut down the system.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and display running GUI applications immediately without waiting or closing anything.",
    )
    parser.add_argument(
        "--check-system",
        "--diagnostics",
        action="store_true",
        dest="check_system",
        help="Run system and platform capability diagnostic checks and exit.",
    )
    parser.add_argument(
        "--install-startup",
        action="store_true",
        help="Create a shortcut in the Windows Startup folder to run GTFB on system login.",
    )
    parser.add_argument(
        "--remove-startup",
        action="store_true",
        help="Remove the GTFB shortcut from the Windows Startup folder.",
    )
    parser.add_argument(
        "--open-startup-folder",
        action="store_true",
        help="Open the Windows Startup folder in File Explorer.",
    )
    return parser


def load_startup_config(hour: int | None = None, minute: int | None = None) -> ConfigProfile:
    """Load the saved configuration and apply command-line overrides in memory only."""
    try:
        profile = load_config_resilient()
    except Exception as err:
        logger.exception("Could not load saved configuration, using defaults: %s", err)
        profile = ConfigProfile()

    if hour is not None:
        profile.app_close_schedule.target_hour = hour
    if minute is not None:
        profile.app_close_schedule.target_minute = minute
    return profile


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.hour is not None and not 0 <= args.hour <= 23:
        parser.error("--hour must be between 0 and 23")
    if args.minute is not None and not 0 <= args.minute <= 59:
        parser.error("--minute must be between 0 and 59")

    if args.check_system:
        from gtfb.core.platform_utils import print_system_diagnostics

        print_system_diagnostics()
        return 0

    if args.install_startup:
        from gtfb.core.platform_utils import create_startup_shortcut

        try:
            path = create_startup_shortcut()
            print(f"Windows startup shortcut successfully created at:\n  {path}")
            return 0
        except Exception as e:
            print(f"Error creating startup shortcut: {e}", file=sys.stderr)
            return 1

    if args.remove_startup:
        from gtfb.core.platform_utils import remove_startup_shortcut

        try:
            if remove_startup_shortcut():
                print("Windows startup shortcut successfully removed.")
            else:
                print("No GTFB startup shortcut was found to remove.")
            return 0
        except Exception as e:
            print(f"Error removing startup shortcut: {e}", file=sys.stderr)
            return 1

    if args.open_startup_folder:
        from gtfb.core.platform_utils import open_windows_startup_folder

        if open_windows_startup_folder():
            print("Opened Windows Startup folder.")
            return 0
        else:
            print("Opening the startup folder is only supported on Windows.", file=sys.stderr)
            return 1

    config = load_startup_config(hour=args.hour, minute=args.minute)
    schedule = config.app_close_schedule

    if args.cli:
        try:
            run_scheduler_cli(
                target_hour=schedule.target_hour,
                target_minute=schedule.target_minute,
                shutdown=not args.no_shutdown,
                dry_run=args.dry_run,
                grace_period=schedule.grace_period_seconds,
                force_kill=schedule.force_kill_after_grace,
            )
            return 0
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return 130
        except Exception as e:
            logger.exception("Error in CLI runner: %s", e)
            print(f"Error: {e}", file=sys.stderr)
            return 1

    try:
        scheduler = BedtimeScheduler(
            target_hour=schedule.target_hour,
            target_minute=schedule.target_minute,
            dry_run=args.dry_run,
            shutdown=not args.no_shutdown,
            enabled=schedule.enabled,
            grace_period_seconds=schedule.grace_period_seconds,
            force_kill=schedule.force_kill_after_grace,
        )
        app = TrayApp(scheduler=scheduler, config=config)
        app.run()
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        logger.exception("Error starting GTFB tray app: %s", e)
        print(f"Error starting GTFB tray app: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

