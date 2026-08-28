"""UI components and system tray integration for GTFB."""

from gtfb.ui.icons import (
    STATE_COLORS,
    create_state_icon,
    generate_fallback_icon,
    get_icon,
    load_tray_icon,
)
from gtfb.ui.settings_window import BedtimeSection, SettingsWindow
from gtfb.ui.tray import TrayApp

__all__ = [
    "STATE_COLORS",
    "BedtimeSection",
    "SettingsWindow",
    "TrayApp",
    "create_state_icon",
    "generate_fallback_icon",
    "get_icon",
    "load_tray_icon",
]

