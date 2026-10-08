"""Tests that the application entry point wires saved configuration into the scheduler."""

import unittest
from unittest.mock import patch

from gtfb.app import main
from gtfb.config import ConfigProfile


def _saved_profile() -> ConfigProfile:
    profile = ConfigProfile()
    profile.app_close_schedule.target_hour = 23
    profile.app_close_schedule.target_minute = 15
    profile.app_close_schedule.enabled = False
    return profile


class TestAppStartupWiring(unittest.TestCase):
    """Verify main() uses config.json rather than hardcoded defaults."""

    def _run_main(self, argv, profile):
        with patch("gtfb.app.setup_logging"), \
             patch("gtfb.app.load_config_resilient", return_value=profile), \
             patch("gtfb.app.TrayApp") as mock_tray, \
             patch("gtfb.app.run_scheduler_cli") as mock_cli:
            ret = main(argv)
        return ret, mock_tray, mock_cli

    def test_tray_scheduler_uses_saved_schedule(self):
        profile = _saved_profile()
        ret, mock_tray, _ = self._run_main([], profile)

        self.assertEqual(ret, 0)
        kwargs = mock_tray.call_args.kwargs
        scheduler = kwargs["scheduler"]
        self.assertEqual(scheduler.target_hour, 23)
        self.assertEqual(scheduler.target_minute, 15)
        self.assertFalse(scheduler.enabled)
        self.assertIs(kwargs["config"], profile)
        mock_tray.return_value.run.assert_called_once()

    def test_cli_flag_overrides_only_given_field(self):
        profile = _saved_profile()
        _, mock_tray, _ = self._run_main(["--hour", "21"], profile)

        scheduler = mock_tray.call_args.kwargs["scheduler"]
        self.assertEqual(scheduler.target_hour, 21)
        self.assertEqual(scheduler.target_minute, 15)
        # The override is visible to the settings window and API through the shared profile
        self.assertEqual(profile.app_close_schedule.target_hour, 21)

    def test_cli_mode_uses_saved_schedule(self):
        ret, mock_tray, mock_cli = self._run_main(["--cli", "--no-shutdown"], _saved_profile())

        self.assertEqual(ret, 0)
        mock_tray.assert_not_called()
        mock_cli.assert_called_once_with(
            target_hour=23,
            target_minute=15,
            shutdown=False,
            dry_run=False,
        )

    def test_unreadable_config_falls_back_to_defaults(self):
        with patch("gtfb.app.setup_logging"), \
             patch("gtfb.app.load_config_resilient", side_effect=OSError("disk error")), \
             patch("gtfb.app.TrayApp") as mock_tray:
            ret = main([])

        self.assertEqual(ret, 0)
        scheduler = mock_tray.call_args.kwargs["scheduler"]
        self.assertEqual(scheduler.target_hour, 22)
        self.assertEqual(scheduler.target_minute, 0)

    def test_out_of_range_hour_flag_is_rejected(self):
        with patch("gtfb.app.setup_logging"), self.assertRaises(SystemExit):
            main(["--hour", "24"])


if __name__ == "__main__":
    unittest.main()
