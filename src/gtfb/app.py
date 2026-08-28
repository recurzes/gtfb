"""Application entry point for GTFB desktop application and CLI runner."""

import argparse
import sys

from gtfb import __version__
from gtfb.config import DEFAULT_TARGET_HOUR, DEFAULT_TARGET_MINUTE
from gtfb.core.scheduler import run_scheduler_cli


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
    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

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
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
