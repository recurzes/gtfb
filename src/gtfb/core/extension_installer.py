"""Core utilities for bundling, deploying, and installing the GTFB browser extension."""

import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
import webbrowser

from gtfb.config.storage import get_config_dir

logger = logging.getLogger(__name__)

MARKER_FILENAME = ".first_run_done"


def get_bundled_extension_path() -> Optional[Path]:
    """Locate the bundled extension directory in frozen executable or source repository."""
    candidates = []

    # 1. PyInstaller _MEIPASS bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.append(Path(sys._MEIPASS) / "extension")

    # 2. Relative to package root / repository root
    pkg_dir = Path(__file__).resolve().parent.parent
    candidates.append(pkg_dir.parent.parent / "extension")
    candidates.append(pkg_dir.parent / "extension")
    candidates.append(pkg_dir / "extension")

    # 3. Current working directory fallback
    candidates.append(Path("extension"))
    candidates.append(Path.cwd() / "extension")

    for cand in candidates:
        if cand.is_dir() and (cand / "manifest.json").is_file():
            return cand.resolve()

    return None


def get_installed_extension_dir() -> Path:
    """Return the permanent user storage directory where the extension is deployed."""
    return get_config_dir() / "extension"


def deploy_extension_files(target_dir: Optional[Path] = None) -> Path:
    """Copy bundled extension files to persistent user storage directory."""
    destination = target_dir or get_installed_extension_dir()
    destination.mkdir(parents=True, exist_ok=True)

    source_dir = get_bundled_extension_path()
    if not source_dir or not source_dir.exists():
        logger.warning("Bundled extension source not found. Creating placeholder directory.")
        return destination

    # Copy files from source to destination
    for item in source_dir.rglob("*"):
        if item.is_dir():
            continue
        rel_path = item.relative_to(source_dir)
        dest_path = destination / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(item, dest_path)
        except Exception as err:
            logger.debug("Failed copying %s to %s: %s", item, dest_path, err)

    logger.info("Deployed GTFB extension to %s", destination)
    return destination


def detect_installed_browsers() -> Dict[str, Dict[str, Any]]:
    """Detect popular web browsers installed on the host system."""
    browsers: Dict[str, Dict[str, Any]] = {
        "chrome": {
            "name": "Google Chrome",
            "type": "chromium",
            "ext_url": "chrome://extensions",
            "paths": [
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            ],
            "installed": False,
            "exe": None,
        },
        "edge": {
            "name": "Microsoft Edge",
            "type": "chromium",
            "ext_url": "edge://extensions",
            "paths": [
                os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            ],
            "installed": False,
            "exe": None,
        },
        "brave": {
            "name": "Brave Browser",
            "type": "chromium",
            "ext_url": "brave://extensions",
            "paths": [
                os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ],
            "installed": False,
            "exe": None,
        },
        "firefox": {
            "name": "Mozilla Firefox",
            "type": "firefox",
            "ext_url": "about:debugging#/runtime/this-firefox",
            "paths": [
                os.path.expandvars(r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe"),
                os.path.expandvars(r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe"),
                os.path.expandvars(r"%LOCALAPPDATA%\Mozilla Firefox\firefox.exe"),
            ],
            "installed": False,
            "exe": None,
        },
        "opera": {
            "name": "Opera",
            "type": "chromium",
            "ext_url": "opera://extensions",
            "paths": [
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\launcher.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Opera\launcher.exe"),
            ],
            "installed": False,
            "exe": None,
        },
    }

    # Verify existing binaries
    for key, info in browsers.items():
        for p in info["paths"]:
            if p and Path(p).is_file():
                info["installed"] = True
                info["exe"] = Path(p)
                break

    return browsers


def is_first_run_completed() -> bool:
    """Check if the first-time installation/consent setup has already been handled."""
    marker_path = get_config_dir() / MARKER_FILENAME
    return marker_path.exists()




def set_first_run_completed(completed: bool = True) -> None:
    """Set the first-run marker status."""
    marker_path = get_config_dir() / MARKER_FILENAME
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    if completed:
        try:
            marker_path.write_text("installed=true\n", encoding="utf-8")
        except Exception as err:
            logger.warning("Could not write first run marker: %s", err)
    else:
        if marker_path.exists():
            try:
                marker_path.unlink()
            except OSError:
                pass


def set_system_clipboard(text: str) -> bool:
    """Safely copy text to system clipboard across threads without creating temporary Tk roots."""
    if sys.platform.startswith("win"):
        try:
            import ctypes

            OpenClipboard = ctypes.windll.user32.OpenClipboard
            EmptyClipboard = ctypes.windll.user32.EmptyClipboard
            SetClipboardData = ctypes.windll.user32.SetClipboardData
            CloseClipboard = ctypes.windll.user32.CloseClipboard
            GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
            GlobalLock = ctypes.windll.kernel32.GlobalLock
            GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
            GMEM_MOVEABLE = 0x0002
            CF_UNICODETEXT = 13

            if OpenClipboard(None):
                try:
                    EmptyClipboard()
                    encoded = text.encode("utf-16-le") + b"\x00\x00"
                    h_mem = GlobalAlloc(GMEM_MOVEABLE, len(encoded))
                    if h_mem:
                        p_mem = GlobalLock(h_mem)
                        if p_mem:
                            ctypes.memmove(p_mem, encoded, len(encoded))
                            GlobalUnlock(h_mem)
                            SetClipboardData(CF_UNICODETEXT, h_mem)
                            return True
                finally:
                    CloseClipboard()
        except Exception as err:
            logger.debug("Native Win32 clipboard write failed: %s", err)

        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{text}'"],
                check=False,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True
        except Exception as ps_err:
            logger.debug("Failed copying via powershell: %s", ps_err)

    return False


def copy_extension_path_to_clipboard(path: Optional[Path] = None) -> bool:
    """Copy the extension folder path to the system clipboard."""
    target_path = str(path or get_installed_extension_dir())
    return set_system_clipboard(target_path)



def open_browser_extension_page(browser_key: str, detected_browsers: Optional[Dict[str, Any]] = None) -> bool:
    """Open the extension management page in the specified browser."""
    browsers = detected_browsers or detect_installed_browsers()
    browser_info = browsers.get(browser_key)
    if not browser_info:
        return False

    ext_url = browser_info.get("ext_url", "")
    exe = browser_info.get("exe")

    if exe and Path(exe).is_file():
        try:
            subprocess.Popen([str(exe), ext_url], shell=False)
            return True
        except Exception as err:
            logger.warning("Failed launching %s with %s: %s", exe, ext_url, err)

    try:
        webbrowser.open(ext_url)
        return True
    except Exception as err:
        logger.warning("Failed opening browser URL %s: %s", ext_url, err)
        return False


def open_folder_in_explorer(folder_path: Optional[Path] = None) -> bool:
    """Open folder in Windows File Explorer or platform default file manager."""
    target = folder_path or get_installed_extension_dir()
    target.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(target))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except Exception as err:
        logger.warning("Failed opening folder %s: %s", target, err)
        return False
