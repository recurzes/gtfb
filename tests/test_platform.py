"""Tests for cross-platform utilities, diagnostics, and OS compatibility."""

import io
from unittest import TestCase
from unittest.mock import MagicMock, patch

import psutil

from gtfb.app import build_parser, main
from gtfb.core.closer import close_application, close_application_gracefully_windows
from gtfb.core.platform_utils import (
    _get_pkg_version,
    get_system_diagnostics,
    has_visible_window_linux,
    has_visible_window_macos,
    has_visible_window_windows,
    is_admin_or_root,
    is_gui_application,
    print_system_diagnostics,
)


class TestPlatformDiagnostics(TestCase):
    """Test suite for system and platform diagnostics."""

    def test_get_system_diagnostics_keys(self) -> None:
        """Verify get_system_diagnostics returns all expected keys and valid structure."""
        diag = get_system_diagnostics()

        self.assertIn("os", diag)
        self.assertIn("tray", diag)
        self.assertIn("process_tools", diag)
        self.assertIn("display", diag)
        self.assertIn("detected_gui_apps_count", diag)
        self.assertIn("detected_gui_apps_sample", diag)
        self.assertIn("notes", diag)

        os_info = diag["os"]
        self.assertIn("system", os_info)
        self.assertIn("release", os_info)
        self.assertIn("python_version", os_info)
        self.assertIn("is_admin_or_root", os_info)

        tray = diag["tray"]
        self.assertIn("pystray_available", tray)
        self.assertIn("pillow_available", tray)

        tools = diag["process_tools"]
        self.assertIn("psutil_available", tools)
        self.assertIn("pywin32_available", tools)

    def test_print_system_diagnostics(self) -> None:
        """Verify print_system_diagnostics formats and prints output cleanly."""
        captured_output = io.StringIO()
        with patch("sys.stdout", captured_output):
            print_system_diagnostics()

        output = captured_output.getvalue()
        self.assertIn("GTFB System & Platform Diagnostics Report", output)
        self.assertIn("[Operating System]", output)
        self.assertIn("[System Tray Backend]", output)
        self.assertIn("[Process Inspection & Automation Tools]", output)
        self.assertIn("[Display & Session Environment]", output)

    def test_get_pkg_version_fallback(self) -> None:
        """Verify _get_pkg_version retrieves version or returns unknown."""
        # Non-existent package
        ver = _get_pkg_version("non_existent_fake_package_12345")
        self.assertEqual(ver, "unknown")

        # Module with __version__
        mock_mod = MagicMock()
        mock_mod.__version__ = "1.2.3"
        self.assertEqual(_get_pkg_version("mock_pkg", mock_mod), "1.2.3")

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Windows")
    @patch("gtfb.core.platform_utils.PYWIN32_AVAILABLE", False)
    def test_diagnostics_windows_without_pywin32(self) -> None:
        """Verify diagnostics reports fallback notes when pywin32 is absent on Windows."""
        diag = get_system_diagnostics()
        self.assertFalse(diag["process_tools"]["pywin32_available"])
        self.assertTrue(any("Falling back to psutil" in note for note in diag["notes"]))

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Linux")
    @patch.dict("os.environ", {}, clear=True)
    def test_diagnostics_linux_notes(self) -> None:
        """Verify diagnostics handles Linux platform notes and display server check."""
        diag = get_system_diagnostics()
        self.assertTrue(any("libayatana-appindicator3" in note for note in diag["notes"]))
        self.assertTrue(any("No DISPLAY or WAYLAND_DISPLAY" in note for note in diag["notes"]))

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Darwin")
    def test_diagnostics_macos_notes(self) -> None:
        """Verify diagnostics reports macOS AppKit and Accessibility notes."""
        diag = get_system_diagnostics()
        self.assertTrue(any("AppKit" in note for note in diag["notes"]))
        self.assertTrue(any("Accessibility permissions" in note for note in diag["notes"]))


class TestPlatformDetectionFallbacks(TestCase):
    """Test platform-specific GUI detection heuristics."""

    def test_has_visible_window_linux(self) -> None:
        """Verify Linux GUI detection heuristic against environment and pattern."""
        proc = MagicMock()
        proc.environ.return_value = {"DISPLAY": ":0"}
        proc.name.return_value = "firefox"
        self.assertTrue(has_visible_window_linux(proc))

        proc_terminal = MagicMock()
        proc_terminal.environ.return_value = {"DISPLAY": ":0"}
        proc_terminal.name.return_value = "systemd"
        self.assertFalse(has_visible_window_linux(proc_terminal))

        proc_no_display = MagicMock()
        proc_no_display.environ.return_value = {}
        proc_no_display.name.return_value = "firefox"
        self.assertFalse(has_visible_window_linux(proc_no_display))

    def test_has_visible_window_macos(self) -> None:
        """Verify macOS GUI detection heuristic."""
        proc = MagicMock()
        proc.name.return_value = "Safari"
        self.assertTrue(has_visible_window_macos(proc))

        proc_app = MagicMock()
        proc_app.name.return_value = "custom_tool"
        proc_app.exe.return_value = "/Applications/CustomTool.app/Contents/MacOS/custom_tool"
        self.assertTrue(has_visible_window_macos(proc_app))

        proc_daemon = MagicMock()
        proc_daemon.name.return_value = "syslogd"
        proc_daemon.exe.return_value = "/usr/sbin/syslogd"
        self.assertFalse(has_visible_window_macos(proc_daemon))

    @patch("gtfb.core.platform_utils.PYWIN32_AVAILABLE", False)
    def test_has_visible_window_windows_fallback(self) -> None:
        """Verify Windows heuristic fallback when pywin32 is not installed."""
        proc = MagicMock()
        proc.username.return_value = "testuser"
        proc.num_threads.return_value = 4
        with patch.dict("os.environ", {"USERNAME": "testuser"}):
            self.assertTrue(has_visible_window_windows(proc))

        proc_single_thread = MagicMock()
        proc_single_thread.username.return_value = "testuser"
        proc_single_thread.num_threads.return_value = 1
        with patch.dict("os.environ", {"USERNAME": "testuser"}):
            self.assertFalse(has_visible_window_windows(proc_single_thread))

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Windows")
    @patch("gtfb.core.platform_utils.PYWIN32_AVAILABLE", False)
    def test_close_application_windows_pywin32_missing_fallback(self) -> None:
        """Verify close_application falls back to terminate when pywin32 is unavailable."""
        proc = MagicMock()
        proc.name.return_value = "notepad.exe"
        proc.wait.return_value = 0

        result = close_application(proc, window_title="Untitled")
        self.assertTrue(result)
        proc.terminate.assert_called_once()

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Linux")
    def test_close_application_linux(self) -> None:
        """Verify close_application on Linux uses SIGTERM / terminate."""
        proc = MagicMock()
        proc.name.return_value = "gedit"
        proc.wait.return_value = 0

        result = close_application(proc)
        self.assertTrue(result)
        proc.terminate.assert_called_once()


class TestPrivilegeChecks(TestCase):
    """Test administrator / root privilege detection."""

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Windows")
    def test_is_admin_windows(self) -> None:
        """Verify is_admin_or_root on Windows."""
        with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=1):
            self.assertTrue(is_admin_or_root())

        with patch("ctypes.windll.shell32.IsUserAnAdmin", return_value=0):
            self.assertFalse(is_admin_or_root())

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Linux")
    def test_is_admin_linux(self) -> None:
        """Verify is_admin_or_root on Linux/POSIX."""
        with patch("os.geteuid", return_value=0, create=True):
            self.assertTrue(is_admin_or_root())

        with patch("os.geteuid", return_value=1000, create=True):
            self.assertFalse(is_admin_or_root())


class TestCliDiagnosticsFlag(TestCase):
    """Test CLI --check-system / --diagnostics argument."""

    def test_parser_has_check_system(self) -> None:
        """Verify build_parser includes --check-system."""
        parser = build_parser()
        args = parser.parse_args(["--check-system"])
        self.assertTrue(args.check_system)

        args_diag = parser.parse_args(["--diagnostics"])
        self.assertTrue(args_diag.check_system)

    @patch("gtfb.app.setup_logging")
    @patch("gtfb.core.platform_utils.print_system_diagnostics")
    def test_main_runs_diagnostics(self, mock_print: MagicMock, mock_logging: MagicMock) -> None:
        """Verify main returns 0 and prints diagnostics when --check-system is passed."""
        ret = main(["--check-system"])
        self.assertEqual(ret, 0)
        mock_print.assert_called_once()


class TestWindowsStartupShortcuts(TestCase):
    """Test suite for Windows startup shortcut creation, verification, and removal."""

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Windows")
    def test_get_windows_startup_dir_and_shortcut_path(self) -> None:
        from pathlib import Path
        with patch.dict("os.environ", {"APPDATA": r"C:\Users\testuser\AppData\Roaming"}):
            from gtfb.core.platform_utils import get_startup_shortcut_path, get_windows_startup_dir

            startup_dir = get_windows_startup_dir()
            self.assertEqual(
                startup_dir,
                Path(r"C:\Users\testuser\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"),
            )

            shortcut = get_startup_shortcut_path("GTFB")
            self.assertEqual(shortcut, startup_dir / "GTFB.lnk")

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Windows")
    def test_is_startup_shortcut_installed(self) -> None:
        from gtfb.core.platform_utils import is_startup_shortcut_installed
        with patch("pathlib.Path.is_file", return_value=True):
            self.assertTrue(is_startup_shortcut_installed("GTFB"))
        with patch("pathlib.Path.is_file", return_value=False):
            self.assertFalse(is_startup_shortcut_installed("GTFB"))

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Linux")
    def test_is_startup_shortcut_installed_non_windows(self) -> None:
        from gtfb.core.platform_utils import is_startup_shortcut_installed
        self.assertFalse(is_startup_shortcut_installed("GTFB"))

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Windows")
    @patch("subprocess.run")
    def test_create_startup_shortcut_invokes_powershell(self, mock_subproc: MagicMock) -> None:
        from pathlib import Path
        mock_subproc.return_value = MagicMock(returncode=0)
        from gtfb.core.platform_utils import create_startup_shortcut

        with patch("pathlib.Path.mkdir"):
            shortcut_path = create_startup_shortcut(
                target_path=r"C:\Program Files\GTFB\gtfb.exe",
                name="GTFB",
            )
            self.assertEqual(shortcut_path.name, "GTFB.lnk")
            mock_subproc.assert_called_once()
            cmd_args = mock_subproc.call_args[0][0]
            self.assertEqual(cmd_args[0], "powershell.exe")
            self.assertIn("WScript.Shell", cmd_args[4])

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Linux")
    def test_create_startup_shortcut_raises_on_non_windows(self) -> None:
        from gtfb.core.platform_utils import create_startup_shortcut
        with self.assertRaises(OSError):
            create_startup_shortcut()

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Windows")
    def test_remove_startup_shortcut(self) -> None:
        from gtfb.core.platform_utils import remove_startup_shortcut
        with patch("pathlib.Path.is_file", return_value=True), patch("pathlib.Path.unlink") as mock_unlink:
            res = remove_startup_shortcut("GTFB")
            self.assertTrue(res)
            mock_unlink.assert_called_once()

        with patch("pathlib.Path.is_file", return_value=False):
            res = remove_startup_shortcut("GTFB")
            self.assertFalse(res)

    @patch("gtfb.core.platform_utils.CURRENT_OS", "Windows")
    def test_open_windows_startup_folder(self) -> None:
        from gtfb.core.platform_utils import open_windows_startup_folder
        with patch("pathlib.Path.mkdir"), patch("os.startfile", create=True) as mock_startfile:
            res = open_windows_startup_folder()
            self.assertTrue(res)
            mock_startfile.assert_called_once()


class TestCliStartupFlags(TestCase):
    """Test CLI startup install, remove, and open-folder commands."""

    def test_parser_has_startup_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--install-startup"])
        self.assertTrue(args.install_startup)

        args = parser.parse_args(["--remove-startup"])
        self.assertTrue(args.remove_startup)

        args = parser.parse_args(["--open-startup-folder"])
        self.assertTrue(args.open_startup_folder)

    @patch("gtfb.app.setup_logging")
    @patch("gtfb.core.platform_utils.create_startup_shortcut")
    def test_main_install_startup(self, mock_create: MagicMock, mock_logging: MagicMock) -> None:
        from pathlib import Path
        mock_create.return_value = Path("C:/test/GTFB.lnk")
        ret = main(["--install-startup"])
        self.assertEqual(ret, 0)
        mock_create.assert_called_once()

    @patch("gtfb.app.setup_logging")
    @patch("gtfb.core.platform_utils.remove_startup_shortcut")
    def test_main_remove_startup(self, mock_remove: MagicMock, mock_logging: MagicMock) -> None:
        mock_remove.return_value = True
        ret = main(["--remove-startup"])
        self.assertEqual(ret, 0)
        mock_remove.assert_called_once()

    @patch("gtfb.app.setup_logging")
    @patch("gtfb.core.platform_utils.open_windows_startup_folder")
    def test_main_open_startup_folder(self, mock_open: MagicMock, mock_logging: MagicMock) -> None:
        mock_open.return_value = True
        ret = main(["--open-startup-folder"])
        self.assertEqual(ret, 0)
        mock_open.assert_called_once()

