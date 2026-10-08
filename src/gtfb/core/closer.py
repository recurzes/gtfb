"""Process management and graceful application closing utilities."""

import logging
import os
from datetime import datetime
from typing import List, Optional, Set, Tuple

import psutil

from gtfb.config import (
    DEFAULT_GRACE_PERIOD_SECONDS,
    DEFAULT_SHUTDOWN_DELAY_SECONDS,
    DEFAULT_TARGET_HOUR,
    DEFAULT_TARGET_MINUTE,
    SYSTEM_EXCLUDED_PROCESSES,
)
from gtfb.core import platform_utils
from gtfb.core.platform_utils import (
    get_gui_windows_pywin32,
    is_gui_application,
)

logger = logging.getLogger("gtfb.core.closer")


def close_application_gracefully_windows(proc: psutil.Process, window_title: Optional[str] = None) -> bool:
    """Attempt to close a Windows application gracefully by sending WM_CLOSE to its windows.

    Falls back to proc.terminate() if pywin32 is not available or WM_CLOSE fails.
    """
    if not platform_utils.PYWIN32_AVAILABLE:
        proc.terminate()
        return False

    try:
        import win32con
        import win32gui
        import win32process

        def find_window_callback(hwnd: int, target_pid: int) -> bool:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == target_pid:
                if win32gui.IsWindowVisible(hwnd):
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    return False
            return True

        win32gui.EnumWindows(lambda hwnd, pid: find_window_callback(hwnd, pid), proc.pid)
        return True
    except Exception as e:
        logger.debug("WM_CLOSE failed for PID %s (%s): %s", proc.pid, window_title, e)
        proc.terminate()
        return False


def _request_close(proc: psutil.Process, window_title: Optional[str] = None) -> None:
    """Ask a process to close: WM_CLOSE on Windows with pywin32, terminate otherwise."""
    if platform_utils.CURRENT_OS == "Windows" and platform_utils.PYWIN32_AVAILABLE:
        close_application_gracefully_windows(proc, window_title)
    else:
        proc.terminate()


def close_application(
    proc: psutil.Process,
    window_title: Optional[str] = None,
    timeout: float = DEFAULT_GRACE_PERIOD_SECONDS,
    force_kill: bool = True,
) -> bool:
    """Close a single process gracefully, escalating to force kill if unresponsive."""
    proc_name = proc.name()
    try:
        _request_close(proc, window_title)

        try:
            proc.wait(timeout=timeout)
            print(f"Closed gracefully: {proc_name}")
            return True
        except psutil.TimeoutExpired:
            if not force_kill:
                print(f"Still running after grace period: {proc_name}")
                return False
            proc.kill()
            print(f"Force closed: {proc_name}")
            return True
    except (psutil.AccessDenied, psutil.NoSuchProcess, PermissionError):
        return False


def _protected_pids() -> Set[int]:
    """Return PIDs that must never be closed: this process and every ancestor.

    Ancestors cover the terminal or shell hosting a CLI run, whose closure would
    kill GTFB before it finishes closing other applications or shutting down.
    """
    pids: Set[int] = {os.getpid()}
    try:
        pids.update(parent.pid for parent in psutil.Process().parents())
    except psutil.Error as err:
        logger.debug("Could not resolve parent processes: %s", err)
    return pids


def get_running_gui_apps() -> List[Tuple[psutil.Process, str]]:
    """Scan and return a list of running GUI applications as (Process, title_or_name) tuples."""
    apps: List[Tuple[psutil.Process, str]] = []
    protected = _protected_pids()

    if platform_utils.CURRENT_OS == "Windows" and platform_utils.PYWIN32_AVAILABLE:
        gui_windows = get_gui_windows_pywin32()
        for pid, title in gui_windows.items():
            if pid in protected:
                continue
            try:
                proc = psutil.Process(pid)
                proc_name = proc.name().lower()
                if proc_name in SYSTEM_EXCLUDED_PROCESSES:
                    continue
                apps.append((proc, title))
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue
    else:
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.pid in protected:
                continue
            try:
                if is_gui_application(proc):
                    apps.append((proc, proc.name()))
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue

    return apps


def close_gui_applications(
    dry_run: bool = False,
    grace_period: float = DEFAULT_GRACE_PERIOD_SECONDS,
    force_kill: bool = True,
) -> List[str]:
    """Identify and close all running GUI applications gracefully.

    Every application is asked to close first, then all of them share a single
    grace period before the ones still running are force killed.

    Args:
        dry_run: If True, only scan and return detected GUI applications without terminating them.
        grace_period: Seconds to wait for applications to exit after the close request.
        force_kill: If True, kill applications still running after the grace period.

    Returns:
        List[str]: List of application names that were closed (or detected in dry-run).
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting to close GUI applications...")
    print("    (Only closing apps from 'Apps' tab, not background processes)\n")

    close_apps: List[str] = []

    gui_apps = get_running_gui_apps()
    print(f"Found {len(gui_apps)} GUI applications to close\n")

    pending: List[Tuple[psutil.Process, str]] = []
    for proc, title in gui_apps:
        try:
            proc_name = proc.name()
            if dry_run:
                print(f"    [DRY RUN] Would close: {proc_name} - '{title}' (PID: {proc.pid})")
                close_apps.append(proc_name)
            else:
                print(f"    Closing: {proc_name} - '{title}' (PID: {proc.pid})")
                logger.info("Requesting close: %s (PID %s) - '%s'", proc_name, proc.pid, title)
                _request_close(proc, title)
                pending.append((proc, proc_name))
        except (psutil.AccessDenied, psutil.NoSuchProcess, PermissionError):
            pass

    if pending:
        names = {proc.pid: name for proc, name in pending}
        gone, alive = psutil.wait_procs([proc for proc, _ in pending], timeout=grace_period)

        for proc in gone:
            print(f"Closed gracefully: {names[proc.pid]}")
            logger.info("Closed gracefully: %s (PID %s)", names[proc.pid], proc.pid)
            close_apps.append(names[proc.pid])

        for proc in alive:
            name = names[proc.pid]
            if not force_kill:
                print(f"Still running after grace period: {name}")
                logger.info("Left running after %ss grace period: %s (PID %s)", grace_period, name, proc.pid)
                continue
            try:
                proc.kill()
                print(f"Force closed: {name}")
                logger.info("Force closed after %ss grace period: %s (PID %s)", grace_period, name, proc.pid)
                close_apps.append(name)
            except (psutil.AccessDenied, psutil.NoSuchProcess, PermissionError):
                pass

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Application closing complete.")
    print(f"  {'Detected' if dry_run else 'Closed'} {len(close_apps)} GUI applications")

    if close_apps:
        print(f"\n Apps {'detected' if dry_run else 'closed'}: {', '.join(set(close_apps))}")

    return close_apps


# Alias for concise import
close_gui_apps = close_gui_applications



def shutdown_system(
    target_hour: int = DEFAULT_TARGET_HOUR,
    target_minute: int = DEFAULT_TARGET_MINUTE,
    delay_seconds: int = DEFAULT_SHUTDOWN_DELAY_SECONDS,
) -> None:
    """Initiate an OS-level system shutdown."""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Initiating system shutdown....")
    message = f"Scheduled shutdown at {target_hour:02d}:{target_minute:02d}"

    if platform_utils.CURRENT_OS == "Windows":
        print(f"System will shut down in {delay_seconds} seconds.")
        os.system(f'shutdown /s /t {delay_seconds} /c "{message}"')
    elif platform_utils.CURRENT_OS == "Linux":
        print("System will shut down in 1 minute")
        print("Note: This requires sudo privileges")
        os.system(f"shutdown -h +1 '{message}'")
    elif platform_utils.CURRENT_OS == "Darwin":
        print("System will shut down in 1 minute")
        print("Note: This requires sudo privileges")
        os.system(f"sudo shutdown -h +1 '{message}'")
    else:
        print(f"Error: Unsupported operating system '{platform_utils.CURRENT_OS}'")


def check_privileges() -> None:
    """Check required OS privileges on Unix-based systems."""
    if platform_utils.CURRENT_OS in ["Linux", "Darwin"]:
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            print(f"\nWarning: Running on {platform_utils.CURRENT_OS} without root privileges")
            print("The scripts can close applications but may not shutdown the system")
            print(f"To enable shutdown, run: sudo python3 {os.path.basename(__file__)}\n")
            response = input("Continue anyway? (y/n): ")
            if response.lower() != "y":
                print("Exiting...")
                exit(0)
