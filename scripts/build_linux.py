"""Automated Linux build script for packaging GTFB into standalone Linux executable."""

import os
from pathlib import Path
import shutil
import subprocess
import sys


def ensure_icon_assets(repo_root: Path) -> Path:
    """Ensure icon.png exists in assets/icons."""
    icon_png = repo_root / "assets" / "icons" / "icon.png"
    ext_icon = repo_root / "extension" / "icons" / "icon128.png"

    if icon_png.is_file() and icon_png.stat().st_size > 0:
        return icon_png

    print("Generating assets/icons/icon.png...")
    icon_png.parent.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image

        if ext_icon.is_file():
            base_img = Image.open(ext_icon)
            base_img.save(icon_png, format="PNG")
        else:
            from gtfb.ui.icons import get_icon
            base_img = get_icon("COUNTING_DOWN", width=128, height=128)
            base_img.save(icon_png, format="PNG")

        print(f"[OK] Created {icon_png}")
        return icon_png
    except Exception as err:
        print(f"Warning: Could not generate icon.png ({err}). Proceeding.")
        return icon_png


def run_pyinstaller_build(repo_root: Path) -> Path:
    """Invoke PyInstaller to build the Linux standalone binary."""
    spec_file = repo_root / "packaging" / "linux" / "gtfb.spec"
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

    bin_path = dist_dir / "gtfb"
    if not bin_path.exists():
        raise FileNotFoundError(f"Expected executable not found at: {bin_path}")

    return bin_path


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
    print("  GTFB Linux Standalone Binary Build (PyInstaller)")
    print("=" * 60)
    print(f"Repository Root: {repo_root}")
    print(f"Python Executable: {sys.executable} ({sys.version.split()[0]})")
    print("-" * 60)
    print("Prerequisites Notice for Linux Tray Indicators:")
    print("  Ubuntu/Debian: sudo apt install libayatana-appindicator3-1 gir1.2-ayatanaappindicator3-0.1")
    print("  Fedora/RHEL:   sudo dnf install libappindicator-gtk3")
    print("  Arch Linux:    sudo pacman -S libappindicator-gtk3")
    print("-" * 60)

    try:
        ensure_icon_assets(repo_root)
        bin_path = run_pyinstaller_build(repo_root)

        size_mb = bin_path.stat().st_size / (1024 * 1024) if bin_path.is_file() else 0
        print("-" * 60)
        print("[SUCCESS] Build Succeeded!")
        print(f"  Binary Location: {bin_path}")
        if size_mb > 0:
            print(f"  Binary Size:     {size_mb:.2f} MB")
        print("=" * 60)
        print("To launch GTFB on Linux:")
        print(f"  Run from terminal: '{bin_path}'")
        print("=" * 60)
        print("To install desktop entry & icon for your application menu:")
        print("  cp packaging/linux/gtfb.desktop ~/.local/share/applications/")
        print("  mkdir -p ~/.local/share/icons/hicolor/128x128/apps")
        print("  cp assets/icons/icon.png ~/.local/share/icons/hicolor/128x128/apps/gtfb.png")
        print("=" * 60)
        return 0
    except Exception as err:
        print(f"\n[ERROR] Build failed: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
