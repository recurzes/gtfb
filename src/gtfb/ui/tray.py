"""System tray application runner using pystray and Pillow."""

from enum import Enum
import logging
from pathlib import Path
import threading
from typing import Callable, Optional, Union

from PIL import Image
import pystray
from pystray import Menu, MenuItem as item

from gtfb.api.server import APIServer
from gtfb.config.models import ConfigProfile
from gtfb.core.scheduler import BedtimeScheduler, SchedulerState
from gtfb.ui.icons import (
    STATE_COLORS,
    create_state_icon,
    generate_fallback_icon,
    get_icon,
    load_tray_icon,
)
from gtfb.ui.settings_window import SettingsWindow

logger = logging.getLogger("gtfb.ui.tray")


def create_menu(app_instance: "TrayApp") -> Menu:
    """Construct the system tray context menu."""
    return app_instance.build_menu()


class TrayApp:
    """GTFB Desktop System Tray Application."""

    def __init__(
        self,
        icon_path: Optional[Union[Path, str]] = None,
        scheduler: Optional[BedtimeScheduler] = None,
        on_quit: Optional[Callable[[], None]] = None,
        api_server: Optional[APIServer] = None,
    ) -> None:
        self.icon_path = icon_path
        self.scheduler = scheduler or BedtimeScheduler()
        self.on_quit_callback = on_quit
        self.api_server = api_server if api_server is not None else APIServer()
        self.current_state: str = "STOPPED"
        self._updater_thread: Optional[threading.Thread] = None
        self._updater_stop_event = threading.Event()

        initial_state = self.scheduler.state if self.scheduler else SchedulerState.STOPPED
        self.icon_image = self._load_icon(icon_path, state=initial_state)
        self.menu = self._create_menu()
        self.icon = pystray.Icon(
            name="gtfb",
            icon=self.icon_image,
            title="GTFB: Stopped",
            menu=self.menu,
        )
        self.update_tray_state(initial_state)

    def _load_icon(
        self,
        icon_path: Optional[Union[Path, str]] = None,
        state: Union[str, Enum] = SchedulerState.STOPPED,
    ) -> Image.Image:
        """Load icon asset for the given state or generate fallback."""
        return get_icon(state=state, icon_path=icon_path)

    def _create_menu(self) -> Menu:
        """Create tray context menu."""
        return self.build_menu()

    def update_tray_state(
        self,
        state: Optional[Union[str, Enum]] = None,
        detail: Optional[str] = None,
    ) -> None:
        """Dynamically update tray icon image and tooltip title based on state.

        Args:
            state: Optional state override ('STOPPED', 'COUNTING_DOWN', 'ENFORCING').
            detail: Optional status detail string (e.g. countdown time).
        """
        if state is None:
            state = self.scheduler.state if self.scheduler else SchedulerState.STOPPED
        if detail is None and self.scheduler:
            detail = self.scheduler.get_status_detail()

        state_key = state.value if isinstance(state, Enum) else str(state).upper()
        self.current_state = state_key

        if self.icon:
            self.icon.icon = get_icon(state_key, icon_path=self.icon_path)
            state_title = state_key.replace("_", " ").title()
            if detail:
                self.icon.title = f"GTFB: {state_title} ({detail})"
            else:
                self.icon.title = f"GTFB: {state_title}"

    def _status_updater_loop(self) -> None:
        """Background loop to periodically refresh tooltip countdown and icon state."""
        while not self._updater_stop_event.is_set():
            try:
                self.update_tray_state()
                if self.icon:
                    self.icon.update_menu()
            except Exception as err:
                logger.debug("Error updating tray status: %s", err)
            self._updater_stop_event.wait(timeout=1.0)

    def _start_status_updater(self) -> None:
        """Start the background status updater thread."""
        if self._updater_thread and self._updater_thread.is_alive():
            return
        self._updater_stop_event.clear()
        self._updater_thread = threading.Thread(
            target=self._status_updater_loop,
            name="TrayStatusUpdater",
            daemon=True,
        )
        self._updater_thread.start()

    def _stop_status_updater(self) -> None:
        """Signal and join the background status updater thread."""
        self._updater_stop_event.set()
        if self._updater_thread and self._updater_thread.is_alive():
            self._updater_thread.join(timeout=1.0)

    def is_scheduler_running(self, item: Optional[pystray.MenuItem] = None) -> bool:
        """Return True if the bedtime scheduler is active and running."""
        return self.scheduler.is_running() if self.scheduler else False

    def is_scheduler_stopped(self, item: Optional[pystray.MenuItem] = None) -> bool:
        """Return True if the bedtime scheduler is currently stopped."""
        return not self.is_scheduler_running(item)

    def on_start(self, icon: Optional[pystray.Icon] = None, item: Optional[pystray.MenuItem] = None) -> None:
        """Handle Start Scheduler menu action."""
        logger.info("Starting scheduler from tray menu...")
        if self.scheduler:
            self.scheduler.start()
        self.update_tray_state()
        if self.icon:
            self.icon.update_menu()

    def on_stop(self, icon: Optional[pystray.Icon] = None, item: Optional[pystray.MenuItem] = None) -> None:
        """Handle Stop Scheduler menu action."""
        logger.info("Stopping scheduler from tray menu...")
        if self.scheduler:
            self.scheduler.stop()
        self.update_tray_state()
        if self.icon:
            self.icon.update_menu()

    def on_settings_saved(self, new_config: ConfigProfile) -> None:
        """Callback invoked when settings are saved in SettingsWindow."""
        logger.info("Settings saved. Updating active scheduler...")
        if self.scheduler:
            self.scheduler.update_config(new_config)
        self.update_tray_state()
        if self.icon:
            self.icon.update_menu()

    def on_open_settings(
        self,
        icon: Optional[pystray.Icon] = None,
        item: Optional[pystray.MenuItem] = None,
    ) -> None:
        """Handle Open Settings menu action."""
        logger.info("Opening GTFB settings window from tray menu...")
        threading.Thread(
            target=SettingsWindow.open_or_focus,
            kwargs={"on_save_callback": self.on_settings_saved},
            name="GTFBSettingsWindowThread",
            daemon=True,
        ).start()

    def build_menu(self) -> Menu:
        """Construct dynamic tray context menu."""
        return Menu(
            item(
                lambda text: f"Status: {'Running' if self.is_scheduler_running() else 'Stopped'}",
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            item("Settings...", self.on_open_settings),
            item(
                "Start Scheduler",
                self.on_start,
                visible=lambda item: not self.is_scheduler_running(),
            ),
            item(
                "Stop Scheduler",
                self.on_stop,
                visible=lambda item: self.is_scheduler_running(),
            ),
            Menu.SEPARATOR,
            item("Quit", self.on_quit),
        )

    def run(self, setup: Optional[Callable[[pystray.Icon], None]] = None) -> None:
        """Start the bedtime scheduler, status updater, API server, and system tray event loop."""
        logger.info("Starting GTFB system tray application...")
        if self.scheduler:
            self.scheduler.start()
        if self.api_server:
            try:
                self.api_server.start()
            except Exception as err:
                logger.exception("Error starting local API server: %s", err)
        self._start_status_updater()
        self.update_tray_state()
        self.icon.run(setup=setup)

    def on_quit(self, icon: Optional[pystray.Icon] = None, item: Optional[item] = None) -> None:
        """Handle Quit menu action and stop the system tray icon."""
        logger.info("Shutting down GTFB system tray application...")
        self._stop_status_updater()

        # Close active settings window if open
        settings_instance = SettingsWindow.get_instance()
        if settings_instance:
            try:
                settings_instance.close()
            except Exception as err:
                logger.debug("Error closing settings window on quit: %s", err)

        if self.scheduler:
            try:
                self.scheduler.stop()
            except Exception as err:
                logger.exception("Error stopping scheduler: %s", err)

        if self.api_server:
            try:
                self.api_server.stop()
            except Exception as err:
                logger.exception("Error stopping local API server: %s", err)

        if self.on_quit_callback:
            try:
                self.on_quit_callback()
            except Exception as err:
                logger.exception("Error in on_quit callback: %s", err)

        if self.icon:
            self.icon.stop()

    def stop(self) -> None:
        """Programmatically stop the tray application."""
        self.on_quit()
