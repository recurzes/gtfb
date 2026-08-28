"""Disk storage and discovery helpers for GTFB configuration."""

import json
import logging
import os
from pathlib import Path
import sys
from typing import Optional, Union

from gtfb.config.models import ConfigProfile

logger = logging.getLogger(__name__)


def get_config_dir(app_name: str = "GTFB") -> Path:
    """Return OS-standard user configuration directory.

    - Windows: %APPDATA%/GTFB or ~/AppData/Roaming/GTFB
    - macOS: ~/Library/Application Support/GTFB
    - Linux / other: $XDG_CONFIG_HOME/gtfb or ~/.config/gtfb
    """
    if sys.platform.startswith("win"):
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / app_name.lower()
        return Path.home() / ".config" / app_name.lower()


def get_config_path(filename: str = "config.json", app_name: str = "GTFB") -> Path:
    """Return full path to the configuration JSON file."""
    return get_config_dir(app_name=app_name) / filename


def save_config(
    profile: ConfigProfile, path: Optional[Union[str, Path]] = None
) -> Path:
    """Save ConfigProfile to a JSON file on disk."""
    target_path = Path(path) if path is not None else get_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(profile.to_json(indent=2))
    logger.info("Saved configuration to %s", target_path)
    return target_path


def load_config(path: Optional[Union[str, Path]] = None) -> ConfigProfile:
    """Load ConfigProfile from JSON file.

    If file does not exist, instantiate default ConfigProfile, save to disk, and return it.
    """
    target_path = Path(path) if path is not None else get_config_path()
    if not target_path.exists():
        logger.info(
            "Configuration file %s does not exist. Creating default.", target_path
        )
        default_profile = ConfigProfile()
        save_config(default_profile, target_path)
        return default_profile

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return ConfigProfile.from_dict(data)
