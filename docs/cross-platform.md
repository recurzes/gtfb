# Cross-Platform Architecture & Compatibility Guide

This document details GTFB's cross-platform architecture, system dependencies, tray backends, window management, and privilege requirements across **Windows**, **Linux**, and **macOS**.

---

## 1. Platform Support Matrix

| Feature | Windows | Linux (GNOME / KDE / XFCE) | macOS |
| :--- | :--- | :--- | :--- |
| **Primary Tray Backend** | Win32 Shell NotifyIcon (`pystray._win32`) | AppIndicator / GTK3 (`pystray._appindicator`) | AppKit `NSStatusBarItem` (`pystray._darwin`) |
| **GUI Process Detection** | `pywin32` (visible HWND enumeration) or `psutil` | `psutil` + `DISPLAY` / `WAYLAND_DISPLAY` patterns | `psutil` + `.app` bundle inspection |
| **Graceful App Closing** | `WM_CLOSE` via `pywin32` &rarr; `proc.terminate()` | `SIGTERM` (`proc.terminate()`) &rarr; `proc.kill()` | `osascript` / `SIGTERM` &rarr; `proc.kill()` |
| **OS Shutdown Trigger** | `shutdown /s /t <sec>` (Native) | `shutdown -h +1` (Requires `sudo` / polkit) | `sudo shutdown -h +1` (Requires `sudo`) |
| **Privilege Requirements** | Standard user for app closing; admin optional | Standard user for apps; root for shutdown | Standard user for apps; root for shutdown |

---

## 2. System Tray Backend (`pystray`)

GTFB uses `pystray` combined with `Pillow` for dynamic icon rendering and system tray interaction.

### Windows
- **Backend:** `pystray._win32`
- **Dependencies:** Standard Windows Python installation. No external system packages required.
- **Behavior:** The tray icon is placed in the taskbar notification area / overflow tray. Left-click or right-click opens the context menu.

### Linux
- **Backend:** `pystray._appindicator` (preferred) / `pystray._gtk` / `pystray._xorg`
- **System Prerequisites:**
  - **Debian / Ubuntu:**
    ```bash
    sudo apt-get install libayatana-appindicator3-1 gir1.2-ayatanaappindicator3-0.1
    ```
  - **GNOME Shell (Ubuntu 20.04+ / Debian):** Install `gnome-shell-extension-appindicator` or ensure AppIndicator extension is active.
  - **Fedora / RHEL:**
    ```bash
    sudo dnf install libappindicator-gtk3
    ```
  - **Arch Linux:**
    ```bash
    sudo pacman -S libappindicator-gtk3
    ```
- **Fallback:** If AppIndicator is unavailable, `pystray` falls back to GTK3 or X11 status icons. If running in a headless environment without `DISPLAY` or `WAYLAND_DISPLAY`, GTFB CLI mode (`gtfb --cli`) should be used.

### macOS
- **Backend:** `pystray._darwin` (AppKit Cocoa)
- **UI Thread Requirement:** On macOS, the Cocoa run loop **must run on the main thread**. GTFB adheres strictly to this requirement: `TrayApp.run()` blocks on the main thread while background tasks (`BedtimeScheduler` and status update polling) run on dedicated daemon worker threads.

---

## 3. Process Detection & Graceful Closing

GTFB isolates user-facing GUI applications from background system services before initiating shutdown.

### Windows
1. **Window-based Detection (Default with `pywin32`):**
   - Enumerates top-level visible HWNDs via `win32gui.EnumWindows`.
   - Filters out tool windows (`WS_EX_TOOLWINDOW`) and system services.
   - Dispatches `WM_CLOSE` to trigger application-native save prompts and clean exits.
2. **Heuristic Fallback (without `pywin32`):**
   - If `pywin32` is not installed or encounters an error, GTFB falls back to inspecting user session ownership (`USERNAME`), thread counts (`num_threads > 1`), and `psutil.terminate()`.

### Linux
1. **Environment & Pattern Matching:**
   - Detects active display session (`DISPLAY` or `WAYLAND_DISPLAY`).
   - Filters process names against `LINUX_GUI_PATTERNS` (browsers, IDEs, media players, chat apps) while excluding desktop environment daemons (`gnome-shell`, `wayland`, `dbus`, `pulseaudio`, etc.).
2. **Closing:** Sends `SIGTERM` to allow processes to save state and exit gracefully, waiting up to the configured grace period (default: 5.0 seconds) before escalating to `SIGKILL`.

### macOS
1. **Application Bundle Inspection:**
   - Detects processes running within `/Applications/` and ending in `.app`.
   - Matches process names against `MACOS_GUI_PATTERNS`.
2. **Permissions Note:** Window closing via AppleScript (`osascript`) or accessibility automation requires Accessibility permissions under:
   `System Settings` &rarr; `Privacy & Security` &rarr; `Accessibility`.

---

## 4. Packaging & Dependency Strategy

To ensure seamless installation and execution on all platforms:
- In `pyproject.toml`, platform-specific packages are conditional:
  ```toml
  dependencies = [
      "pillow>=10.0.0",
      "psutil>=7.2.2",
      "pystray>=0.19.5",
      "pywin32>=312; sys_platform == 'win32'",
  ]
  ```
- All modules import OS-specific libraries (`win32gui`, `win32con`, `win32process`) inside conditional checks and `try...except` blocks with fallback mechanisms.
- **Standalone OS Packaging with PyInstaller:**
  - **Windows:** Spec at `packaging/windows/gtfb.spec`, automated build script `scripts/build_windows.py` / `build_windows.bat` creating a windowless `gtfb.exe` binary. See [BUILD_WINDOWS.md](BUILD_WINDOWS.md).
  - **macOS:** Spec at `packaging/macos/gtfb.spec`, automated build script `scripts/build_macos.py` / `build_macos.sh` creating native `GTFB.app` bundle with `LSUIElement=true` (runs as a top menu bar agent app without a Dock icon). See [BUILD_MACOS.md](BUILD_MACOS.md) for full build instructions and Gatekeeper bypass guide.
  - **Linux:** Spec at `packaging/linux/gtfb.spec`, automated build script `scripts/build_linux.py` / `build_linux.sh` producing standalone ELF binary and XDG desktop entry `packaging/linux/gtfb.desktop`. See [BUILD_LINUX.md](BUILD_LINUX.md) for distribution prerequisites and menu integration.


---

## 5. System Diagnostics Command

GTFB includes a platform diagnostic tool to verify environment readiness and active backends.

### Usage

Run via CLI flag:
```bash
gtfb --check-system
# or
gtfb --diagnostics
```

Or execute the diagnostic module directly:
```bash
python -m gtfb.core.platform_utils
```

### Sample Output

```text
============================================================
 GTFB System & Platform Diagnostics Report
============================================================

[Operating System]
  OS System:        Windows
  OS Release:       11
  OS Version:       10.0.26200
  Platform:         Windows-11-10.0.26200-SP0
  Architecture:     AMD64
  Python Version:   3.12.13
  Elevated Privs:   No (Standard User)

[System Tray Backend]
  pystray:          Available (v0.19.5)
  Tray Backend:     pystray._win32
  Pillow (PIL):     Available (v12.3.0)

[Process Inspection & Automation Tools]
  psutil:           Available (v7.2.2)
  pywin32:          Available

[Display & Session Environment]
  User:             username

[Detected GUI Applications]
  Active GUI Apps:  4
    - Visual Studio Code
    - Google Chrome
    - Slack
    - Spotify

[Platform Notes & Recommendations]
  * Windows: pywin32 is active (WM_CLOSE graceful window closing supported).
  * Note: Running without administrator/root privileges (GUI closing works; OS shutdown requires elevation).

============================================================
```
