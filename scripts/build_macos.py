"""Automated macOS build script for packaging GTFB into standalone GTFB.app bundle."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


def ensure_icon_assets(repo_root: Path) -> Path:
    """Ensure multi-resolution icon.icns exists in assets/icons."""
    icon_icns = repo_root / "assets" / "icons" / "icon.icns"
    icon_png = repo_root / "assets" / "icons" / "icon.png"
    ext_icon = repo_root / "extension" / "icons" / "icon128.png"

    if icon_icns.is_file() and icon_icns.stat().st_size > 0:
        return icon_icns

    print("Generating assets/icons/icon.icns...")
    icon_icns.parent.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image

        if icon_png.is_file():
            base_img = Image.open(icon_png)
        elif ext_icon.is_file():
            base_img = Image.open(ext_icon)
        else:
            from gtfb.ui.icons import get_icon
            base_img = get_icon("COUNTING_DOWN", width=512, height=512)

        base_img.save(
            icon_icns,
            format="ICNS",
            sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)],
        )
        print(f"[OK] Created {icon_icns}")
        return icon_icns
    except Exception as err:
        print(f"Warning: Could not generate multi-resolution icon.icns ({err}). Proceeding.")
        return icon_icns


def run_pyinstaller_build(repo_root: Path) -> Path:
    """Invoke PyInstaller to build the macOS application bundle."""
    spec_file = repo_root / "packaging" / "macos" / "gtfb.spec"
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

    app_path = dist_dir / "GTFB.app"
    if not app_path.exists():
        raise FileNotFoundError(f"Expected application bundle not found at: {app_path}")

    return app_path


def main() -> int:
    """Main build orchestrator."""
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
    print("  GTFB macOS Application Bundle Build (PyInstaller)")
    print("=" * 60)
    print(f"Repository Root: {repo_root}")
    print(f"Python Executable: {sys.executable} ({sys.version.split()[0]})")
    print("-" * 60)

    try:
        ensure_icon_assets(repo_root)
        app_path = run_pyinstaller_build(repo_root)

        print("-" * 60)
        print("[SUCCESS] Build Succeeded!")
        print(f"  Bundle Location: {app_path}")
        print("=" * 60)
        print("To launch GTFB on macOS:")
        print(f"  Run from terminal: open '{app_path}'")
        print(f"  Or execute directly: '{app_path / 'Contents' / 'MacOS' / 'gtfb'}'")
        print("=" * 60)
        print("Gatekeeper Note for Indie / Unsigned Builds:")
        print("  If macOS blocks launching, right-click GTFB.app in Finder and choose 'Open',")
        print("  or run: xattr -d com.apple.quarantine dist/GTFB.app")
        print("=" * 60)
        return 0
    except Exception as err:
        print(f"\n[ERROR] Build failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
