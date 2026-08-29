# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

block_cipher = None

spec_dir = Path(SPECPATH).resolve()
repo_root = spec_dir.parent.parent

assets_dir = str(repo_root / "assets")
extension_dir = str(repo_root / "extension")
app_py = str(repo_root / "src" / "gtfb" / "app.py")
src_dir = str(repo_root / "src")
icon_path = str(repo_root / "assets" / "icons" / "icon.ico")

datas = [
    (assets_dir, "assets"),
    (extension_dir, "extension"),
]

hiddenimports = [
    "pystray._win32",
    "win32gui",
    "win32process",
    "win32con",
    "win32api",
    "PIL._tkinter_finder",
    "tkinter",
    "tkinter.ttk",
    "tkinter.messagebox",
    "gtfb",
    "gtfb.app",
    "gtfb.config",
    "gtfb.config.models",
    "gtfb.config.storage",
    "gtfb.config.sanitizer",
    "gtfb.core",
    "gtfb.core.scheduler",
    "gtfb.core.closer",
    "gtfb.core.platform_utils",
    "gtfb.core.extension_installer",
    "gtfb.ui",
    "gtfb.ui.tray",
    "gtfb.ui.icons",
    "gtfb.ui.manager",
    "gtfb.ui.settings_window",
    "gtfb.ui.extension_dialog",
    "gtfb.api",
    "gtfb.api.server",
    "gtfb.api.handler",
    "gtfb.api.status_store",
]

a = Analysis(
    [app_py],
    pathex=[src_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="gtfb",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowless: No console window!
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
