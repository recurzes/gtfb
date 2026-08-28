"""System tray application runner using pystray and Pillow."""

import logging
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw
import pystray
from pystray import Menu, MenuItem as item

from gtfb.core.scheduler import BedtimeScheduler

logger = logging.getLogger("gtfb.ui.tray")


def generate_fallback_icon(width: int = 64, height: int = 64) -> Image.Image:
    """Generate a dynamic fallback RGBA tray icon image.

    Creates an anti-distraction emblem (dark circle badge with crescent moon)
    to ensure the application never crashes due to missing asset files.
    """
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Base circular background
    draw.ellipse([4, 4, width - 4, height - 4], fill=(30, 41, 59, 255), outline=(99, 102, 241, 255), width=2)

    # Crescent moon emblem
    draw.ellipse([18, 16, 46, 44], fill=(251, 191, 36, 255))
    draw.ellipse([25, 12, 51, 40], fill=(30, 41, 59, 255))

    # Star accent
    draw.line([(45, 20), (45, 26)], fill=(253, 230, 138, 255), width=1)
    draw.line([(42, 23), (48, 23)], fill=(253, 230, 138, 255), width=1)

    return image


def load_tray_icon(icon_path: Optional[Path | str] = None) -> Image.Image:
    """Attempt to load a tray icon from file, falling back to dynamic generation."""
    candidates = []
    if icon_path:
        candidates.append(Path(icon_path))

    # Module-relative package asset path
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / "icon.png")
    # Repository root asset path
    candidates.append(Path("assets/icons/icon.png"))
    candidates.append(Path("assets/icon.png"))

    for path in candidates:
        try:
            if path.is_file():
                return Image.open(path).convert("RGBA")
        except Exception as err:
            logger.warning("Failed loading icon from %s: %s", path, err)

    logger.info("Using dynamically generated fallback tray icon")
    return generate_fallback_icon()


def create_menu(app_instance: "TrayApp") -> Menu:
    """Construct the system tray context menu."""
    return app_instance.build_menu()


class TrayApp:
    """GTFB Desktop System Tray Application."""

    def __init__(
        self,
        icon_path: Optional[Path | str] = None,
        scheduler: Optional[BedtimeScheduler] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ) -> None:
        self.scheduler = scheduler or BedtimeScheduler()
        self.on_quit_callback = on_quit
        self.icon_image = self._load_icon(icon_path)
        self.menu = self._create_menu()
        self.icon = pystray.Icon(
            name="gtfb",
            icon=self.icon_image,
            title="GTFB - Anti-Distraction Suite",
            menu=self.menu,
        )

    def _load_icon(self, icon_path: Optional[Path | str] = None) -> Image.Image:
        """Load icon asset or generate fallback."""
        return load_tray_icon(icon_path)

    def _create_menu(self) -> Menu:
        """Create tray context menu."""
        return self.build_menu()

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
        if self.icon:
            self.icon.update_menu()

    def on_stop(self, icon: Optional[pystray.Icon] = None, item: Optional[pystray.MenuItem] = None) -> None:
        """Handle Stop Scheduler menu action."""
        logger.info("Stopping scheduler from tray menu...")
        if self.scheduler:
            self.scheduler.stop()
        if self.icon:
            self.icon.update_menu()

    def build_menu(self) -> Menu:
        """Construct dynamic tray context menu."""
        return Menu(
            item(
                lambda text: f"Status: {'Running' if self.is_scheduler_running() else 'Stopped'}",
                None,
                enabled=False,
            ),
            Menu.SEPARATOR,
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
        """Start the bedtime scheduler and system tray event loop."""
        logger.info("Starting GTFB system tray application...")
        if self.scheduler:
            self.scheduler.start()
        self.icon.run(setup=setup)

    def on_quit(self, icon: Optional[pystray.Icon] = None, item: Optional[item] = None) -> None:
        """Handle Quit menu action and stop the system tray icon."""
        logger.info("Shutting down GTFB system tray application...")
        if self.scheduler:
            try:
                self.scheduler.stop()
            except Exception as err:
                logger.exception("Error stopping scheduler: %s", err)

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

