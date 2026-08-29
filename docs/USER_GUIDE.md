# GTFB (Get The F*** to Bed) — User Overview & User Guide

> **"Remove the friction between intention and action, and add friction where willpower fails."**

---

## Table of Contents

1. [Project Overview & Purpose](#1-project-overview--purpose)
2. [Key Features](#2-key-features)
3. [Architecture at a Glance](#3-architecture-at-a-glance)
4. [Installation & First-Time Setup](#4-installation--first-time-setup)
   - [Method A: Standalone Windows Executable (.exe)](#method-a-standalone-windows-executable-exe)
   - [Method B: Python / Developer Installation](#method-b-python--developer-installation)
5. [User Guide: Configuring & Using GTFB](#5-user-guide-configuring--using-gtfb)
   - [System Tray Icon & Controls](#51-system-tray-icon--controls)
   - [Configuring Bedtime Enforcement](#52-configuring-bedtime-enforcement)
   - [Configuring Website Blocklists](#53-configuring-website-blocklists)
   - [Enabling Windows Startup & Customization](#54-enabling-windows-startup--customization)
   - [Browser Companion Extension Setup](#55-browser-companion-extension-setup)
   - [Command-Line Interface (CLI) Guide](#56-command-line-interface-cli-guide)
6. [Visual Status Indicators & Tray Icons](#6-visual-status-indicators--tray-icons)
7. [File Locations, Logs & Data Safety](#7-file-locations-logs--data-safety)
8. [Privacy & Security Guarantee](#8-privacy--security-guarantee)
9. [Troubleshooting & FAQs](#9-troubleshooting--faqs)

---

## 1. Project Overview & Purpose

### The Problem
Most people who struggle with late-night screen time or daytime digital distractions don't suffer from a lack of awareness — they know when they should be sleeping or working. The problem is **zero friction**: opening a new tab to Reddit, YouTube, or social media takes under two seconds, and dismissing a reminder prompt takes one click.

When temptation offers no resistance, willpower consistently loses.

### The Solution: GTFB
**GTFB** is a local, privacy-first bedtime automation and anti-distraction system. Instead of gentle, easily ignored notifications, GTFB puts real, automated boundaries in place at both the **Operating System level** and the **Browser level**:

1. **At the OS Level:** When bedtime arrives, GTFB gracefully closes user GUI applications (browsers, chat apps, games, media players) and can initiate a clean system shutdown.
2. **At the Browser Level:** The GTFB Companion Browser Extension actively redirects distracting websites to a calm, customizable blocked screen with countdown timers and motivational reminders.

Once configured, GTFB works autonomously in the background without requiring daily intervention.

---

## 2. Key Features

| Feature | Description |
|---|---|
| **System Tray Background Daemon** | Runs unobtrusively in your system tray with live tooltip countdowns and dynamic colored status icons. |
| **Smart Application Closer** | Distinguishes between user applications and critical system processes. Gracefully requests apps to close (`WM_CLOSE`/`SIGTERM`), waiting through a configurable grace period before fallback force-closing. |
| **Cross-Browser Extension (MV3)** | Supports Google Chrome, Microsoft Edge, Brave, and Mozilla Firefox. Uses native browser declarative rules for ultra-fast, zero-overhead website blocking. |
| **Unified Settings Window** | One clean GUI to manage your bedtime hour, minute, grace period, and blocked website domain list. |
| **Local Real-Time Sync** | The desktop application hosts a secure, loopback-only API that instantly synchronizes settings with your browser extensions via Server-Sent Events (SSE). |
| **Offline Resilience** | The browser extension caches rules locally in browser storage. Even if the desktop tray app is closed, scheduled site blocking continues seamlessly. |
| **Windows Startup Integration** | Easily toggle GTFB to run on Windows login. Fully integrated with Windows Task Manager (`Startup apps`) and Windows Settings. |
| **Resilient Storage Architecture** | Configuration files and logs are stored away from workspace folders in `%APPDATA%\GTFB\` with atomic saves and self-healing backup recovery. |
| **Full CLI & Diagnostics** | Run headless, dry-run process scans, custom schedules, or deep platform compatibility diagnostics via terminal commands. |
| **Zero Telemetry / 100% Local** | No cloud servers, no account registration, no data collection. All operations happen strictly on your machine. |

---

## 3. Architecture at a Glance

```
┌──────────────────────────────────────────────────────────┐
│                   GTFB Desktop Daemon                    │
│                                                          │
│   ┌──────────────────┐         ┌─────────────────────┐   │
│   │   System Tray    │         │   Settings Window   │   │
│   │  (Pystray + PIL) │         │  (Tkinter Form GUI) │   │
│   └────────┬─────────┘         └──────────┬──────────┘   │
│            │                              │              │
│            ▼                              ▼              │
│   ┌──────────────────────────────────────────────────┐   │
│   │           Bedtime Scheduler & Engine             │   │
│   │   - Tracks bedtime countdown                     │   │
│   │   - Closes GUI apps (psutil / pywin32)           │   │
│   │   - Handles OS shutdown timer                    │   │
│   └────────────────────────┬─────────────────────────┘   │
│                            │                             │
│                            ▼                             │
│   ┌──────────────────────────────────────────────────┐   │
│   │        Embedded Local HTTP / SSE API Server      │   │
│   │         (Bound strictly to 127.0.0.1)            │   │
│   └────────────────────────┬─────────────────────────┘   │
└────────────────────────────┼─────────────────────────────┘
                             │  (Local REST & SSE Sync)
                             ▼
┌──────────────────────────────────────────────────────────┐
│          Companion Browser Extension (Manifest V3)       │
│                                                          │
│   Chrome  •  Edge  •  Brave  •  Firefox                  │
│                                                          │
│   - declarativeNetRequest block rules                    │
│   - Local schedule & domain cache                        │
│   - Custom blocked page with countdown                   │
└──────────────────────────────────────────────────────────┘
```

---

## 4. Installation & First-Time Setup

### Method A: Standalone Windows Executable (.exe)
*Recommended for Windows users who do not want to install Python.*

1. **Build or Download the Standalone Binary:**
   Run `scripts/build_windows.bat` or `python scripts/build_windows.py` to generate `dist\gtfb.exe`.
2. **Launch:** Double-click `gtfb.exe`.
3. **Tray Appearance:** GTFB will launch windowless directly into your Windows system tray (near the clock).

---

### Method B: Python / Developer Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/recurzes/gtfb.git
   cd gtfb
   ```

2. **Install with uv or pip:**
   ```bash
   # Using uv
   uv pip install -e .

   # Or standard pip
   pip install -e .
   ```

3. **Launch the application:**
   ```bash
   gtfb
   ```

---

## 5. User Guide: Configuring & Using GTFB

### 5.1 System Tray Icon & Controls
Right-clicking the GTFB tray icon opens the context menu:

- **Status:** Displays whether the scheduler is currently active or stopped.
- **Extension:** Shows live companion browser extension connection status (e.g. `● Extension: Connected (Chrome, Firefox — Active)`).
- **Settings...:** Opens the main configuration window.
- **Extension Setup...:** Launches the browser extension installation assistant.
- **Start / Stop Scheduler:** Manually pause or resume bedtime monitoring.
- **Quit:** Cleanly closes the tray daemon and all UI windows.

---

### 5.2 Configuring Bedtime Enforcement

1. Right-click the system tray icon and select **Settings...**.
2. Under **Bedtime Enforcement**:
   - **Enable Bedtime App Closing:** Check to turn bedtime enforcement on.
   - **Hour (0-23):** Enter your target bedtime hour in 24-hour format (e.g. `22` for 10:00 PM, `23` for 11:00 PM).
   - **Minute (0-59):** Enter your target bedtime minute (e.g. `00` or `30`).
   - **Grace Period (seconds):** Number of seconds GTFB waits after sending a graceful close command (`WM_CLOSE`) before force-closing stubborn applications (default: `15` seconds).
3. Click **Save Settings**.

---

### 5.3 Configuring Website Blocklists

1. Open **Settings...** from the tray icon.
2. Under **Website Blocklist**:
   - Type a domain into the text box (e.g. `reddit.com`, `youtube.com`, `twitter.com`, `x.com`, `instagram.com`).
   - Press **Enter** or click **Add Domain**.
   - *Note: URLs are automatically sanitized — entering `https://www.youtube.com/watch?v=...` automatically extracts `youtube.com`.*
   - To remove a site, click the domain in the list and click **Remove Selected**.
3. Click **Save Settings**. Changes are instantly broadcast to all open browser extensions.

---

### 5.4 Enabling Windows Startup & Customization

GTFB makes it easy to ensure your bedtime protection is always active whenever your computer turns on:

1. Open **Settings...** from the tray icon.
2. Under **Windows Startup**:
   - Check **Launch GTFB on Windows Startup**.
   - Click **Save Settings**.
3. **Customizing via Windows:**
   - Click the **Open Startup Folder** button to inspect the shortcut in File Explorer (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GTFB.lnk`).
   - You can also view and toggle GTFB at any time inside **Windows Task Manager > Startup apps** tab or **Windows Settings > Apps > Startup**.

---

### 5.5 Browser Companion Extension Setup

On your first run, GTFB prompts to install the companion extension. You can also open the installer assistant anytime by selecting **Extension Setup...** from the tray menu.

```
┌──────────────────────────────────────────────────────────┐
│             GTFB Browser Extension Setup                 │
├──────────────────────────────────────────────────────────┤
│  1. Open your browser's Extensions page:                 │
│     • Chrome:   chrome://extensions                      │
│     • Edge:     edge://extensions                        │
│     • Brave:    brave://extensions                       │
│     • Firefox:  about:debugging#/runtime/this-firefox    │
│                                                          │
│  2. Enable "Developer Mode" (toggle at top-right).       │
│                                                          │
│  3. Click "Load unpacked" and select:                    │
│     %APPDATA%\GTFB\extension                             │
└──────────────────────────────────────────────────────────┘
```

Once loaded:
- The extension connects automatically to the GTFB background daemon.
- When bedtime arrives, visiting any blocked domain displays the GTFB focus shield:

```
┌──────────────────────────────────────────────────────────┐
│                   🌙 GET TO BED!                         │
│                                                          │
│      reddit.com is blocked during scheduled bedtime.     │
│                                                          │
│                 Bedtime Window: 22:00                    │
│                                                          │
│        "Sleep is the best meditation." — Dalai Lama      │
└──────────────────────────────────────────────────────────┘
```

---

### 5.6 Command-Line Interface (CLI) Guide

GTFB includes powerful terminal options:

```bash
# Run system & platform capability diagnostics
gtfb --check-system

# Perform a dry-run scan (lists detected GUI apps without closing anything)
gtfb --dry-run

# Run bedtime enforcement for 23:15 without shutting down the computer
gtfb --hour 23 --minute 15 --no-shutdown

# Run in foreground CLI mode instead of system tray
gtfb --cli --hour 22 --minute 0

# Register GTFB in Windows Startup
gtfb --install-startup

# Remove GTFB from Windows Startup
gtfb --remove-startup

# Open Windows Startup folder in File Explorer
gtfb --open-startup-folder
```

---

## 6. Visual Status Indicators & Tray Icons

The system tray icon dynamically updates its color and appearance based on current system state:

| Icon Color | Status | Meaning |
|:---:|:---|:---|
| ⚪ **Grey** | `STOPPED` | Scheduler is stopped/inactive. No apps will be closed. |
| 🔵 **Blue** | `COUNTING_DOWN` | Active countdown. Hover over the icon to view the exact time remaining. |
| 🔴 **Red** | `ENFORCING` | Bedtime has arrived. GTFB is actively closing GUI apps and enforcing blocks. |

---

## 7. File Locations, Logs & Data Safety

To ensure users do not accidentally move or delete vital files, GTFB isolates all persistent data within OS-standard application directories:

| Platform | Configuration & Log Directory |
|---|---|
| **Windows** | `%APPDATA%\GTFB\` (e.g. `C:\Users\<User>\AppData\Roaming\GTFB\`) |
| **macOS** | `~/Library/Application Support/GTFB/` |
| **Linux** | `~/.config/gtfb/` or `$XDG_CONFIG_HOME/gtfb/` |

### Key Files:
- **`config.json`**: Primary settings file (schedule, domain blocklist, grace period).
- **`config.bak`**: Automatic self-healing backup file created before every atomic write.
- **`bedtime.log`**: Application activity and troubleshooting logs.
- **`api_port.json`**: Ephemeral port discovery file used by browser extensions to connect.
- **`extension/`**: Unpacked browser extension files ready for browser installation.

---

## 8. Privacy & Security Guarantee

- **100% Local Execution:** GTFB does not connect to any remote servers, cloud databases, or third-party APIs.
- **Loopback-Only Server:** The embedded API server binds exclusively to `127.0.0.1` (localhost) with strict address validation. Outside network connections are impossible.
- **No Telemetry / No Tracking:** Zero analytics, crash reporting pings, or usage telemetry.
- **Non-Destructive Process Handling:** System-critical processes (`explorer.exe`, `dwm.exe`, `kernel_task`, `systemd`, etc.) are hard-coded in exclusion lists and will never be closed.

---

## 9. Troubleshooting & FAQs

#### Q: Will GTFB close work in progress without warning?
**A:** GTFB first sends standard OS close requests (`WM_CLOSE`/`SIGTERM`), giving applications (like text editors or office suites) the opportunity to prompt to save open files. The grace period (customizable in Settings) determines how long GTFB waits before force-closing.

#### Q: How do I test the app-closing logic safely without closing anything?
**A:** Run `gtfb --dry-run` from your terminal. This scans and displays all detectable GUI apps on your system immediately without closing anything.

#### Q: Why does the browser extension show "Not Connected"?
**A:** Ensure the GTFB system tray app is running. If running for the first time, make sure the unpacked extension from `%APPDATA%\GTFB\extension` is loaded in your browser with Developer Mode enabled.

#### Q: How do I check if my platform supports all features?
**A:** Run `gtfb --check-system` in terminal to generate a comprehensive diagnostic report of your window manager, tray backend, pywin32 status, and privileges.

---

*Sleep well and stay focused with GTFB!*
