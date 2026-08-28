"""Settings window UI for GTFB desktop configuration."""

import logging
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from gtfb.config.models import BlockRule, ConfigProfile
from gtfb.config.sanitizer import clean_domain_input
from gtfb.config.storage import get_config_path, load_config, save_config_atomic

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
        self.var_enabled = tk.BooleanVar(master=self, value=schedule.enabled)
        self.chk_enabled = ttk.Checkbutton(
            self,
            text="Enable Bedtime App Closing",
            variable=self.var_enabled,
        )
        self.chk_enabled.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # Hour input (0-23)
        self.lbl_hour = ttk.Label(self, text="Hour (0-23):")
        self.lbl_hour.grid(row=1, column=0, sticky="w", pady=4)
        self.var_hour = tk.StringVar(master=self, value=f"{schedule.target_hour:02d}")
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
        self.var_minute = tk.StringVar(master=self, value=f"{schedule.target_minute:02d}")
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
        self.var_grace_period = tk.IntVar(master=self, value=schedule.grace_period_seconds)
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


class BlocklistSection(ttk.LabelFrame):
    """UI Section for viewing, adding, and removing blocked website domains."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_domains: Optional[List[str]] = None,
        config: Optional[ConfigProfile] = None,
    ) -> None:
        super().__init__(parent, text="Website Blocklist", padding="12")
        if initial_domains is not None:
            self.domains: List[str] = list(initial_domains)
        elif config is not None and config.block_rules and len(config.block_rules) > 0:
            self.domains = list(config.block_rules[0].domains)
        else:
            self.domains = []
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct input field, listbox with scrollbar, and action buttons."""
        # Entry + Add row
        entry_frame = ttk.Frame(self)
        entry_frame.pack(fill=tk.X, pady=(0, 8))

        self.entry_domain = ttk.Entry(entry_frame)
        self.entry_domain.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.entry_domain.bind("<Return>", lambda e: self.on_add())

        self.btn_add = ttk.Button(entry_frame, text="Add Domain", command=self.on_add)
        self.btn_add.pack(side=tk.RIGHT)

        # Listbox with Scrollbar
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame, height=8, selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)

        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for d in self.domains:
            self.listbox.insert(tk.END, d)

        # Remove button
        self.btn_remove = ttk.Button(self, text="Remove Selected", command=self.on_remove)
        self.btn_remove.pack(anchor="e", pady=(6, 0))

    def on_add(self) -> None:
        """Sanitize domain input, validate duplicates, and append to domain list."""
        raw = self.entry_domain.get()
        cleaned = clean_domain_input(raw)
        if not cleaned:
            return
        if cleaned in self.domains:
            messagebox.showwarning("Duplicate", f"'{cleaned}' is already in the blocklist.")
            return
        self.domains.append(cleaned)
        self.listbox.insert(tk.END, cleaned)
        self.entry_domain.delete(0, tk.END)

    def on_remove(self) -> None:
        """Remove currently selected domain from the listbox and internal state."""
        selected_idx = self.listbox.curselection()
        if not selected_idx:
            return
        idx = selected_idx[0]
        self.domains.pop(idx)
        self.listbox.delete(idx)

    def get_domains(self) -> List[str]:
        """Return the current list of blocked domains."""
        return list(self.domains)


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
        self.blocklist_section: Optional[BlocklistSection] = None

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
                        if on_save_callback is not None:
                            cls._instance.on_save_callback = on_save_callback
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

    def _center_window(self, width: int = 480, height: int = 580) -> None:
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

    def _add_action_buttons(self, container: tk.Misc) -> None:
        """Add Save and Cancel action buttons."""
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(12, 0))

        btn_cancel = ttk.Button(btn_frame, text="Cancel", command=self._on_close)
        btn_cancel.pack(side=tk.RIGHT, padx=(6, 0))

        btn_save = ttk.Button(btn_frame, text="Save Settings", command=self._on_save)
        btn_save.pack(side=tk.RIGHT)

    def _on_save(self) -> None:
        """Validate inputs, save configuration atomically, notify callback, and close window."""
        try:
            if not self.bedtime_section or not self.blocklist_section:
                return

            bedtime_data = self.bedtime_section.validate_and_get()
            domains = self.blocklist_section.get_domains()

            # Update profile
            self.config.app_close_schedule.enabled = bedtime_data["enabled"]
            self.config.app_close_schedule.target_hour = bedtime_data["target_hour"]
            self.config.app_close_schedule.target_minute = bedtime_data["target_minute"]
            if "grace_period_seconds" in bedtime_data:
                self.config.app_close_schedule.grace_period_seconds = bedtime_data["grace_period_seconds"]

            if not self.config.block_rules:
                self.config.block_rules.append(BlockRule())
            self.config.block_rules[0].domains = domains

            # Save atomically to disk
            save_config_atomic(self.config, get_config_path())

            # Notify live application/scheduler
            if self.on_save_callback:
                self.on_save_callback(self.config)

            self._on_close()
        except Exception as e:
            logger.exception("Error saving settings: %s", e)
            messagebox.showerror("Error Saving Settings", str(e))

    def _create_window(self) -> None:
        """Instantiate and run the Tkinter window mainloop."""
        try:
            self.root = tk.Tk()
            self.root.title("GTFB — Settings")
            self.root.geometry("480x580")
            self.root.resizable(False, False)

            self._set_window_icon()
            self._center_window(480, 580)

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

            # Website blocklist section
            initial_domains = (
                self.config.block_rules[0].domains
                if (self.config.block_rules and len(self.config.block_rules) > 0)
                else []
            )
            self.blocklist_section = BlocklistSection(main_frame, initial_domains=initial_domains)
            self.blocklist_section.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

            # Action buttons
            self._add_action_buttons(main_frame)

            self.root.mainloop()
        except Exception as err:
            logger.exception("Error in SettingsWindow mainloop: %s", err)
        finally:
            self._on_close()

    def _on_close(self) -> None:
        """Cleanly destroy window, exit mainloop, and reset singleton reference."""
        with SettingsWindow._lock:
            if self.root:
                try:
                    if self.root.winfo_exists():
                        self.root.quit()
                        self.root.destroy()
                except Exception as err:
                    logger.debug("Error destroying settings root: %s", err)
                self.root = None

            if SettingsWindow._instance is self:
                SettingsWindow._instance = None

    def close(self) -> None:
        """Public method to close the settings window cleanly across threads."""
        with SettingsWindow._lock:
            if self.root:
                try:
                    if self.root.winfo_exists():
                        self.root.after(0, self._on_close)
                        return
                except Exception as err:
                    logger.debug("Error scheduling settings close: %s", err)
        self._on_close()
