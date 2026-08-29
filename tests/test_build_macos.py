"""Unit tests for macOS PyInstaller build configuration and scripts."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.build_macos import ensure_icon_assets, run_pyinstaller_build


class TestMacOSBuildSpec(unittest.TestCase):
    """Test packaging/macos/gtfb.spec syntax and structure."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.spec_file = self.repo_root / "packaging" / "macos" / "gtfb.spec"

    def test_spec_file_exists(self):
        self.assertTrue(self.spec_file.is_file(), f"Spec file missing: {self.spec_file}")

    def test_spec_file_syntax_and_contents(self):
        content = self.spec_file.read_text(encoding="utf-8")
        self.assertIn("BUNDLE", content)
        self.assertIn("GTFB.app", content)
        self.assertIn("LSUIElement", content)
        self.assertIn("com.gtfb.app", content)
        self.assertIn("pystray._darwin", content)
        self.assertIn("icon.icns", content)
        self.assertIn("assets", content)
        self.assertIn("extension", content)
        self.assertIn("NSHighResolutionCapable", content)

    def test_ensure_icon_assets_creates_icns(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            icons_dir = tmp_repo / "assets" / "icons"
            icons_dir.mkdir(parents=True, exist_ok=True)

            real_icon = self.repo_root / "assets" / "icons" / "icon.png"
            if real_icon.is_file():
                import shutil
                shutil.copy2(real_icon, icons_dir / "icon.png")

            icns_path = ensure_icon_assets(tmp_repo)
            self.assertTrue(icns_path.is_file())
            self.assertGreater(icns_path.stat().st_size, 0)

    @patch("subprocess.run")
    def test_run_pyinstaller_build_invokes_pyinstaller(self, mock_subproc_run):
        mock_subproc_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            spec_dir = tmp_repo / "packaging" / "macos"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "gtfb.spec").write_text("# dummy macos spec", encoding="utf-8")

            dist_dir = tmp_repo / "dist"
            dist_dir.mkdir(parents=True, exist_ok=True)
            dummy_app = dist_dir / "GTFB.app"
            dummy_app.mkdir(parents=True, exist_ok=True)

            app_res = run_pyinstaller_build(tmp_repo)
            self.assertEqual(app_res, dummy_app)
            mock_subproc_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
