# How to Build GTFB for Linux (Standalone Executable Guide)

Welcome! If you want to build and bundle **GTFB** directly on your Linux machine into a native, standalone executable, this guide walks you through every step.

---

## 📋 Table of Contents

1. [Prerequisites & System Libraries](#1-prerequisites--system-libraries)
2. [Step-by-Step Build Instructions](#2-step-by-step-build-instructions)
   - [Step 1: Open Terminal](#step-1-open-terminal)
   - [Step 2: Navigate to the GTFB Folder](#step-2-navigate-to-the-gtfb-folder)
   - [Step 3: Create and Activate a Virtual Environment](#step-3-create-and-activate-a-virtual-environment)
   - [Step 4: Install Dependencies](#step-4-install-dependencies)
   - [Step 5: Run the Automated Build Script](#step-5-run-the-automated-build-script)
   - [Step 6: Launch Your Built Application](#step-6-launch-your-built-application)
3. [Desktop Menu & Icon Integration (`.desktop`)](#3-desktop-menu--icon-integration-desktop)
4. [First-Time Launch & Browser Extension Setup](#4-first-time-launch--browser-extension-setup)
5. [Autostart on Login (Optional)](#5-autostart-on-login-optional)
6. [Troubleshooting & Frequently Asked Questions](#6-troubleshooting--frequently-asked-questions)

---

## 1. Prerequisites & System Libraries

Before building, make sure you have:

1. **A modern Linux distribution (Ubuntu 20.04+, Debian 11+, Fedora 38+, Arch Linux, or openSUSE).**
2. **Python 3.11 or newer installed.**
   - Verify in terminal:
     ```bash
     python3 --version
     ```
3. **AppIndicator / GTK3 System Libraries:**
   GTFB uses system tray indicators (`pystray` with AppIndicator / GTK3 backend). Install the required library for your distribution:

   - **Debian / Ubuntu / Linux Mint / Pop!_OS:**
     ```bash
     sudo apt update
     sudo apt install -y python3-pip python3-venv libayatana-appindicator3-1 gir1.2-ayatanaappindicator3-0.1
     ```
   - **Fedora / RHEL / CentOS Stream:**
     ```bash
     sudo dnf install -y python3-pip python3-devel libappindicator-gtk3
     ```
   - **Arch Linux / Manjaro:**
     ```bash
     sudo pacman -S --needed python python-pip libappindicator-gtk3
     ```
   - **GNOME Shell Users Note:**
     If you use GNOME Shell without built-in tray icon support, install the AppIndicator extension:
     ```bash
     sudo apt install gnome-shell-extension-appindicator
     ```
     *(Or enable "AppIndicator and KStatusNotifierItem Support" via GNOME Extensions).*

---

## 2. Step-by-Step Build Instructions

### Step 1: Open Terminal

Open your favorite terminal emulator (<kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>T</kbd> on most distributions).

---

### Step 2: Navigate to the GTFB Folder

```bash
cd ~/path/to/gtfb
```

---

### Step 3: Create and Activate a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Your prompt will now show `(.venv)`.

---

### Step 4: Install Dependencies

Install GTFB and `pyinstaller`:

```bash
pip install -e .
pip install pyinstaller
```

*(If using [uv](https://github.com/astral-sh/uv), simply run `uv sync --dev`).*

---

### Step 5: Run the Automated Build Script

Execute the build using either helper:

**Option A (Bash script):**
```bash
./scripts/build_linux.sh
```

**Option B (Python build orchestrator):**
```bash
python3 scripts/build_linux.py
```

The build script will:
- Verify multi-resolution application icon assets (`assets/icons/icon.png`).
- Bundle the desktop tray runner, background bedtime scheduler, local API server, and companion browser extension.
- Compile everything into a single, standalone ELF executable in `dist/gtfb`.

---

### Step 6: Launch Your Built Application

When the build finishes, your executable is located at `dist/gtfb`:

```bash
./dist/gtfb
```

The GTFB icon will appear in your desktop panel / system tray, and the local API will listen on `http://127.0.0.1:8765`.

---

## 3. Desktop Menu & Icon Integration (`.desktop`)

To add GTFB to your application launcher (GNOME Dash, KDE Kickoff, XFCE Whisker menu, Rofi, etc.):

1. **Install the executable to your user binary folder:**
   ```bash
   mkdir -p ~/.local/bin
   cp dist/gtfb ~/.local/bin/gtfb
   chmod +x ~/.local/bin/gtfb
   ```
   *(Ensure `~/.local/bin` is in your `$PATH`).*

2. **Install the application icon:**
   ```bash
   mkdir -p ~/.local/share/icons/hicolor/128x128/apps
   cp assets/icons/icon.png ~/.local/share/icons/hicolor/128x128/apps/gtfb.png
   ```

3. **Install the Desktop Entry launcher:**
   ```bash
   mkdir -p ~/.local/share/applications
   cp packaging/linux/gtfb.desktop ~/.local/share/applications/
   update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
   ```

GTFB will now appear in your system application search as **GTFB** with its custom icon.

---

## 4. First-Time Launch & Browser Extension Setup

When you start GTFB for the first time, an extension onboarding dialog appears:

> **"GTFB requires the companion browser extension to enforce bedtime website blocking and synchronize your bedtime schedule. The extension is essential to make the app properly working. Would you like GTFB to install and configure the browser extension now?"**

### Guided Setup Steps:
1. Click **Yes** on the consent prompt.
2. GTFB deploys the extension files to `~/.local/share/gtfb/extension` and copies the folder path to your clipboard.
3. The **Browser Extension Setup Assistant** window opens:
   - Click the button for your browser (**Google Chrome**, **Mozilla Firefox**, **Brave**, or **Microsoft Edge**) to open its extension management page.
   - For Chromium-based browsers: Toggle on **Developer mode**, click **Load unpacked**, paste the copied path, and confirm.
   - For Mozilla Firefox: Navigate to `about:debugging#/runtime/this-firefox`, click **Load Temporary Add-on...**, and select `manifest.json` inside the copied path.
4. The GTFB icon will appear in your browser toolbar and connect to the local API.

---

## 5. Autostart on Login (Optional)

To start GTFB automatically when logging in to your desktop session:

```bash
mkdir -p ~/.config/autostart
cp packaging/linux/gtfb.desktop ~/.config/autostart/
```

---

## 6. Troubleshooting & Frequently Asked Questions

### Q: Why is the tray icon not showing up on Ubuntu / GNOME?
GNOME Shell requires an AppIndicator extension to display top-panel tray icons. Install it with:
```bash
sudo apt install gnome-shell-extension-appindicator
```
Then log out and log back in, or enable it using the **Extensions** app.

---

### Q: How do I open Settings?
Click the GTFB icon in your top panel / system tray and select **Settings...**. Configure your bedtime and blocklist, then click **Save Settings**.

---

### Q: How do I exit GTFB?
Click the GTFB icon in the system tray and select **Quit**.

---

### Q: How do I clean up build files?
To delete temporary build artifacts before rebuilding:
```bash
rm -rf build/ dist/
```
Then re-run `./scripts/build_linux.sh`.
