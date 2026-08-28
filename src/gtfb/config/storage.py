"""Disk storage and discovery helpers for GTFB configuration."""

import json
import logging
import os
from pathlib import Path
import shutil
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


get_app_dir = get_config_dir


def get_config_path(filename: str = "config.json", app_name: str = "GTFB") -> Path:
    """Return full path to the configuration JSON file."""
    return get_config_dir(app_name=app_name) / filename


def save_config_atomic(
    profile: ConfigProfile, path: Optional[Union[str, Path]] = None
) -> Path:
    """Save ConfigProfile to a JSON file atomically with hardware flush and backup creation."""
    target_path = Path(path) if path is not None else get_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    temp_file = target_path.with_suffix(".tmp")
    bak_file = target_path.with_suffix(".bak")

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        if target_path.exists():
            try:
                if bak_file.exists():
                    bak_file.unlink()
                shutil.copy2(target_path, bak_file)
            except Exception as e:
                logger.warning("Could not update backup config file: %s", e)

        os.replace(temp_file, target_path)
        logger.info("Successfully saved configuration atomically to %s", target_path)
        return target_path
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def save_config(
    profile: ConfigProfile, path: Optional[Union[str, Path]] = None
) -> Path:
    """Save ConfigProfile to a JSON file on disk."""
    return save_config_atomic(profile, path)


def load_config_resilient(path: Optional[Union[str, Path]] = None) -> ConfigProfile:
    """Load ConfigProfile from disk with backup fallback and self-healing recovery.

    - If primary file is missing:
      - If backup exists, recover from backup and restore primary file.
      - Otherwise create and save default ConfigProfile.
    - If primary file is corrupt or invalid:
      - If backup exists and is valid, recover from backup and restore primary file.
      - Otherwise create and save default ConfigProfile.
    """
    target_path = Path(path) if path is not None else get_config_path()
    bak_file = target_path.with_suffix(".bak")

    if not target_path.exists():
        if bak_file.exists():
            try:
                with open(bak_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    profile = ConfigProfile.from_dict(data)
                    logger.info(
                        "Primary config missing; recovered configuration from backup file %s",
                        bak_file,
                    )
                    save_config_atomic(profile, target_path)
                    return profile
            except Exception as bak_err:
                logger.error(
                    "Backup file corrupt when recovering missing config (%s): %s",
                    bak_file,
                    bak_err,
                )

        default_profile = ConfigProfile()
        save_config_atomic(default_profile, target_path)
        return default_profile

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(
                f"Config root must be a dictionary, got {type(data).__name__}"
            )
        return ConfigProfile.from_dict(data)
    except Exception as err:
        logger.error(
            "Failed to load primary config (%s): %s. Checking backup.", target_path, err
        )

    if bak_file.exists():
        try:
            with open(bak_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError(
                    f"Backup config root must be a dictionary, got {type(data).__name__}"
                )
            profile = ConfigProfile.from_dict(data)
            logger.info("Successfully recovered configuration from backup file.")
            save_config_atomic(profile, target_path)
            return profile
        except Exception as bak_err:
            logger.error(
                "Backup file also corrupt: %s. Resetting to defaults.", bak_err
            )

    default_profile = ConfigProfile()
    save_config_atomic(default_profile, target_path)
    return default_profile


def load_config(path: Optional[Union[str, Path]] = None) -> ConfigProfile:
    """Load ConfigProfile from JSON file.

    If file does not exist or is corrupt, recover from backup or instantiate default ConfigProfile.
    """
    return load_config_resilient(path)
