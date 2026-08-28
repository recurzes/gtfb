"""Platform-specific utilities for window detection and GUI process identification."""

import os
import platform
from typing import Dict, Optional

import psutil

from gtfb.config import LINUX_GUI_PATTERNS, MACOS_GUI_PATTERNS, SYSTEM_EXCLUDED_PROCESSES

CURRENT_OS: str = platform.system()

if CURRENT_OS == "Windows":
    try:
        import win32con
        import win32gui
        import win32process

        PYWIN32_AVAILABLE: bool = True
    except ImportError:
        PYWIN32_AVAILABLE = False
else:
    PYWIN32_AVAILABLE = False


def get_gui_windows_pywin32() -> Dict[int, str]:
    """Enumerate visible top-level GUI windows on Windows using pywin32.

    Returns:
        Dict[int, str]: Mapping of Process ID (PID) to Window Title.
    """
    if not PYWIN32_AVAILABLE:
        return {}

    gui_apps: Dict[int, str] = {}

    def enum_window_callback(hwnd: int, results: Dict[int, str]) -> None:
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return

            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

            # Check visible and not tool window
            if style & win32con.WS_VISIBLE and not (ex_style & win32con.WS_EX_TOOLWINDOW):
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in results:
                    results[pid] = title

    try:
        win32gui.EnumWindows(enum_window_callback, gui_apps)
    except Exception as e:
        # Logging or debug output
        print(f"Error enumerating windows: {e}")

    return gui_apps


def has_visible_window_windows(proc: psutil.Process) -> bool:
    """Determine if a Windows process has a visible GUI window."""
    if PYWIN32_AVAILABLE:
        gui_windows = get_gui_windows_pywin32()
        return proc.pid in gui_windows

    try:
        username = proc.username()
        current_user = os.environ.get("USERNAME", "")
        return (
            proc.num_threads() > 1
            and bool(username)
            and bool(current_user)
            and current_user.lower() in username.lower()
        )
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return False


def has_visible_window_linux(proc: psutil.Process) -> bool:
    """Determine if a Linux process has a visible GUI window via environment and name heuristic."""
    try:
        env = proc.environ()
        if "DISPLAY" in env or "WAYLAND_DISPLAY" in env:
            proc_name = proc.name().lower()
            return any(pattern in proc_name for pattern in LINUX_GUI_PATTERNS)
        return False
    except (psutil.AccessDenied, psutil.NoSuchProcess, KeyError):
        return False


def has_visible_window_macos(proc: psutil.Process) -> bool:
    """Determine if a macOS process is a GUI application."""
    try:
        proc_name = proc.name().lower()
        if any(pattern in proc_name for pattern in MACOS_GUI_PATTERNS):
            return True

        try:
            exe = proc.exe()
            if "/Applications/" in exe and ".app/" in exe:
                return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass

        return False
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return False


def is_gui_application(proc: psutil.Process) -> bool:
    """Check if the given psutil Process corresponds to a visible user-facing GUI application."""
    try:
        proc_name = proc.name().lower()

        if proc_name in SYSTEM_EXCLUDED_PROCESSES:
            return False

        # Exclude our own python process
        if "python" in proc_name and proc.pid == os.getpid():
            return False

        if CURRENT_OS == "Windows":
            return has_visible_window_windows(proc)
        elif CURRENT_OS == "Linux":
            return has_visible_window_linux(proc)
        elif CURRENT_OS == "Darwin":
            return has_visible_window_macos(proc)

        return False
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return False
