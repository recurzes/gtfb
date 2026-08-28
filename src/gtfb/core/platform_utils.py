"""Platform-specific utilities for window detection and GUI process identification."""

import ctypes
import logging
import os
import platform
import shutil
import sys
from typing import Any, Dict, List, Optional

import psutil

from gtfb.config import LINUX_GUI_PATTERNS, MACOS_GUI_PATTERNS, SYSTEM_EXCLUDED_PROCESSES

logger = logging.getLogger("gtfb.core.platform_utils")

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


def is_admin_or_root() -> bool:
    """Check if the current process has administrative or root privileges."""
    if CURRENT_OS == "Windows":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin() != 0)
        except Exception:
            return False
    else:
        if hasattr(os, "geteuid"):
            return os.geteuid() == 0
        return False


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
        logger.debug("Error enumerating windows: %s", e)

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


def _get_pkg_version(pkg_name: str, module: Any = None) -> str:
    """Retrieve package version via attribute or importlib metadata."""
    if module and hasattr(module, "__version__"):
        return str(module.__version__)
    try:
        import importlib.metadata
        return importlib.metadata.version(pkg_name)
    except Exception:
        return "unknown"


def get_system_diagnostics() -> Dict[str, Any]:
    """Gather diagnostic and capability information across platforms.

    Returns:
        Dict[str, Any]: Diagnostic information for system, tray, closer, and environment.
    """
    # 1. OS & Python Info
    os_info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "is_admin_or_root": is_admin_or_root(),
    }

    # 2. Tray Backend Info
    tray_info: Dict[str, Any] = {}
    try:
        import pystray
        tray_info["pystray_available"] = True
        tray_info["pystray_version"] = _get_pkg_version("pystray", pystray)
        tray_info["backend_module"] = getattr(pystray.Icon, "__module__", "unknown")
    except Exception as err:
        tray_info["pystray_available"] = False
        tray_info["error"] = str(err)

    try:
        import PIL
        tray_info["pillow_available"] = True
        tray_info["pillow_version"] = _get_pkg_version("pillow", PIL)
    except Exception as err:
        tray_info["pillow_available"] = False
        tray_info["pillow_error"] = str(err)

    # 3. Process & Automation Utilities
    process_info: Dict[str, Any] = {
        "psutil_available": True,
        "psutil_version": _get_pkg_version("psutil", psutil),
        "pywin32_available": PYWIN32_AVAILABLE,
        "pywin32_version": _get_pkg_version("pywin32") if PYWIN32_AVAILABLE else None,
        "xdotool_available": shutil.which("xdotool") is not None,
        "wmctrl_available": shutil.which("wmctrl") is not None,
        "osascript_available": shutil.which("osascript") is not None,
    }

    # 4. Display / Session Environment
    display_info: Dict[str, Any] = {
        "DISPLAY": os.environ.get("DISPLAY"),
        "WAYLAND_DISPLAY": os.environ.get("WAYLAND_DISPLAY"),
        "XDG_SESSION_TYPE": os.environ.get("XDG_SESSION_TYPE"),
        "XDG_CURRENT_DESKTOP": os.environ.get("XDG_CURRENT_DESKTOP"),
        "USERNAME": os.environ.get("USERNAME") or os.environ.get("USER"),
    }

    # 5. Detected GUI apps sample count
    detected_apps: List[str] = []
    try:
        if CURRENT_OS == "Windows" and PYWIN32_AVAILABLE:
            windows = get_gui_windows_pywin32()
            detected_apps = list(windows.values())
        else:
            for proc in psutil.process_iter(["pid", "name"]):
                if is_gui_application(proc):
                    detected_apps.append(proc.name())
    except Exception as e:
        logger.debug("Error sampling GUI apps during diagnostics: %s", e)

    # 6. Observations / Notes
    notes: List[str] = []
    if CURRENT_OS == "Windows":
        if PYWIN32_AVAILABLE:
            notes.append("Windows: pywin32 is active (WM_CLOSE graceful window closing supported).")
        else:
            notes.append("Windows: pywin32 not found. Falling back to psutil process heuristics and SIGTERM/terminate.")
    elif CURRENT_OS == "Linux":
        notes.append("Linux: Tray backend uses AppIndicator/GTK/XEmbed. Ensure libayatana-appindicator3 is installed.")
        if not display_info["DISPLAY"] and not display_info["WAYLAND_DISPLAY"]:
            notes.append("Linux Warning: No DISPLAY or WAYLAND_DISPLAY environment variable detected.")
    elif CURRENT_OS == "Darwin":
        notes.append("macOS: AppKit tray backend active. Main-thread execution required for event loop.")
        notes.append("macOS: Accessibility permissions required for window closing and automation.")

    if not os_info["is_admin_or_root"]:
        notes.append("Note: Running without administrator/root privileges (GUI closing works; OS shutdown requires elevation).")

    return {
        "os": os_info,
        "tray": tray_info,
        "process_tools": process_info,
        "display": display_info,
        "detected_gui_apps_count": len(detected_apps),
        "detected_gui_apps_sample": detected_apps[:10],
        "notes": notes,
    }


def print_system_diagnostics() -> None:
    """Print formatted system and platform capability diagnostic report."""
    diag = get_system_diagnostics()
    os_info = diag["os"]
    tray = diag["tray"]
    proc_tools = diag["process_tools"]
    display = diag["display"]

    print("=" * 60)
    print(" GTFB System & Platform Diagnostics Report")
    print("=" * 60)

    print("\n[Operating System]")
    print(f"  OS System:        {os_info['system']}")
    print(f"  OS Release:       {os_info['release']}")
    print(f"  OS Version:       {os_info['version']}")
    print(f"  Platform:         {os_info['platform']}")
    print(f"  Architecture:     {os_info['architecture']}")
    print(f"  Python Version:   {os_info['python_version']}")
    print(f"  Elevated Privs:   {'Yes (Admin/Root)' if os_info['is_admin_or_root'] else 'No (Standard User)'}")

    print("\n[System Tray Backend]")
    pystray_status = "Available" if tray.get("pystray_available") else "Missing"
    print(f"  pystray:          {pystray_status} (v{tray.get('pystray_version', 'N/A')})")
    print(f"  Tray Backend:     {tray.get('backend_module', 'None')}")
    pillow_status = "Available" if tray.get("pillow_available") else "Missing"
    print(f"  Pillow (PIL):     {pillow_status} (v{tray.get('pillow_version', 'N/A')})")

    print("\n[Process Inspection & Automation Tools]")
    print(f"  psutil:           {'Available' if proc_tools['psutil_available'] else 'Missing'} (v{proc_tools.get('psutil_version', 'N/A')})")
    print(f"  pywin32:          {'Available' if proc_tools['pywin32_available'] else 'Not Installed / Non-Windows'}")
    if os_info["system"] == "Linux":
        print(f"  xdotool:          {'Available' if proc_tools['xdotool_available'] else 'Not Installed'}")
        print(f"  wmctrl:           {'Available' if proc_tools['wmctrl_available'] else 'Not Installed'}")
    elif os_info["system"] == "Darwin":
        print(f"  osascript:        {'Available' if proc_tools['osascript_available'] else 'Not Installed'}")

    print("\n[Display & Session Environment]")
    print(f"  User:             {display.get('USERNAME', 'Unknown')}")
    if os_info["system"] == "Linux":
        print(f"  DISPLAY:          {display.get('DISPLAY') or 'Not set'}")
        print(f"  WAYLAND_DISPLAY:  {display.get('WAYLAND_DISPLAY') or 'Not set'}")
        print(f"  Session Type:     {display.get('XDG_SESSION_TYPE') or 'Not set'}")
        print(f"  Desktop:          {display.get('XDG_CURRENT_DESKTOP') or 'Not set'}")

    print("\n[Detected GUI Applications]")
    print(f"  Active GUI Apps:  {diag['detected_gui_apps_count']}")
    if diag["detected_gui_apps_sample"]:
        for app_title in diag["detected_gui_apps_sample"][:5]:
            print(f"    - {app_title}")
        if diag["detected_gui_apps_count"] > 5:
            print(f"    ... and {diag['detected_gui_apps_count'] - 5} more")

    print("\n[Platform Notes & Recommendations]")
    for note in diag["notes"]:
        print(f"  * {note}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_system_diagnostics()

