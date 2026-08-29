"""Unit tests for extension bundling, deployment, browser detection, and setup assistants."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from gtfb.core.extension_installer import (
    MARKER_FILENAME,
    copy_extension_path_to_clipboard,
    deploy_extension_files,
    detect_installed_browsers,
    get_bundled_extension_path,
    get_installed_extension_dir,
    is_first_run_completed,
    open_browser_extension_page,
    open_folder_in_explorer,
    set_first_run_completed,
)
from gtfb.ui.extension_dialog import (
    ExtensionSetupWindow,
    check_and_run_first_time_setup,
    prompt_extension_installation_consent,
)


class TestExtensionInstallerCore(unittest.TestCase):
    """Test core extension bundle discovery and installation mechanics."""

    def test_get_bundled_extension_path_finds_repo_extension(self):
        ext_path = get_bundled_extension_path()
        self.assertIsNotNone(ext_path)
        self.assertTrue((ext_path / "manifest.json").is_file())

    def test_get_bundled_extension_path_when_frozen(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            frozen_ext = tmp_path / "extension"
            frozen_ext.mkdir()
            (frozen_ext / "manifest.json").write_text('{"name": "test"}', encoding="utf-8")

            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "_MEIPASS", str(tmp_path), create=True
            ):
                result = get_bundled_extension_path()
                self.assertEqual(result, frozen_ext.resolve())

    def test_get_installed_extension_dir(self):
        target = get_installed_extension_dir()
        self.assertIsInstance(target, Path)
        self.assertTrue(str(target).endswith("extension"))

    def test_deploy_extension_files(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dest_path = Path(tmp_dir) / "test_ext_deploy"
            deployed_dir = deploy_extension_files(target_dir=dest_path)
            self.assertEqual(deployed_dir, dest_path)
            self.assertTrue(dest_path.is_dir())
            self.assertTrue((dest_path / "manifest.json").is_file())
            self.assertTrue((dest_path / "icons").is_dir())

    def test_detect_installed_browsers_structure(self):
        browsers = detect_installed_browsers()
        self.assertIn("chrome", browsers)
        self.assertIn("edge", browsers)
        self.assertIn("firefox", browsers)
        self.assertIn("brave", browsers)

        for key, info in browsers.items():
            self.assertIn("name", info)
            self.assertIn("type", info)
            self.assertIn("ext_url", info)
            self.assertIn("installed", info)

    def test_first_run_state_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("gtfb.core.extension_installer.get_config_dir", return_value=Path(tmp_dir)):
                self.assertFalse(is_first_run_completed())
                set_first_run_completed(True)
                self.assertTrue(is_first_run_completed())
                self.assertTrue((Path(tmp_dir) / MARKER_FILENAME).exists())
                set_first_run_completed(False)
                self.assertFalse(is_first_run_completed())

    def test_copy_extension_path_to_clipboard(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dummy_path = Path(tmp_dir) / "extension"
            success = copy_extension_path_to_clipboard(dummy_path)
            self.assertIsInstance(success, bool)

    def test_open_browser_extension_page(self):
        with patch("subprocess.Popen") as mock_popen, patch("webbrowser.open") as mock_web_open:
            browsers = {
                "test_browser": {
                    "name": "Test Browser",
                    "ext_url": "test://extensions",
                    "exe": Path(sys.executable),
                    "installed": True,
                }
            }
            res = open_browser_extension_page("test_browser", detected_browsers=browsers)
            self.assertTrue(res)
            mock_popen.assert_called_once()

    def test_open_folder_in_explorer(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("os.startfile", create=True) as mock_startfile, patch("subprocess.Popen") as mock_popen:
                success = open_folder_in_explorer(Path(tmp_dir))
                self.assertTrue(success)


class TestExtensionDialogUI(unittest.TestCase):
    """Test consent prompts and onboarding window."""

    @patch("gtfb.ui.manager.UIManager.prompt_extension_consent", return_value=True)
    def test_prompt_extension_installation_consent_yes(self, mock_prompt):
        consent = prompt_extension_installation_consent()
        self.assertTrue(consent)
        mock_prompt.assert_called_once()

    @patch("gtfb.ui.manager.UIManager.prompt_extension_consent", return_value=False)
    def test_prompt_extension_installation_consent_no(self, mock_prompt):
        consent = prompt_extension_installation_consent()
        self.assertFalse(consent)
        mock_prompt.assert_called_once()


    @patch("gtfb.ui.extension_dialog.prompt_extension_installation_consent", return_value=True)
    @patch("gtfb.ui.extension_dialog.ExtensionSetupWindow.open_or_focus")
    @patch("gtfb.ui.extension_dialog.is_first_run_completed", return_value=False)
    @patch("gtfb.ui.extension_dialog.set_first_run_completed")
    def test_check_and_run_first_time_setup_when_agreed(
        self, mock_set_done, mock_is_done, mock_open_win, mock_prompt
    ):
        check_and_run_first_time_setup()
        mock_prompt.assert_called_once()
        mock_set_done.assert_called_with(True)
        mock_open_win.assert_called_once()

    @patch("gtfb.ui.extension_dialog.prompt_extension_installation_consent", return_value=False)
    @patch("gtfb.ui.extension_dialog.ExtensionSetupWindow.open_or_focus")
    @patch("gtfb.ui.extension_dialog.is_first_run_completed", return_value=False)
    @patch("gtfb.ui.extension_dialog.set_first_run_completed")
    def test_check_and_run_first_time_setup_when_declined(
        self, mock_set_done, mock_is_done, mock_open_win, mock_prompt
    ):
        check_and_run_first_time_setup()
        mock_prompt.assert_called_once()
        mock_set_done.assert_called_with(True)
        mock_open_win.assert_not_called()

    @patch("gtfb.ui.extension_dialog.is_first_run_completed", return_value=True)
    @patch("gtfb.ui.extension_dialog.prompt_extension_installation_consent")
    def test_check_and_run_first_time_setup_skips_if_already_completed(
        self, mock_prompt, mock_is_done
    ):
        check_and_run_first_time_setup(force=False)
        mock_prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
