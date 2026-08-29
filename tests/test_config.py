"""Unit tests for configuration schema models, serialization, and disk storage."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from gtfb.config import (
    DEFAULT_GRACE_PERIOD_SECONDS,
    DEFAULT_LOG_FILE,
    DEFAULT_SHUTDOWN_DELAY_SECONDS,
    DEFAULT_TARGET_HOUR,
    DEFAULT_TARGET_MINUTE,
    LINUX_GUI_PATTERNS,
    MACOS_GUI_PATTERNS,
    SYSTEM_EXCLUDED_PROCESSES,
    AppCloseSchedule,
    BlockRule,
    ConfigProfile,
    OverridePolicy,
    get_config_dir,
    get_config_path,
    get_log_path,
    load_config,
    save_config,
    setup_logging,
)


class TestConfigModels(unittest.TestCase):
    """Tests for ConfigProfile and nested dataclass models."""

    def test_default_app_close_schedule(self):
        schedule = AppCloseSchedule()
        self.assertEqual(schedule.target_hour, 22)
        self.assertEqual(schedule.target_minute, 0)
        self.assertTrue(schedule.enabled)
        self.assertEqual(schedule.grace_period_seconds, 15)
        self.assertTrue(schedule.force_kill_after_grace)

    def test_default_block_rule(self):
        rule = BlockRule()
        self.assertEqual(rule.trigger_type, "recurring")
        self.assertEqual(rule.start_hour, 22)
        self.assertEqual(rule.start_minute, 0)
        self.assertEqual(rule.end_hour, 6)
        self.assertEqual(rule.end_minute, 0)
        self.assertTrue(rule.active)
        self.assertIn("reddit.com", rule.domains)
        self.assertIn("youtube.com", rule.domains)
        self.assertIn("x.com", rule.domains)
        self.assertIn("twitter.com", rule.domains)
        self.assertIn("instagram.com", rule.domains)
        self.assertIn("tiktok.com", rule.domains)

    def test_default_override_policy(self):
        policy = OverridePolicy()
        self.assertEqual(policy.friction_type, "none")
        self.assertEqual(policy.cooldown_minutes, 0)

    def test_default_config_profile(self):
        profile = ConfigProfile()
        self.assertEqual(profile.version, 1)
        self.assertEqual(profile.profile_name, "Default")
        self.assertIsInstance(profile.app_close_schedule, AppCloseSchedule)
        self.assertEqual(profile.app_close_schedule.target_hour, 22)
        self.assertEqual(len(profile.block_rules), 1)
        self.assertIsInstance(profile.block_rules[0], BlockRule)
        self.assertIsInstance(profile.override_policy, OverridePolicy)

    def test_to_dict_and_from_dict_roundtrip(self):
        profile = ConfigProfile(
            version=2,
            profile_name="StrictNight",
            app_close_schedule=AppCloseSchedule(
                target_hour=23,
                target_minute=30,
                enabled=False,
                grace_period_seconds=30,
                force_kill_after_grace=False,
            ),
            block_rules=[
                BlockRule(
                    domains=["facebook.com", "twitch.tv"],
                    trigger_type="timer",
                    start_hour=20,
                    start_minute=15,
                    end_hour=8,
                    end_minute=45,
                    active=False,
                )
            ],
            override_policy=OverridePolicy(
                friction_type="typing_challenge",
                cooldown_minutes=15,
            ),
        )

        data_dict = profile.to_dict()
        reconstructed = ConfigProfile.from_dict(data_dict)

        self.assertEqual(reconstructed.version, 2)
        self.assertEqual(reconstructed.profile_name, "StrictNight")
        self.assertEqual(reconstructed.app_close_schedule.target_hour, 23)
        self.assertEqual(reconstructed.app_close_schedule.target_minute, 30)
        self.assertFalse(reconstructed.app_close_schedule.enabled)
        self.assertEqual(reconstructed.app_close_schedule.grace_period_seconds, 30)
        self.assertFalse(reconstructed.app_close_schedule.force_kill_after_grace)
        self.assertEqual(len(reconstructed.block_rules), 1)
        self.assertEqual(
            reconstructed.block_rules[0].domains, ["facebook.com", "twitch.tv"]
        )
        self.assertEqual(reconstructed.block_rules[0].trigger_type, "timer")
        self.assertEqual(reconstructed.block_rules[0].start_hour, 20)
        self.assertEqual(reconstructed.block_rules[0].start_minute, 15)
        self.assertEqual(reconstructed.block_rules[0].end_hour, 8)
        self.assertEqual(reconstructed.block_rules[0].end_minute, 45)
        self.assertFalse(reconstructed.block_rules[0].active)
        self.assertEqual(reconstructed.override_policy.friction_type, "typing_challenge")
        self.assertEqual(reconstructed.override_policy.cooldown_minutes, 15)

    def test_to_json_and_from_json(self):
        profile = ConfigProfile()
        json_str = profile.to_json()
        parsed = json.loads(json_str)

        self.assertEqual(parsed["version"], 1)
        self.assertEqual(parsed["profile_name"], "Default")
        self.assertIn("app_close_schedule", parsed)
        self.assertIn("block_rules", parsed)
        self.assertIn("override_policy", parsed)

        reconstructed = ConfigProfile.from_json(json_str)
        self.assertEqual(reconstructed.profile_name, "Default")
        self.assertEqual(reconstructed.app_close_schedule.target_hour, 22)

    def test_from_dict_with_missing_and_malformed_fields(self):
        # Empty dict fallback
        empty_profile = ConfigProfile.from_dict({})
        self.assertEqual(empty_profile.version, 1)
        self.assertEqual(empty_profile.profile_name, "Default")
        self.assertEqual(empty_profile.app_close_schedule.target_hour, 22)
        self.assertEqual(len(empty_profile.block_rules), 1)

        # None input fallback
        none_profile = ConfigProfile.from_dict(None)
        self.assertEqual(none_profile.version, 1)
        self.assertEqual(none_profile.profile_name, "Default")

        # Partial fields with already instantiated objects
        mixed = ConfigProfile.from_dict(
            {
                "version": 3,
                "profile_name": "Custom",
                "app_close_schedule": AppCloseSchedule(target_hour=21),
                "block_rules": [BlockRule(domains=["example.com"])],
                "override_policy": OverridePolicy(friction_type="delay"),
            }
        )
        self.assertEqual(mixed.version, 3)
        self.assertEqual(mixed.app_close_schedule.target_hour, 21)
        self.assertEqual(mixed.block_rules[0].domains, ["example.com"])
        self.assertEqual(mixed.override_policy.friction_type, "delay")


class TestConfigStorage(unittest.TestCase):
    """Tests for config path resolution, save_config, and load_config."""

    def test_get_config_dir_windows_with_env(self):
        with patch("sys.platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": "C:\\MockAppData"}):
                config_dir = get_config_dir()
                self.assertEqual(config_dir, Path("C:\\MockAppData\\GTFB"))

    def test_get_config_dir_windows_without_env(self):
        with patch("sys.platform", "win32"):
            with patch.dict(os.environ, {}, clear=True):
                with patch("pathlib.Path.home", return_value=Path("C:\\Users\\Test")):
                    config_dir = get_config_dir()
                    self.assertEqual(
                        config_dir, Path("C:\\Users\\Test\\AppData\\Roaming\\GTFB")
                    )

    def test_get_config_dir_macos(self):
        with patch("sys.platform", "darwin"):
            with patch("pathlib.Path.home", return_value=Path("/Users/test")):
                config_dir = get_config_dir()
                self.assertEqual(
                    config_dir, Path("/Users/test/Library/Application Support/GTFB")
                )

    def test_get_config_dir_linux_with_xdg(self):
        with patch("sys.platform", "linux"):
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/custom/xdg"}):
                config_dir = get_config_dir()
                self.assertEqual(config_dir, Path("/custom/xdg/gtfb"))

    def test_get_config_dir_linux_default(self):
        with patch("sys.platform", "linux"):
            with patch.dict(os.environ, {}, clear=True):
                with patch("pathlib.Path.home", return_value=Path("/home/test")):
                    config_dir = get_config_dir()
                    self.assertEqual(config_dir, Path("/home/test/.config/gtfb"))

    def test_get_config_path(self):
        with patch("sys.platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": "C:\\MockAppData"}):
                config_path = get_config_path()
                self.assertEqual(config_path, Path("C:\\MockAppData\\GTFB\\config.json"))
                custom_path = get_config_path("custom.json", app_name="MyBedtime")
                self.assertEqual(
                    custom_path, Path("C:\\MockAppData\\MyBedtime\\custom.json")
                )

    def test_save_and_load_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "subdir" / "test_config.json"

            profile = ConfigProfile(
                profile_name="SavedProfile",
                app_close_schedule=AppCloseSchedule(target_hour=23, target_minute=45),
            )

            saved_path = save_config(profile, file_path)
            self.assertTrue(saved_path.exists())

            loaded_profile = load_config(file_path)
            self.assertEqual(loaded_profile.profile_name, "SavedProfile")
            self.assertEqual(loaded_profile.app_close_schedule.target_hour, 23)
            self.assertEqual(loaded_profile.app_close_schedule.target_minute, 45)

    def test_load_config_creates_default_when_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "nested" / "non_existent_config.json"
            self.assertFalse(file_path.exists())

            profile = load_config(file_path)
            self.assertEqual(profile.profile_name, "Default")
            self.assertEqual(profile.app_close_schedule.target_hour, 22)
            self.assertTrue(file_path.exists())


    def test_get_log_path_resolves_to_config_dir(self):
        log_path = get_log_path()
        config_dir = get_config_dir()
        self.assertEqual(log_path, config_dir / "bedtime.log")
        self.assertEqual(log_path.name, "bedtime.log")

    def test_setup_logging_creates_parent_dir_and_file_handler(self):
        import logging
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_log = Path(tmpdir) / "appdata_sim" / "bedtime.log"
            self.assertFalse(custom_log.parent.exists())

            # Test setup_logging with non-existent parent directory
            with patch("logging.getLogger") as mock_get_logger:
                mock_root = MagicMock()
                mock_root.handlers = []
                mock_get_logger.return_value = mock_root

                setup_logging(log_file=custom_log)
                self.assertTrue(custom_log.parent.exists())
                self.assertTrue(mock_root.addHandler.called)

                # Close file handlers to release file lock on Windows
                for call in mock_root.addHandler.call_args_list:
                    handler = call[0][0]
                    if hasattr(handler, "close"):
                        handler.close()


class TestConfigReExports(unittest.TestCase):
    """Tests ensuring backwards compatibility with legacy gtfb.config imports."""

    def test_constants_and_logging_exported(self):
        self.assertEqual(DEFAULT_TARGET_HOUR, 22)
        self.assertEqual(DEFAULT_TARGET_MINUTE, 0)
        self.assertEqual(DEFAULT_GRACE_PERIOD_SECONDS, 3.0)
        self.assertEqual(DEFAULT_SHUTDOWN_DELAY_SECONDS, 30)
        self.assertEqual(DEFAULT_LOG_FILE, "bedtime.log")
        self.assertTrue(callable(setup_logging))
        self.assertTrue(callable(get_log_path))
        self.assertIsInstance(SYSTEM_EXCLUDED_PROCESSES, list)
        self.assertIsInstance(LINUX_GUI_PATTERNS, list)
        self.assertIsInstance(MACOS_GUI_PATTERNS, list)


if __name__ == "__main__":
    unittest.main()
