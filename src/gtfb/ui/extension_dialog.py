"""Extension installation consent and setup assistant UI dialog."""

import logging
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, Optional

from gtfb.core.extension_installer import (
    copy_extension_path_to_clipboard,
    deploy_extension_files,
    detect_installed_browsers,
    get_installed_extension_dir,
    is_first_run_completed,
    open_browser_extension_page,
    open_folder_in_explorer,
    set_first_run_completed,
)

logger = logging.getLogger(__name__)


class ExtensionSetupWindow:
    """Guided UI Assistant for loading the GTFB browser extension."""

    _instance: Optional["ExtensionSetupWindow"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        master: Optional[tk.Misc] = None,
        on_close_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        self.master = master
        self.on_close_callback = on_close_callback
        self.window: Optional[tk.Toplevel | tk.Tk] = None
        self.root: Optional[tk.Toplevel | tk.Tk] = None
        self.browsers = detect_installed_browsers()
        self.extension_dir = deploy_extension_files()

    @classmethod
    def open_or_focus(cls, on_close_callback: Optional[Callable[[], None]] = None) -> "ExtensionSetupWindow":
        """Open or bring to focus the singleton setup assistant window via UIManager."""
        from gtfb.ui.manager import UIManager

        ui_mgr = UIManager.get_instance()
        ui_mgr.open_extension_setup(on_close_callback=on_close_callback)
        return cls._instance or cls(on_close_callback=on_close_callback)

    def show(self) -> None:
        """Create and display the setup window."""
        self._build_and_run()
        ExtensionSetupWindow._instance = self

    def bring_to_front(self) -> None:
        """Deiconify and lift window to top."""
        win = self.window or self.root
        if not win:
            return
        try:
            win.deiconify()
            win.lift()
            win.focus_force()
        except Exception as err:
            logger.debug("Error bringing extension setup window to front: %s", err)

    def _build_and_run(self) -> None:
        """Construct the Tkinter window."""
        if self.master is not None:
            self.window = tk.Toplevel(self.master)
        else:
            self.window = tk.Tk()

        self.root = self.window
        self.window.title("GTFB — Browser Extension Setup")
        self.window.geometry("620x540")
        self.window.minsize(560, 480)
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

        # Style configuration
        style = ttk.Style(self.window)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        main_frame = ttk.Frame(self.window, padding="16")
        main_frame.pack(fill="both", expand=True)

        # Header Title & Description
        header_title = ttk.Label(
            main_frame,
            text="GTFB Browser Extension Setup",
            font=("Segoe UI", 14, "bold"),
        )
        header_title.pack(anchor="w", pady=(0, 4))

        desc_text = (
            "The GTFB companion extension enforces bedtime website blocking and synchronizes "
            "rules with the desktop app. It is essential for full bedtime protection."
        )
        lbl_desc = ttk.Label(main_frame, text=desc_text, wraplength=560)
        lbl_desc.pack(anchor="w", pady=(0, 12))

        # Extension Folder Location Section
        loc_frame = ttk.LabelFrame(main_frame, text="1. Extension Location", padding="10")
        loc_frame.pack(fill="x", pady=(0, 12))

        path_var = tk.StringVar(master=self.window, value=str(self.extension_dir))
        entry_path = ttk.Entry(loc_frame, textvariable=path_var, state="readonly", font=("Consolas", 9))
        entry_path.pack(fill="x", pady=(0, 8))

        btn_box = ttk.Frame(loc_frame)
        btn_box.pack(fill="x")

        self.lbl_copied = ttk.Label(btn_box, text="", font=("Segoe UI", 9, "italic"), foreground="green")
        self.lbl_copied.pack(side="left")

        btn_copy = ttk.Button(btn_box, text="Copy Path", command=self._on_copy_path)
        btn_copy.pack(side="right", padx=(6, 0))

        btn_explore = ttk.Button(btn_box, text="Open Folder in Explorer", command=self._on_open_folder)
        btn_explore.pack(side="right")

        # Browser Installation Section
        browser_frame = ttk.LabelFrame(main_frame, text="2. Add to Your Browser", padding="10")
        browser_frame.pack(fill="both", expand=True, pady=(0, 12))

        instruction_text = (
            "Steps to load in Chrome, Edge, Brave, or Firefox:\n"
            "  1. Click your browser button below to open its Extensions management page.\n"
            "  2. Enable 'Developer mode' toggle (top right / menu).\n"
            "  3. Click 'Load unpacked' and select the GTFB extension folder.\n"
            "     (For Firefox: click 'Load Temporary Add-on' and choose manifest.json)."
        )
        lbl_inst = ttk.Label(browser_frame, text=instruction_text, justify="left", font=("Segoe UI", 9))
        lbl_inst.pack(anchor="w", pady=(0, 10))

        # Detected Browser Buttons
        btn_grid = ttk.Frame(browser_frame)
        btn_grid.pack(fill="x", pady=(4, 4))

        installed_count = 0
        for b_key, b_info in self.browsers.items():
            if b_info.get("installed"):
                installed_count += 1
                b_name = b_info.get("name", b_key.title())
                btn = ttk.Button(
                    btn_grid,
                    text=f"Open {b_name} Extensions Page",
                    command=lambda k=b_key: self._on_open_browser(k),
                )
                btn.pack(fill="x", pady=2)

        if installed_count == 0:
            # Fallback generic button
            btn_generic = ttk.Button(
                btn_grid,
                text="Open Default Browser Extensions Page",
                command=lambda: open_browser_extension_page("chrome"),
            )
            btn_generic.pack(fill="x", pady=2)

        # Bottom Actions
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill="x", pady=(8, 0))

        btn_done = ttk.Button(bottom_frame, text="Done / Finish Setup", command=self._on_close)
        btn_done.pack(side="right")

        # Auto-copy path on open for user convenience
        copy_extension_path_to_clipboard(self.extension_dir)
        self.lbl_copied.config(text="✓ Folder path copied to clipboard!")

        # Center on screen
        self.window.update_idletasks()
        w = self.window.winfo_width()
        h = self.window.winfo_height()
        ws = self.window.winfo_screenwidth()
        hs = self.window.winfo_screenheight()
        x = (ws // 2) - (w // 2)
        y = (hs // 2) - (h // 2)
        self.window.geometry(f"+{x}+{y}")

        self.bring_to_front()

        if isinstance(self.window, tk.Tk):
            self.window.mainloop()

    def _on_copy_path(self) -> None:
        """Copy extension directory path to clipboard."""
        copy_extension_path_to_clipboard(self.extension_dir)
        if hasattr(self, "lbl_copied") and self.lbl_copied:
            self.lbl_copied.config(text="✓ Folder path copied to clipboard!")

    def _on_open_folder(self) -> None:
        """Open the extension folder in Windows Explorer."""
        open_folder_in_explorer(self.extension_dir)

    def _on_open_browser(self, browser_key: str) -> None:
        """Launch the specified browser to its extensions management page."""
        open_browser_extension_page(browser_key, self.browsers)

    def _on_close(self) -> None:
        """Handle window close event."""
        set_first_run_completed(True)
        if self.window:
            try:
                if self.window.winfo_exists():
                    self.window.destroy()
            except Exception:
                pass
            self.window = None
            self.root = None

        with ExtensionSetupWindow._lock:
            ExtensionSetupWindow._instance = None

        if self.on_close_callback:
            try:
                self.on_close_callback()
            except Exception as err:
                logger.debug("Error in setup window on_close_callback: %s", err)

    def close(self) -> None:
        """Public method to close window."""
        self._on_close()


def prompt_extension_installation_consent() -> bool:
    """Prompt user with a native consent dialog for installing the browser extension."""
    from gtfb.ui.manager import UIManager

    return UIManager.get_instance().prompt_extension_consent()


def check_and_run_first_time_setup(force: bool = False) -> None:
    """Check first-run status and run extension onboarding assistant if needed."""
    if not force and is_first_run_completed():
        return

    # Deploy extension files upfront
    deploy_extension_files()

    if force:
        ExtensionSetupWindow.open_or_focus()
        return

    # Ask for consent first
    user_agreed = prompt_extension_installation_consent()
    set_first_run_completed(True)

    if user_agreed:
        logger.info("User consented to browser extension setup. Opening setup assistant.")
        ExtensionSetupWindow.open_or_focus()
    else:
        logger.info("User deferred browser extension setup. Available via tray menu.")

