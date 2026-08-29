"""Thread-safe UI Manager coordinating all Tkinter windows on a dedicated UI thread."""

from concurrent.futures import Future
import logging
import queue
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any, Callable, Optional

from gtfb.config.models import ConfigProfile

logger = logging.getLogger("gtfb.ui.manager")


class UIManager:
    """Singleton UI Manager running a single Tkinter root and event loop on a dedicated thread."""

    _instance: Optional["UIManager"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self.root: Optional[tk.Tk] = None
        self._thread: Optional[threading.Thread] = None
        self._ready_event = threading.Event()
        self._stop_event = threading.Event()
        self._task_queue: queue.Queue = queue.Queue()
        self._settings_window: Optional[Any] = None
        self._extension_setup_window: Optional[Any] = None

    @classmethod
    def get_instance(cls) -> "UIManager":
        """Return global singleton UIManager instance, initializing if needed."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance


    @property
    def is_running(self) -> bool:
        """Return True if UI thread is alive and initialized."""
        return self._thread is not None and self._thread.is_alive() and self._ready_event.is_set()

    def start(self) -> None:
        """Start the background UI thread if not already running."""
        with self._lock:
            if self.is_running:
                return
            self._stop_event.clear()
            self._ready_event.clear()
            self._thread = threading.Thread(
                target=self._ui_thread_main,
                name="GTFB-UIThread",
                daemon=True,
            )
            self._thread.start()

        # Wait until root is initialized
        self._ready_event.wait(timeout=5.0)

    def _ui_thread_main(self) -> None:
        """Main loop of the dedicated Tkinter UI thread."""
        try:
            self.root = tk.Tk()
            self.root.withdraw()  # Hidden root container
            self._ready_event.set()

            # Schedule periodic queue polling on UI thread
            self._poll_tasks()

            self.root.mainloop()
        except Exception as err:
            logger.exception("Fatal error in UIManager event loop: %s", err)
        finally:
            self._ready_event.clear()
            if self.root:
                try:
                    self.root.destroy()
                except Exception:
                    pass
                self.root = None

    def _poll_tasks(self) -> None:
        """Process queued UI tasks on the Tkinter thread."""
        if not self.root or self._stop_event.is_set():
            return

        while not self._task_queue.empty():
            try:
                task_fn, args, kwargs, future = self._task_queue.get_nowait()
                try:
                    res = task_fn(*args, **kwargs)
                    if future and not future.done():
                        future.set_result(res)
                except Exception as ex:
                    if future and not future.done():
                        future.set_exception(ex)
                    logger.debug("Error executing queued UI task: %s", ex)
            except queue.Empty:
                break
            except Exception as ex:
                logger.debug("Error in task polling loop: %s", ex)

        if self.root and not self._stop_event.is_set():
            try:
                self.root.after(50, self._poll_tasks)
            except Exception:
                pass

    def run_on_ui_thread(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute a callable synchronously on the UI thread and return its result."""
        if not self.is_running:
            self.start()

        # If already on the UI thread, call directly
        if threading.current_thread() is self._thread:
            return fn(*args, **kwargs)

        fut: Future[Any] = Future()
        self._task_queue.put((fn, args, kwargs, fut))
        return fut.result(timeout=30.0)

    def post_to_ui_thread(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Schedule a callable asynchronously on the UI thread without blocking."""
        if not self.is_running:
            self.start()

        if threading.current_thread() is self._thread:
            try:
                fn(*args, **kwargs)
            except Exception as err:
                logger.exception("Error executing UI task directly: %s", err)
            return

        self._task_queue.put((fn, args, kwargs, None))

    def open_settings(
        self,
        config: Optional[ConfigProfile] = None,
        on_save_callback: Optional[Callable[[Any], None]] = None,
    ) -> None:
        """Open or bring to front the Settings window on the UI thread."""
        self.post_to_ui_thread(self._open_settings_impl, config, on_save_callback)

    def _open_settings_impl(
        self,
        config: Optional[ConfigProfile] = None,
        on_save_callback: Optional[Callable[[Any], None]] = None,
    ) -> None:
        from gtfb.ui.settings_window import SettingsWindow

        if self._settings_window and hasattr(self._settings_window, "window") and self._settings_window.window:
            try:
                if self._settings_window.window.winfo_exists():
                    if on_save_callback is not None:
                        self._settings_window.on_save_callback = on_save_callback
                    self._settings_window.bring_to_front()
                    return
            except Exception:
                self._settings_window = None

        self._settings_window = SettingsWindow(
            master=self.root,
            config=config,
            on_save_callback=on_save_callback,
            on_close_callback=self._on_settings_closed,
        )
        self._settings_window.show()

    def _on_settings_closed(self) -> None:
        self._settings_window = None

    def open_extension_setup(
        self,
        on_close_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Open or bring to front the Extension Setup assistant on the UI thread."""
        self.post_to_ui_thread(self._open_extension_setup_impl, on_close_callback)

    def _open_extension_setup_impl(
        self,
        on_close_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        from gtfb.ui.extension_dialog import ExtensionSetupWindow

        if self._extension_setup_window and hasattr(self._extension_setup_window, "window") and self._extension_setup_window.window:
            try:
                if self._extension_setup_window.window.winfo_exists():
                    self._extension_setup_window.bring_to_front()
                    return
            except Exception:
                self._extension_setup_window = None

        self._extension_setup_window = ExtensionSetupWindow(
            master=self.root,
            on_close_callback=lambda: self._on_extension_setup_closed(on_close_callback),
        )
        self._extension_setup_window.show()

    def _on_extension_setup_closed(self, extra_callback: Optional[Callable[[], None]] = None) -> None:
        self._extension_setup_window = None
        if extra_callback:
            try:
                extra_callback()
            except Exception as err:
                logger.debug("Error in setup window extra callback: %s", err)

    def prompt_extension_consent(self) -> bool:
        """Display the first-time extension consent messagebox safely on the UI thread."""
        def _show_dialog() -> bool:
            title = "GTFB — Browser Extension Setup"
            message = (
                "GTFB requires the companion browser extension to enforce bedtime website "
                "blocking and synchronize your bedtime schedule.\n\n"
                "The extension is essential to make the app properly working.\n\n"
                "Would you like GTFB to install and configure the browser extension now?"
            )
            return bool(messagebox.askyesno(title=title, message=message, parent=self.root))

        try:
            return bool(self.run_on_ui_thread(_show_dialog))
        except Exception as err:
            logger.debug("Error showing consent dialog on UI thread: %s", err)
            return False

    def close_all_windows(self) -> None:
        """Close open child windows on the UI thread without destroying the UI thread root."""
        def _close() -> None:
            if self._settings_window:
                try:
                    self._settings_window.close()
                except Exception as err:
                    logger.debug("Error closing settings window: %s", err)
                self._settings_window = None

            if self._extension_setup_window:
                try:
                    self._extension_setup_window.close()
                except Exception as err:
                    logger.debug("Error closing extension setup window: %s", err)
                self._extension_setup_window = None

        if self.is_running:
            self.run_on_ui_thread(_close)

    def shutdown(self) -> None:
        """Gracefully close open windows and stop the UI thread."""
        with self._lock:
            self._stop_event.set()
            if self.root:
                try:
                    if self._settings_window:
                        self._settings_window.close()
                    if self._extension_setup_window:
                        self._extension_setup_window.close()
                    self.root.quit()
                except Exception as err:
                    logger.debug("Error closing UI root on shutdown: %s", err)

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
                self._thread = None
            UIManager._instance = None


