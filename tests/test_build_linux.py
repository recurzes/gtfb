"""Unit tests for Linux PyInstaller build configuration, desktop entry, and scripts."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.build_linux import ensure_icon_assets, run_pyinstaller_build


class TestLinuxBuildSpec(unittest.TestCase):
    """Test packaging/linux/gtfb.spec syntax and structure."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.spec_file = self.repo_root / "packaging" / "linux" / "gtfb.spec"
        self.desktop_file = self.repo_root / "packaging" / "linux" / "gtfb.desktop"
        self.build_sh = self.repo_root / "scripts" / "build_linux.sh"

    def test_spec_file_exists(self):
        self.assertTrue(self.spec_file.is_file(), f"Spec file missing: {self.spec_file}")

    def test_spec_file_syntax_and_contents(self):
        content = self.spec_file.read_text(encoding="utf-8")
        self.assertIn("pystray._appindicator", content)
        self.assertIn("pystray._xorg", content)
        self.assertIn("pystray._gtk", content)
        self.assertIn("gi.repository.AyatanaAppIndicator3", content)
        self.assertIn("assets", content)
        self.assertIn("extension", content)
        self.assertIn("console=False", content)
        self.assertIn("strip=True", content)
        self.assertIn("icon.png", content)

    def test_desktop_file_exists(self):
        self.assertTrue(self.desktop_file.is_file(), f"Desktop file missing: {self.desktop_file}")

    def test_desktop_file_contents(self):
        content = self.desktop_file.read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", content)
        self.assertIn("Name=GTFB", content)
        self.assertIn("Comment=Anti-Distraction Suite", content)
        self.assertIn("Exec=gtfb", content)
        self.assertIn("Icon=gtfb", content)
        self.assertIn("Terminal=false", content)
        self.assertIn("Type=Application", content)
        self.assertIn("Categories=Utility;Productivity;", content)
        self.assertIn("StartupNotify=false", content)

    def test_build_sh_file_exists_and_format(self):
        self.assertTrue(self.build_sh.is_file(), f"Build shell script missing: {self.build_sh}")
        content = self.build_sh.read_text(encoding="utf-8")
        self.assertIn("#!/usr/bin/env bash", content)
        self.assertIn("build_linux.py", content)

    def test_ensure_icon_assets_creates_png(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            icons_dir = tmp_repo / "assets" / "icons"
            icons_dir.mkdir(parents=True, exist_ok=True)

            real_icon = self.repo_root / "assets" / "icons" / "icon.png"
            if real_icon.is_file():
                import shutil
                shutil.copy2(real_icon, icons_dir / "icon.png")

            png_path = ensure_icon_assets(tmp_repo)
            self.assertTrue(png_path.is_file())
            self.assertGreater(png_path.stat().st_size, 0)

    @patch("subprocess.run")
    def test_run_pyinstaller_build_invokes_pyinstaller(self, mock_subproc_run):
        mock_subproc_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            spec_dir = tmp_repo / "packaging" / "linux"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "gtfb.spec").write_text("# dummy linux spec", encoding="utf-8")

            dist_dir = tmp_repo / "dist"
            dist_dir.mkdir(parents=True, exist_ok=True)
            dummy_bin = dist_dir / "gtfb"
            dummy_bin.write_bytes(b"\x7fELF dummy binary content")

            bin_res = run_pyinstaller_build(tmp_repo)
            self.assertEqual(bin_res, dummy_bin)
            mock_subproc_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_pyinstaller_build_handles_failure(self, mock_subproc_run):
        mock_subproc_run.return_value = MagicMock(returncode=1)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            spec_dir = tmp_repo / "packaging" / "linux"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "gtfb.spec").write_text("# dummy linux spec", encoding="utf-8")

            with self.assertRaises(RuntimeError):
                run_pyinstaller_build(tmp_repo)


if __name__ == "__main__":
    unittest.main()
