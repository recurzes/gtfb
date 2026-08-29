"""Automated Windows build script for packaging GTFB into standalone gtfb.exe."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


def ensure_icon_assets(repo_root: Path) -> Path:
    """Ensure multi-resolution icon.ico exists in assets/icons."""
    icon_ico = repo_root / "assets" / "icons" / "icon.ico"
    icon_png = repo_root / "assets" / "icons" / "icon.png"
    ext_icon = repo_root / "extension" / "icons" / "icon128.png"

    if icon_ico.is_file() and icon_ico.stat().st_size > 0:
        return icon_ico

    print("Generating assets/icons/icon.ico...")
    icon_ico.parent.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image

        if icon_png.is_file():
            base_img = Image.open(icon_png)
        elif ext_icon.is_file():
            base_img = Image.open(ext_icon)
        else:
            from gtfb.ui.icons import get_icon
            base_img = get_icon("COUNTING_DOWN", width=256, height=256)

        base_img.save(
            icon_ico,
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
        )
        print(f"[OK] Created {icon_ico}")
        return icon_ico
    except Exception as err:
        print(f"Warning: Could not generate multi-resolution icon.ico ({err}). Proceeding.")
        return icon_ico


def run_pyinstaller_build(repo_root: Path) -> Path:
    """Invoke PyInstaller to build the Windows standalone binary."""
    spec_file = repo_root / "packaging" / "windows" / "gtfb.spec"
    dist_dir = repo_root / "dist"
    build_dir = repo_root / "build"

    if not spec_file.is_file():
        raise FileNotFoundError(f"Spec file not found at: {spec_file}")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        str(spec_file),
    ]

    print(f"Running PyInstaller command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(repo_root), check=False)

    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller build failed with exit code {result.returncode}")

    exe_path = dist_dir / "gtfb.exe"
    if not exe_path.is_file():
        raise FileNotFoundError(f"Expected binary not found at: {exe_path}")

    return exe_path


def main() -> int:
    """Main build orchestrator."""
    # Ensure UTF-8 output when possible
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    repo_root = Path(__file__).resolve().parent.parent
    print("=" * 60)
    print("  GTFB Windows Standalone Build (PyInstaller)")
    print("=" * 60)
    print(f"Repository Root: {repo_root}")
    print(f"Python Executable: {sys.executable} ({sys.version.split()[0]})")
    print("-" * 60)

    try:
        ensure_icon_assets(repo_root)
        exe_path = run_pyinstaller_build(repo_root)

        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print("-" * 60)
        print("[SUCCESS] Build Succeeded!")
        print(f"  Binary Location: {exe_path}")
        print(f"  Binary Size:     {size_mb:.2f} MB")
        print("=" * 60)
        print("To launch GTFB:")
        print(f"  Double-click '{exe_path.name}' or run from terminal: '{exe_path}'")
        print("=" * 60)
        return 0
    except Exception as err:
        print(f"\n[ERROR] Build failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
