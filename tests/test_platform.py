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
