# How to Build GTFB for macOS (Standalone GTFB.app Bundle Guide)

Welcome! If you want to build and bundle **GTFB** directly on your macOS machine into a native, standalone `GTFB.app` application bundle, this guide walks you through every step.

---

## 📋 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Step-by-Step Build Instructions](#2-step-by-step-build-instructions)
   - [Step 1: Open Terminal](#step-1-open-terminal)
   - [Step 2: Navigate to the GTFB Folder](#step-2-navigate-to-the-gtfb-folder)
   - [Step 3: Create and Activate a Virtual Environment](#step-3-create-and-activate-a-virtual-environment)
   - [Step 4: Install Dependencies](#step-4-install-dependencies)
   - [Step 5: Run the Automated Build Script](#step-5-run-the-automated-build-script)
   - [Step 6: Launch Your Built Application](#step-6-launch-your-built-application)
3. [macOS Native Behavior (`LSUIElement`)](#3-macos-native-behavior-lsuielement)
4. [First-Time Launch & Browser Extension Setup](#4-first-time-launch--browser-extension-setup)
5. [macOS Gatekeeper & Permissions Guide](#5-macos-gatekeeper--permissions-guide)
6. [Troubleshooting & Frequently Asked Questions](#6-troubleshooting--frequently-asked-questions)

---

## 1. Prerequisites

Before you begin, ensure you have:

1. **macOS 11 (Big Sur) or newer (Apple Silicon M1/M2/M3/M4 or Intel).**
2. **Python 3.11 or newer installed.**
   - To verify in Terminal:
     ```bash
     python3 --version
     ```
   - If you need Python, install it via [python.org](https://www.python.org/downloads/) or Homebrew:
     ```bash
     brew install python
     ```
3. **The GTFB Source Code.**
   - Clone via Git:
     ```bash
     git clone https://github.com/your-username/gtfb.git
     ```
   - Or extract a downloaded `.zip` archive to a folder of your choice (e.g. `~/Documents/gtfb`).

---

## 2. Step-by-Step Build Instructions

### Step 1: Open Terminal

1. Press <kbd>Cmd</kbd> + <kbd>Space</kbd> to open Spotlight.
2. Type `Terminal` and press <kbd>Return</kbd>.

---

### Step 2: Navigate to the GTFB Folder

Type `cd` followed by the path to your GTFB folder:

```bash
cd ~/Documents/gtfb
```

*(Tip: You can type `cd ` and drag the GTFB folder from Finder directly into Terminal, then press <kbd>Return</kbd>).*

---

### Step 3: Create and Activate a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Once activated, your terminal prompt will show `(.venv)` on the left.

---

### Step 4: Install Dependencies

Install GTFB in editable mode alongside `pyinstaller`:

```bash
pip install -e .
pip install pyinstaller
```

*(If you use [uv](https://github.com/astral-sh/uv), you can simply run `uv sync --dev`).*

---

### Step 5: Run the Automated Build Script

Execute the build script using either helper:

**Option A (Bash script):**
```bash
./scripts/build_macos.sh
```

**Option B (Python build orchestrator):**
```bash
python3 scripts/build_macos.py
```

The build script will:
- Generate the Apple ICNS icon resource (`assets/icons/icon.icns`) with all standard resolutions (16x16 up to 1024x1024 Retina).
- Bundle the desktop tray runner, background bedtime scheduler, local API server, and browser companion extension.
- Package everything into a native `GTFB.app` application bundle inside `dist/`.

---

### Step 6: Launch Your Built Application

When the build finishes, your standalone macOS bundle is located in `dist/`:

```
gtfb/
 └── dist/
      └── GTFB.app   <--- Your native macOS application bundle!
```

To launch GTFB:
- **From Finder:** Double-click `dist/GTFB.app`.
- **From Terminal:**
  ```bash
  open dist/GTFB.app
  ```

---

## 3. macOS Native Behavior (`LSUIElement`)

On macOS, utility apps that live in the menu bar run as background agent applications. 

GTFB configures `LSUIElement = True` in its bundle `Info.plist`:
- **No Dock Icon:** GTFB does not take up space or clutter your macOS Dock while running.
- **Menu Bar Presence:** The GTFB icon appears directly in your top-right macOS menu bar.
- **Native Context Menu:** Clicking the menu bar icon displays the control menu (Status, Next Bedtime, Sync Status, Settings, Extension Setup, Start/Stop, Quit).

---

## 4. First-Time Launch & Browser Extension Setup

When you start GTFB for the first time, an extension onboarding dialog appears:

> **"GTFB requires the companion browser extension to enforce bedtime website blocking and synchronize your bedtime schedule. The extension is essential to make the app properly working. Would you like GTFB to install and configure the browser extension now?"**

### Guided Setup Steps:
1. Click **Yes** on the consent prompt.
2. GTFB deploys the extension files to `~/Library/Application Support/GTFB/extension` and copies the folder path to your clipboard.
3. The **Browser Extension Setup Assistant** window opens:
   - Click the button for your browser (**Google Chrome**, **Microsoft Edge**, **Brave**, or **Mozilla Firefox**) to open its extension management page.
   - Toggle on **Developer mode** (top-right of the extensions page).
   - Click **Load unpacked** (or "Load Temporary Add-on" in Firefox).
   - Press <kbd>Cmd</kbd> + <kbd>Shift</kbd> + <kbd>G</kbd> in the file picker, paste the clipboard path, and click **Select Folder**.
4. The GTFB icon will appear in your browser toolbar.

---

## 5. macOS Gatekeeper & Permissions Guide

### Gatekeeper Bypass for Indie / Unsigned Builds
Because this application is built directly from source and is not signed with an annual paid Apple Developer ID certificate, macOS Gatekeeper may display a security notice on first launch:
> *"GTFB.app cannot be opened because Apple cannot check it for malicious software."*

**How to bypass Gatekeeper safely:**

**Method 1 (GUI):**
1. Open the `dist/` folder in **Finder**.
2. **Right-click** (or <kbd>Control</kbd>-click) on `GTFB.app`.
3. Click **Open** from the context menu.
4. Click **Open** again in the confirmation dialog. (macOS will remember this approval).

**Method 2 (Terminal command):**
```bash
xattr -d com.apple.quarantine dist/GTFB.app
```

---

### macOS Accessibility Permissions
GTFB detects and gracefully closes distracting desktop applications at bedtime. To allow GTFB to automate application closing on macOS:
1. Open **System Settings**.
2. Navigate to **Privacy & Security** &rarr; **Accessibility**.
3. Enable permissions for `GTFB` (or your Terminal if testing from command line).

---

## 6. Troubleshooting & Frequently Asked Questions

### Q: How do I access Settings or change my bedtime schedule?
- Click the GTFB icon in your top-right menu bar.
- Click **Settings...** to open the bedtime and blocklist configuration window.
- Click **Save Settings** to persist changes.

---

### Q: How do I exit GTFB?
- Click the GTFB icon in the top menu bar.
- Select **Quit**.

---

### Q: How do I move GTFB to my Applications folder?
You can drag `dist/GTFB.app` directly into `/Applications`:
```bash
cp -R dist/GTFB.app /Applications/
```

---

### Q: How do I clean up build files?
To delete temporary build artifacts before rebuilding:
```bash
rm -rf build/ dist/
```
Then run `./scripts/build_macos.sh` again.
