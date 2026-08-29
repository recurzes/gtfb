# GTFB (Get The F*** to Bed)

GTFB is a cross-platform anti-distraction bedtime automation tool designed to enforce healthy digital habits by gracefully closing open desktop applications and triggering a scheduled system shutdown at bedtime.

## Repository Layout

```
gtfb/
├── assets/                  # Icons and static graphical assets
│   └── icons/
├── extension/               # Cross-browser extension (Manifest V3)
├── notes/                   # Architecture notes, specs, and roadmaps
│   ├── specs/
│   ├── GTFB_Branch_Roadmap.md
│   └── GTFB_Masterplan.md
├── old_projects/            # Legacy monolithic prototype scripts
│   └── main.py
├── src/
│   └── gtfb/
│       ├── __init__.py      # Package version and exports
│       ├── app.py           # CLI / GUI runner entry point
│       ├── config.py        # Default configuration values and rules
│       ├── core/            # Core process closing and scheduling engine
│       │   ├── closer.py    # Process termination & shutdown logic
│       │   ├── platform_utils.py # Cross-platform window detection & diagnostics
│       │   └── scheduler.py # Bedtime countdown & trigger loop
│       └── ui/              # Desktop GUI and system tray components
│           ├── icons.py     # Dynamic state icon generation
│           └── tray.py      # Pystray background runner
├── tests/                   # Automated unit and integration tests
├── pyproject.toml           # Packaging metadata and dependencies
├── docs/                    # Architectural and platform guides
│   └── cross-platform.md
└── README.md
```

## Quick Start

### Installation

GTFB uses modern Python packaging via `uv` or `pip`:

```bash
# Using uv (recommended)
uv sync
uv pip install -e .

# Or using standard pip
pip install -e .
```

### CLI Usage

```bash
# Check platform readiness and system tray backend
gtfb --check-system

# Run a dry-run check to list detectable GUI apps without closing anything
gtfb --dry-run
# or
python -m gtfb.app --dry-run

# Run bedtime scheduler for 22:30 without shutting down OS
gtfb --hour 22 --minute 30 --no-shutdown

# Run standard bedtime automation (closes apps at 22:00 and shuts down)
gtfb
```

### Windows Standalone Executable (.exe)

You can build a windowless standalone `gtfb.exe` binary that runs without requiring Python installed:

```powershell
# Run the automated Windows build
python scripts/build_windows.py

# Or double-click scripts/build_windows.bat in File Explorer
```

For a comprehensive, beginner-friendly walkthrough, see the [Windows Build Guide](docs/BUILD_WINDOWS.md).

### Browser Companion Extension

GTFB includes a companion browser extension for Google Chrome, Microsoft Edge, Brave, and Mozilla Firefox that blocks distracting websites and synchronizes rules with the desktop application.

- On first launch, GTFB prompts for consent to deploy the extension to your profile (`%APPDATA%/GTFB/extension`) and opens the Extension Setup Assistant.
- You can also re-open the setup assistant anytime from the system tray menu via **Extension Setup...**.

For detailed platform prerequisites (Linux AppIndicator packages, macOS permissions, Windows specifics), see [docs/cross-platform.md](docs/cross-platform.md).

### Running Tests

```bash
uv run pytest
```

