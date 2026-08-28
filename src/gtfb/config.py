import logging
from pathlib import Path
from typing import Optional, Union

DEFAULT_TARGET_HOUR: int = 22
DEFAULT_TARGET_MINUTE: int = 0
DEFAULT_GRACE_PERIOD_SECONDS: float = 3.0
DEFAULT_SHUTDOWN_DELAY_SECONDS: int = 30
DEFAULT_LOG_FILE: str = "bedtime.log"


def setup_logging(
    log_file: Optional[Union[str, Path]] = DEFAULT_LOG_FILE,
    level: int = logging.INFO,
) -> None:
    """Configure root logging to output to both console and a log file."""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    root_logger.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_file:
        file_path = Path(log_file)
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


# Processes that should never be identified or closed as user GUI applications
SYSTEM_EXCLUDED_PROCESSES: list[str] = [
    "system",
    "registry",
    "csrss.exe",
    "smss.exe",
    "services.exe",
    "lsass.exe",
    "winlogon.exe",
    "svchost.exe",
    "explorer.exe",
    "dwm.exe",
    "taskmgr.exe",
    "systemd",
    "init",
    "launchd",
    "kernel_task",
    "windowserver",
    "loginwindow",
    "finder",
    "dock",
]

# Common Linux GUI application keywords/patterns
LINUX_GUI_PATTERNS: list[str] = [
    "chrome",
    "firefox",
    "brave",
    "edge",
    "opera",
    "vivaldi",
    "code",
    "atom",
    "sublime",
    "gedit",
    "kate",
    "geany",
    "libreoffice",
    "gimp",
    "inkscape",
    "blender",
    "discord",
    "slack",
    "telegram",
    "signal",
    "zoom",
    "spotify",
    "vlc",
    "mpv",
    "totem",
    "nautilus",
    "dolphin",
    "thunar",
    "pcmanfm",
    "nemo",
    "calculator",
    "gnome-",
    "kde-",
    "plasma-",
    "thunderbird",
    "evolution",
    "geary",
]

# Common macOS GUI application keywords/patterns
MACOS_GUI_PATTERNS: list[str] = [
    "safari",
    "chrome",
    "firefox",
    "brave",
    "edge",
    "opera",
    "code",
    "xcode",
    "atom",
    "sublime",
    "textedit",
    "pages",
    "numbers",
    "keynote",
    "office",
    "word",
    "excel",
    "powerpoint",
    "discord",
    "slack",
    "telegram",
    "signal",
    "zoom",
    "facetime",
    "spotify",
    "music",
    "itunes",
    "vlc",
    "quicktime",
    "photos",
    "preview",
    "mail",
    "messages",
    "notes",
    "reminders",
    "calendar",
    "contacts",
    "calculator",
    "activity monitor",
]
