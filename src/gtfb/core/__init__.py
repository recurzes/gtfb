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
    create_startup_shortcut,
    get_gui_windows_pywin32,
    get_startup_shortcut_path,
    get_system_diagnostics,
    get_windows_startup_dir,
    is_admin_or_root,
    is_gui_application,
    is_startup_shortcut_installed,
    open_windows_startup_folder,
    print_system_diagnostics,
    remove_startup_shortcut,
)
from gtfb.core.scheduler import (
    BedtimeScheduler,
    SchedulerState,
    calculate_delay,
    run_scheduler_cli,
    wait_until_shutdown_time,
)

__all__ = [
    "CURRENT_OS",
    "PYWIN32_AVAILABLE",
    "create_startup_shortcut",
    "get_gui_windows_pywin32",
    "get_startup_shortcut_path",
    "get_system_diagnostics",
    "get_windows_startup_dir",
    "is_admin_or_root",
    "is_gui_application",
    "is_startup_shortcut_installed",
    "open_windows_startup_folder",
    "print_system_diagnostics",
    "remove_startup_shortcut",
    "close_application",
    "close_gui_apps",
    "close_gui_applications",
    "get_running_gui_apps",
    "shutdown_system",
    "BedtimeScheduler",
    "SchedulerState",
    "calculate_delay",
    "wait_until_shutdown_time",
    "run_scheduler_cli",
]


