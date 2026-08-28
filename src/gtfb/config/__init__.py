"""Configuration models, storage, defaults, and logging setup for GTFB."""

from gtfb.config.defaults import (
    DEFAULT_GRACE_PERIOD_SECONDS,
    DEFAULT_LOG_FILE,
    DEFAULT_SHUTDOWN_DELAY_SECONDS,
    DEFAULT_TARGET_HOUR,
    DEFAULT_TARGET_MINUTE,
    LINUX_GUI_PATTERNS,
    MACOS_GUI_PATTERNS,
    SYSTEM_EXCLUDED_PROCESSES,
    setup_logging,
)
from gtfb.config.models import (
    AppCloseSchedule,
    BlockRule,
    ConfigProfile,
    OverridePolicy,
)
from gtfb.config.storage import (
    get_config_dir,
    get_config_path,
    load_config,
    save_config,
)

__all__ = [
    "DEFAULT_GRACE_PERIOD_SECONDS",
    "DEFAULT_LOG_FILE",
    "DEFAULT_SHUTDOWN_DELAY_SECONDS",
    "DEFAULT_TARGET_HOUR",
    "DEFAULT_TARGET_MINUTE",
    "LINUX_GUI_PATTERNS",
    "MACOS_GUI_PATTERNS",
    "SYSTEM_EXCLUDED_PROCESSES",
    "setup_logging",
    "AppCloseSchedule",
    "BlockRule",
    "ConfigProfile",
    "OverridePolicy",
    "get_config_dir",
    "get_config_path",
    "load_config",
    "save_config",
]
