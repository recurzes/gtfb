"""Unit tests for Windows PyInstaller build configuration and scripts."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.build_windows import ensure_icon_assets, run_pyinstaller_build


class TestWindowsBuildSpec(unittest.TestCase):
    """Test packaging/windows/gtfb.spec syntax and structure."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.spec_file = self.repo_root / "packaging" / "windows" / "gtfb.spec"

    def test_spec_file_exists(self):
        self.assertTrue(self.spec_file.is_file(), f"Spec file missing: {self.spec_file}")

    def test_spec_file_syntax_and_contents(self):
        content = self.spec_file.read_text(encoding="utf-8")
        self.assertIn("gtfb.app", content)
        self.assertIn("console=False", content)
        self.assertIn("pystray._win32", content)
        self.assertIn("extension", content)
        self.assertIn("assets", content)
        self.assertIn("icon.ico", content)

    def test_ensure_icon_assets_creates_ico(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            icons_dir = tmp_repo / "assets" / "icons"
            icons_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy real icon.png or let it create dynamically
            real_icon = self.repo_root / "assets" / "icons" / "icon.png"
            if real_icon.is_file():
                import shutil
                shutil.copy2(real_icon, icons_dir / "icon.png")

            ico_path = ensure_icon_assets(tmp_repo)
            self.assertTrue(ico_path.is_file())
            self.assertGreater(ico_path.stat().st_size, 0)

    @patch("subprocess.run")
    def test_run_pyinstaller_build_invokes_pyinstaller(self, mock_subproc_run):
        mock_subproc_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_repo = Path(tmp_dir)
            spec_dir = tmp_repo / "packaging" / "windows"
            spec_dir.mkdir(parents=True, exist_ok=True)
            (spec_dir / "gtfb.spec").write_text("# dummy spec", encoding="utf-8")

            dist_dir = tmp_repo / "dist"
            dist_dir.mkdir(parents=True, exist_ok=True)
            dummy_exe = dist_dir / "gtfb.exe"
            dummy_exe.write_bytes(b"MZ dummy exe content")

            exe_res = run_pyinstaller_build(tmp_repo)
            self.assertEqual(exe_res, dummy_exe)
            mock_subproc_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
