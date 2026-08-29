# How to Build GTFB for Windows (Standalone Executable Guide)

Welcome! If you prefer to compile and build **GTFB** directly on your own computer instead of downloading pre-built binaries, this guide will walk you through every single step.

Even if you have never used a terminal or compiled software before, you can follow these instructions easily.

---

## 📋 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Step-by-Step Build Instructions](#2-step-by-step-build-instructions)
   - [Step 1: Open PowerShell or Command Prompt](#step-1-open-powershell-or-command-prompt)
   - [Step 2: Navigate to the GTFB Folder](#step-2-navigate-to-the-gtfb-folder)
   - [Step 3: Create and Activate a Virtual Environment](#step-3-create-and-activate-a-virtual-environment)
   - [Step 4: Install Dependencies](#step-4-install-dependencies)
   - [Step 5: Run the Automated Build Script](#step-5-run-the-automated-build-script)
   - [Step 6: Launch Your Built Application](#step-6-launch-your-built-application)
3. [First-Time Launch & Browser Extension Setup](#3-first-time-launch--browser-extension-setup)
4. [Troubleshooting & Frequently Asked Questions](#4-troubleshooting--frequently-asked-questions)

---

## 1. Prerequisites

Before you start, ensure you have:

1. **Python 3.12 or newer installed on your Windows PC.**
   - To verify, press <kbd>Win</kbd> + <kbd>R</kbd>, type `powershell`, press <kbd>Enter</kbd>, and run:
     ```powershell
     python --version
     ```
   - If it outputs `Python 3.12.x` (or higher), you are ready!
   - *(Note: Ensure "Add Python to PATH" was checked during Python installation).*

2. **The GTFB Source Code.**
   - Either clone the repository using Git:
     ```powershell
     git clone https://github.com/your-username/gtfb.git
     ```
   - Or download the repository as a `.zip` file from GitHub and extract it to a folder of your choice (e.g., `C:\Users\YourName\Documents\gtfb`).

---

## 2. Step-by-Step Build Instructions

### Step 1: Open PowerShell or Command Prompt

1. Press <kbd>Win</kbd> + <kbd>S</kbd> on your keyboard.
2. Type **PowerShell** (or **Terminal** on Windows 11).
3. Click to open it.

---

### Step 2: Navigate to the GTFB Folder

Type `cd` followed by a space and the path to your extracted GTFB folder. For example:

```powershell
cd C:\Users\YourName\Documents\gtfb
```

*(Tip: You can type `cd ` and simply drag-and-drop the GTFB folder from File Explorer into the PowerShell window, then press <kbd>Enter</kbd>).*

---

### Step 3: Create and Activate a Virtual Environment

Creating an isolated virtual environment keeps your Python installation clean and ensures all required libraries are installed properly:

1. **Create the environment:**
   ```powershell
   python -m venv .venv
   ```

2. **Activate the environment:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

*(If PowerShell shows a script execution policy restriction, you can enable it for the current session by running: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and then run the activate command again).*

Once activated, your terminal prompt will show `(.venv)` on the left.

---

### Step 4: Install Dependencies

Install GTFB in editable mode along with `PyInstaller`:

```powershell
pip install -e .
pip install pyinstaller
```

*(If you use [uv](https://github.com/astral-sh/uv), you can simply run `uv sync --dev`).*

---

### Step 5: Run the Automated Build Script

You can build the standalone executable with either the Python script or the batch file:

**Option A (PowerShell / Command Prompt):**
```powershell
python scripts/build_windows.py
```

**Option B (One-Click File Explorer):**
- Open File Explorer, go into the `scripts\` folder, and double-click `build_windows.bat`.

The build script will:
- Generate the Windows application icon resource (`icon.ico`).
- Bundle the desktop tray runner, background bedtime scheduler, local API server, and browser extension.
- Package everything into a windowless binary (`gtfb.exe`).

---

### Step 6: Launch Your Built Application

When the build finishes successfully, you will find your standalone application in the `dist\` folder:

```
gtfb\
 └── dist\
      └── gtfb.exe   <--- Your standalone Windows executable!
```

Double-click `dist\gtfb.exe` to run it! 

You will notice:
- **No black terminal window** opens.
- The **GTFB icon appears in your Windows system tray** (bottom-right near your clock).
- The local background API server is running on `http://127.0.0.1:8765`.

---

## 3. First-Time Launch & Browser Extension Setup

When you start GTFB for the first time, a setup prompt will appear:

> **"GTFB requires the companion browser extension to enforce bedtime website blocking and synchronize your bedtime schedule. The extension is essential to make the app properly working. Would you like GTFB to install and configure the browser extension now?"**

### Why is the extension essential?
GTFB protects your sleep on two levels:
1. **Desktop Level:** Closes distracting desktop applications and shuts down your PC at bedtime.
2. **Browser Level:** Blocks distracting websites (e.g. YouTube, Reddit, Twitter) inside your browser so you cannot procrastinate in open tabs.

### Guided Setup Steps:
1. Click **Yes** on the consent prompt.
2. GTFB automatically deploys the bundled extension files to your user profile (`%APPDATA%\GTFB\extension`) and copies the folder path to your clipboard.
3. The **Browser Extension Setup Assistant** window opens:
   - Click the button for your browser (**Google Chrome**, **Microsoft Edge**, **Brave**, or **Mozilla Firefox**) to open its extension management page.
   - Turn on the **Developer mode** switch (usually located in the top-right corner of the browser extensions page).
   - Click **Load unpacked** (or "Load Temporary Add-on" in Firefox).
   - Select the GTFB extension folder (or paste the copied path) and click **Select Folder**.
4. The GTFB icon will appear in your browser toolbar!

*(You can re-open this setup assistant at any time by right-clicking the GTFB tray icon and selecting **Extension Setup...**).*

---

## 4. Troubleshooting & Frequently Asked Questions

### Q: Windows SmartScreen says "Windows protected your PC" / "Unknown Publisher"
**Why this happens:**  
Microsoft Windows SmartScreen shows this warning for any executable built from source that does not have a multi-hundred dollar commercial code-signing certificate.

**How to proceed:**  
1. Click **"More info"** on the blue SmartScreen popup.
2. Click **"Run anyway"**.
3. GTFB will launch safely into your system tray.

---

### Q: How do I close or exit GTFB?
- Look for the GTFB icon in your system tray (bottom-right near the clock).
- Right-click the icon and select **Quit**.

---

### Q: How do I change my bedtime or edit blocked websites?
- Right-click the GTFB tray icon.
- Select **Settings...** to open the configuration window.
- Adjust your bedtime hour/minute or customize your blocked domains list, then click **Save Settings**.

---

### Q: How do I clean up build files?
If you want to remove temporary build files before rebuilding, delete the `build\` and `dist\` folders:

```powershell
Remove-Item -Recurse -Force build, dist
```

Then run `python scripts/build_windows.py` again.
