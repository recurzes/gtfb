"""GTFB Core process management and scheduling primitives."""

from gtfb.core.closer import (
    close_application,
    close_gui_apps,
    close_gui_applications,
    get_running_gui_apps,
    shutdown_system,
)
from gtfb.core.platform_utils import (
    CURRENT_OS,
    PYWIN32_AVAILABLE,
    get_gui_windows_pywin32,
    is_gui_application,
)
from gtfb.core.scheduler import (
    calculate_delay,
    run_scheduler_cli,
    wait_until_shutdown_time,
)

__all__ = [
    "CURRENT_OS",
    "PYWIN32_AVAILABLE",
    "get_gui_windows_pywin32",
    "is_gui_application",
    "close_application",
    "close_gui_apps",
    "close_gui_applications",
    "get_running_gui_apps",
    "shutdown_system",
    "calculate_delay",
    "wait_until_shutdown_time",
    "run_scheduler_cli",
]
