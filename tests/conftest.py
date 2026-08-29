"""Pytest configuration and environment setup for GTFB test suite."""

import os
from pathlib import Path
import sys

# Ensure Tkinter / Tcl libraries are discovered reliably on Windows under uv environments
if sys.platform == "win32":
    tcl_dir = Path(sys.base_prefix) / "tcl" / "tcl8.6"
    tk_dir = Path(sys.base_prefix) / "tcl" / "tk8.6"
    if tcl_dir.is_dir():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
    if tk_dir.is_dir():
        os.environ.setdefault("TK_LIBRARY", str(tk_dir))
