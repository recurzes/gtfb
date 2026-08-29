"""Application entry point for GTFB desktop application and CLI runner."""

import argparse
import logging
import sys

from gtfb import __version__
from gtfb.config import DEFAULT_TARGET_HOUR, DEFAULT_TARGET_MINUTE, setup_logging
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
        default=DEFAULT_TARGET_HOUR,
        help=f"Target shutdown hour (0-23, default: {DEFAULT_TARGET_HOUR})",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=DEFAULT_TARGET_MINUTE,
        help=f"Target shutdown minute (0-59, default: {DEFAULT_TARGET_MINUTE})",
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


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

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

    if args.cli:
        try:
            run_scheduler_cli(
                target_hour=args.hour,
                target_minute=args.minute,
                shutdown=not args.no_shutdown,
                dry_run=args.dry_run,
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
            target_hour=args.hour,
            target_minute=args.minute,
            dry_run=args.dry_run,
            shutdown=not args.no_shutdown,
        )
        app = TrayApp(scheduler=scheduler)
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

