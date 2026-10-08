"""Unit tests for atomic configuration storage and resilient corruption recovery."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from gtfb.config import (
    AppCloseSchedule,
    BlockRule,
    ConfigProfile,
    load_config,
    load_config_resilient,
    save_config,
    save_config_atomic,
)


class TestConfigAtomicStorage(unittest.TestCase):
    """Unit tests for atomic write behavior and temp file cleanup."""

    def test_save_config_atomic_initial_write(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"
            temp_file = Path(tmpdir) / "config.tmp"
            bak_file = Path(tmpdir) / "config.bak"

            profile = ConfigProfile(profile_name="InitialProfile")
            saved_path = save_config_atomic(profile, target_file)

            self.assertEqual(saved_path, target_file)
            self.assertTrue(target_file.exists())
            self.assertFalse(temp_file.exists())
            self.assertFalse(bak_file.exists())

            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["profile_name"], "InitialProfile")

    def test_save_config_atomic_creates_and_rotates_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"
            bak_file = Path(tmpdir) / "config.bak"

            profile_v1 = ConfigProfile(profile_name="Version1")
            save_config_atomic(profile_v1, target_file)
            self.assertFalse(bak_file.exists())

            profile_v2 = ConfigProfile(profile_name="Version2")
            save_config_atomic(profile_v2, target_file)
            self.assertTrue(bak_file.exists())

            with open(target_file, "r", encoding="utf-8") as f:
                primary_data = json.load(f)
            with open(bak_file, "r", encoding="utf-8") as f:
                bak_data = json.load(f)

            self.assertEqual(primary_data["profile_name"], "Version2")
            self.assertEqual(bak_data["profile_name"], "Version1")

            profile_v3 = ConfigProfile(profile_name="Version3")
            save_config_atomic(profile_v3, target_file)

            with open(target_file, "r", encoding="utf-8") as f:
                primary_data = json.load(f)
            with open(bak_file, "r", encoding="utf-8") as f:
                bak_data = json.load(f)

            self.assertEqual(primary_data["profile_name"], "Version3")
            self.assertEqual(bak_data["profile_name"], "Version2")

    def test_save_config_atomic_cleans_up_tmp_on_exception(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"
            temp_file = Path(tmpdir) / "config.tmp"

            profile = ConfigProfile(profile_name="FailureProfile")

            with patch("os.replace", side_effect=OSError("Simulated rename failure")):
                with self.assertRaises(OSError):
                    save_config_atomic(profile, target_file)

            # Ensure temp file was cleaned up by the finally block
            self.assertFalse(temp_file.exists())
            self.assertFalse(target_file.exists())

    def test_save_config_atomic_invokes_fsync(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"
            profile = ConfigProfile(profile_name="FsyncTest")

            with patch("os.fsync", wraps=os.fsync) as mock_fsync:
                save_config_atomic(profile, target_file)
                mock_fsync.assert_called_once()


class TestConfigResilientLoading(unittest.TestCase):
    """Unit tests for resilient loading, validation, and self-healing recovery."""

    def test_load_config_resilient_missing_file_creates_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "sub" / "config.json"
            self.assertFalse(target_file.exists())

            profile = load_config_resilient(target_file)
            self.assertIsInstance(profile, ConfigProfile)
            self.assertEqual(profile.profile_name, "Default")
            self.assertTrue(target_file.exists())

    def test_load_config_resilient_normal_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"
            profile = ConfigProfile(
                profile_name="CustomProfile",
                app_close_schedule=AppCloseSchedule(target_hour=23, target_minute=15),
            )
            save_config_atomic(profile, target_file)

            loaded = load_config_resilient(target_file)
            self.assertEqual(loaded.profile_name, "CustomProfile")
            self.assertEqual(loaded.app_close_schedule.target_hour, 23)
            self.assertEqual(loaded.app_close_schedule.target_minute, 15)

    def test_load_config_resilient_recovers_from_corrupted_primary_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"

            profile_good = ConfigProfile(
                profile_name="GoodProfile",
                app_close_schedule=AppCloseSchedule(target_hour=21, target_minute=45),
            )
            save_config_atomic(profile_good, target_file)

            profile_v2 = ConfigProfile(profile_name="UpdatedProfile")
            save_config_atomic(profile_v2, target_file)

            # Corrupt the primary config file with invalid JSON syntax
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("{invalid: json, truncated syntax...")

            loaded = load_config_resilient(target_file)
            self.assertEqual(loaded.profile_name, "GoodProfile")
            self.assertEqual(loaded.app_close_schedule.target_hour, 21)

            # Check that primary file on disk was automatically restored
            with open(target_file, "r", encoding="utf-8") as f:
                restored_data = json.load(f)
            self.assertEqual(restored_data["profile_name"], "GoodProfile")

    def test_load_config_resilient_recovers_from_non_dict_primary_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"

            profile_good = ConfigProfile(profile_name="GoodProfile")
            save_config_atomic(profile_good, target_file)
            save_config_atomic(ConfigProfile(profile_name="NextGood"), target_file)

            # Write a JSON array or string instead of a dictionary
            with open(target_file, "w", encoding="utf-8") as f:
                f.write('["not", "a", "dictionary"]')

            loaded = load_config_resilient(target_file)
            self.assertEqual(loaded.profile_name, "GoodProfile")

    def test_load_config_resilient_recovers_from_invalid_field_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"

            profile_good = ConfigProfile(profile_name="GoodProfile")
            save_config_atomic(profile_good, target_file)
            save_config_atomic(ConfigProfile(profile_name="NextGood"), target_file)

            # Write bad version field that cannot be converted to int
            with open(target_file, "w", encoding="utf-8") as f:
                f.write('{"version": "non-integer-value", "profile_name": "Bad"}')

            loaded = load_config_resilient(target_file)
            self.assertEqual(loaded.profile_name, "GoodProfile")

    def test_load_config_resilient_missing_primary_with_valid_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"

            profile = ConfigProfile(profile_name="BackupOnlyProfile")
            save_config_atomic(profile, target_file)
            save_config_atomic(ConfigProfile(profile_name="SecondProfile"), target_file)

            # Delete the primary config.json file
            target_file.unlink()
            self.assertFalse(target_file.exists())
            self.assertTrue(target_file.with_suffix(".bak").exists())

            loaded = load_config_resilient(target_file)
            self.assertEqual(loaded.profile_name, "BackupOnlyProfile")
            # Primary file should now be recreated from backup
            self.assertTrue(target_file.exists())

    def test_load_config_resilient_both_corrupted_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"
            bak_file = target_file.with_suffix(".bak")

            with open(target_file, "w", encoding="utf-8") as f:
                f.write("{garbage primary json")
            with open(bak_file, "w", encoding="utf-8") as f:
                f.write("{garbage bak json")

            loaded = load_config_resilient(target_file)
            self.assertEqual(loaded.profile_name, "Default")
            self.assertEqual(loaded.version, 1)

            # Primary file should have been overwritten with a valid default profile
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["profile_name"], "Default")

    def test_load_config_resilient_missing_primary_and_corrupted_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"
            bak_file = target_file.with_suffix(".bak")

            with open(bak_file, "w", encoding="utf-8") as f:
                f.write("{garbage bak json")

            loaded = load_config_resilient(target_file)
            self.assertEqual(loaded.profile_name, "Default")
            self.assertTrue(target_file.exists())

    def test_save_and_load_config_wrappers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"

            profile = ConfigProfile(profile_name="WrapperTest")
            saved_path = save_config(profile, target_file)
            self.assertEqual(saved_path, target_file)

            loaded = load_config(target_file)
            self.assertEqual(loaded.profile_name, "WrapperTest")

    def test_load_config_resilient_salvages_valid_fields_without_backup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"

            data = ConfigProfile(profile_name="Mine").to_dict()
            data["block_rules"][0]["domains"] = ["mysite.com"]
            data["app_close_schedule"]["target_hour"] = "ten"
            data["app_close_schedule"]["target_minute"] = 45
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            loaded = load_config_resilient(target_file)

            # Only the invalid field is reset; everything else survives
            self.assertEqual(loaded.app_close_schedule.target_hour, 22)
            self.assertEqual(loaded.app_close_schedule.target_minute, 45)
            self.assertEqual(loaded.profile_name, "Mine")
            self.assertEqual(loaded.block_rules[0].domains, ["mysite.com"])

            with open(target_file, "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            self.assertEqual(on_disk["block_rules"][0]["domains"], ["mysite.com"])
            self.assertEqual(on_disk["app_close_schedule"]["target_hour"], 22)

    def test_load_config_resilient_salvages_out_of_range_hour(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"

            data = ConfigProfile().to_dict()
            data["app_close_schedule"]["target_hour"] = 99
            with open(target_file, "w", encoding="utf-8") as f:
                json.dump(data, f)

            loaded = load_config_resilient(target_file)
            self.assertEqual(loaded.app_close_schedule.target_hour, 22)

    def test_load_config_resilient_preserves_rejected_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "config.json"
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("{garbage primary json")

            load_config_resilient(target_file)

            preserved = list(Path(tmpdir).glob("config.corrupt-*.json"))
            self.assertEqual(len(preserved), 1)
            self.assertEqual(
                preserved[0].read_text(encoding="utf-8"), "{garbage primary json"
            )


if __name__ == "__main__":
    unittest.main()
