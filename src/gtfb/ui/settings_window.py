"""Settings window UI for GTFB desktop configuration."""

import logging
from pathlib import Path
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, Optional

from gtfb.config.models import ConfigProfile
from gtfb.config.storage import load_config

logger = logging.getLogger("gtfb.ui.settings")


class BedtimeSection(ttk.LabelFrame):
    """UI Section for configuring Bedtime Enforcement and App Closing schedule."""

    def __init__(self, parent: tk.Misc, config: Optional[ConfigProfile] = None) -> None:
        super().__init__(parent, text="Bedtime Enforcement", padding="12")
        self.config: ConfigProfile = config if config is not None else ConfigProfile()
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct form widgets for bedtime schedule parameters."""
        schedule = self.config.app_close_schedule

        # Enable / Disable enforcement checkbox
        self.var_enabled = tk.BooleanVar(value=schedule.enabled)
        self.chk_enabled = ttk.Checkbutton(
            self,
            text="Enable Bedtime App Closing",
            variable=self.var_enabled,
        )
        self.chk_enabled.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Hour input (0-23)
        self.lbl_hour = ttk.Label(self, text="Hour (0-23):")
        self.lbl_hour.grid(row=1, column=0, sticky="w", pady=4)
        self.var_hour = tk.StringVar(value=f"{schedule.target_hour:02d}")
        self.spin_hour = ttk.Spinbox(
            self,
            from_=0,
            to=23,
            textvariable=self.var_hour,
            width=6,
            format="%02.0f",
        )
        self.spin_hour.set(f"{schedule.target_hour:02d}")
        self.spin_hour.grid(row=1, column=1, sticky="w", pady=4, padx=(8, 0))

        # Minute input (0-59)
        self.lbl_minute = ttk.Label(self, text="Minute (0-59):")
        self.lbl_minute.grid(row=2, column=0, sticky="w", pady=4)
        self.var_minute = tk.StringVar(value=f"{schedule.target_minute:02d}")
        self.spin_minute = ttk.Spinbox(
            self,
            from_=0,
            to=59,
            textvariable=self.var_minute,
            width=6,
            format="%02.0f",
        )
        self.spin_minute.set(f"{schedule.target_minute:02d}")
        self.spin_minute.grid(row=2, column=1, sticky="w", pady=4, padx=(8, 0))

        # Grace Period input (seconds before force kill)
        self.lbl_grace = ttk.Label(self, text="Grace Period (seconds):")
        self.lbl_grace.grid(row=3, column=0, sticky="w", pady=4)
        self.var_grace_period = tk.IntVar(value=schedule.grace_period_seconds)
        self.spin_grace = ttk.Spinbox(
            self,
            from_=0,
            to=300,
            textvariable=self.var_grace_period,
            width=6,
        )
        self.spin_grace.set(str(schedule.grace_period_seconds))
        self.spin_grace.grid(row=3, column=1, sticky="w", pady=4, padx=(8, 0))

    def validate_and_get(self) -> Dict[str, Any]:
        """Validate hour, minute, and grace period inputs and return schedule settings dict.

        Raises:
            ValueError: If hour, minute, or grace period values are invalid or out of range.
        """
        # Validate Hour
        try:
            raw_h = self.spin_hour.get() if hasattr(self, "spin_hour") else str(self.var_hour.get())
            h = int(raw_h)
        except (ValueError, tk.TclError, TypeError):
            raise ValueError("Hour must be an integer between 0 and 23.")

        if not (0 <= h <= 23):
            raise ValueError("Hour must be between 0 and 23.")

        # Validate Minute
        try:
            raw_m = self.spin_minute.get() if hasattr(self, "spin_minute") else str(self.var_minute.get())
            m = int(raw_m)
        except (ValueError, tk.TclError, TypeError):
            raise ValueError("Minute must be an integer between 0 and 59.")

        if not (0 <= m <= 59):
            raise ValueError("Minute must be between 0 and 59.")

        res: Dict[str, Any] = {
            "enabled": bool(self.var_enabled.get()),
            "target_hour": h,
            "target_minute": m,
        }

        # Validate Grace Period
        if hasattr(self, "var_grace_period"):
            try:
                raw_g = (
                    self.spin_grace.get()
                    if hasattr(self, "spin_grace")
                    else str(self.var_grace_period.get())
                )
                g = int(raw_g)
                if g < 0:
                    raise ValueError("Grace period must be 0 or greater.")
                res["grace_period_seconds"] = g
            except (ValueError, tk.TclError, TypeError) as err:
                if "0 or greater" in str(err):
                    raise
                raise ValueError("Grace period must be a non-negative integer.")

        return res


class SettingsWindow:
    """GTFB Desktop Settings Window (Singleton)."""

    _instance: Optional["SettingsWindow"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        config: Optional[ConfigProfile] = None,
        on_save_callback: Optional[Callable[[Any], None]] = None,
    ) -> None:
        self.config: ConfigProfile = config if config is not None else load_config()
        self.on_save_callback = on_save_callback
        self.root: Optional[tk.Tk] = None
        self._icon_img: Optional[tk.PhotoImage] = None
        self.bedtime_section: Optional[BedtimeSection] = None

    @classmethod
    def get_instance(cls) -> Optional["SettingsWindow"]:
        """Return current active singleton instance if any."""
        return cls._instance

    @classmethod
    def open_or_focus(
        cls,
        config: Optional[ConfigProfile] = None,
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

            instance = cls(config=config, on_save_callback=on_save_callback)
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

            # Bedtime section
            self.bedtime_section = BedtimeSection(main_frame, config=self.config)
            self.bedtime_section.pack(fill=tk.X, pady=(0, 12))

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
