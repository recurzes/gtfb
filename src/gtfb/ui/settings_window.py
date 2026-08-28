"""Settings window UI for GTFB desktop configuration."""

import logging
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Optional

logger = logging.getLogger("gtfb.ui.settings")


class SettingsWindow:
    """GTFB Desktop Settings Window (Singleton)."""

    _instance: Optional["SettingsWindow"] = None
    _lock = threading.Lock()

    def __init__(self, on_save_callback: Optional[Callable[[Any], None]] = None) -> None:
        self.on_save_callback = on_save_callback
        self.root: Optional[tk.Tk] = None
        self._icon_img: Optional[tk.PhotoImage] = None

    @classmethod
    def get_instance(cls) -> Optional["SettingsWindow"]:
        """Return current active singleton instance if any."""
        return cls._instance

    @classmethod
    def open_or_focus(
        cls,
        on_save_callback: Optional[Callable[[Any], None]] = None,
    ) -> "SettingsWindow":
        """Open settings window or bring existing window into focus."""
        with cls._lock:
            if cls._instance and cls._instance.root:
                try:
                    if cls._instance.root.winfo_exists():
                        cls._instance._bring_to_front()
                        return cls._instance
                except Exception as err:
                    logger.debug("Error checking existing settings window: %s", err)

            instance = cls(on_save_callback=on_save_callback)
            cls._instance = instance

        instance._create_window()
        return instance

    def _bring_to_front(self) -> None:
        """Deiconify and focus the existing window."""
        if not self.root:
            return
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception as err:
            logger.debug("Error bringing settings window to front: %s", err)

    def _set_window_icon(self) -> None:
        """Attempt to set the window icon from packaged assets."""
        if not self.root:
            return
        try:
            asset_dir = Path(__file__).resolve().parent.parent / "assets"
            icon_file = asset_dir / "icon.png"
            if icon_file.exists():
                self._icon_img = tk.PhotoImage(file=str(icon_file))
                self.root.iconphoto(False, self._icon_img)
        except Exception as err:
            logger.debug("Could not set window icon: %s", err)

    def _center_window(self, width: int = 480, height: int = 420) -> None:
        """Center the window on screen."""
        if not self.root:
            return
        try:
            self.root.eval("tk::PlaceWindow . center")
        except Exception:
            try:
                self.root.update_idletasks()
                screen_w = self.root.winfo_screenwidth()
                screen_h = self.root.winfo_screenheight()
                x = max(0, (screen_w - width) // 2)
                y = max(0, (screen_h - height) // 2)
                self.root.geometry(f"{width}x{height}+{x}+{y}")
            except Exception as err:
                logger.debug("Failed centering window geometry: %s", err)

    def _create_window(self) -> None:
        """Instantiate and run the Tkinter window mainloop."""
        try:
            self.root = tk.Tk()
            self.root.title("GTFB — Settings")
            self.root.geometry("480x420")
            self.root.resizable(False, False)

            self._set_window_icon()
            self._center_window(480, 420)

            # Bind close window protocol
            self.root.protocol("WM_DELETE_WINDOW", self._on_close)

            # Main layout frame
            main_frame = ttk.Frame(self.root, padding="16")
            main_frame.pack(fill=tk.BOTH, expand=True)

            # Title label
            title_label = ttk.Label(
                main_frame,
                text="GTFB Configuration",
                font=("Helvetica", 14, "bold"),
            )
            title_label.pack(anchor="w", pady=(0, 12))

            # Placeholder label for upcoming settings controls
            placeholder = ttk.Label(
                main_frame,
                text="Settings fields will be added in upcoming branches.",
            )
            placeholder.pack(expand=True)

            self.root.mainloop()
        except Exception as err:
            logger.exception("Error in SettingsWindow mainloop: %s", err)
        finally:
            self._on_close()

    def _on_close(self) -> None:
        """Cleanly destroy window and reset singleton reference."""
        with SettingsWindow._lock:
            if self.root:
                try:
                    if self.root.winfo_exists():
                        self.root.destroy()
                except Exception as err:
                    logger.debug("Error destroying settings root: %s", err)
                self.root = None

            if SettingsWindow._instance is self:
                SettingsWindow._instance = None

    def close(self) -> None:
        """Public method to close the settings window."""
        self._on_close()
