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
from gtfb.config.sanitizer import clean_domain_input
from gtfb.config.storage import (
    get_app_dir,
    get_config_dir,
    get_config_path,
    get_log_path,
    load_config,
    load_config_resilient,
    save_config,
    save_config_atomic,
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
    "clean_domain_input",
    "get_app_dir",
    "get_config_dir",
    "get_config_path",
    "get_log_path",
    "load_config",
    "load_config_resilient",
    "save_config",
    "save_config_atomic",
]
