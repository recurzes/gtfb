"""Thread-safe in-memory store for browser extension status telemetry."""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, Optional


class ExtensionStatusStore:
    """Thread-safe repository for extension heartbeat pulses and enforcement states."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_status: Optional[Dict[str, Any]] = None
        self._last_received_at: Optional[datetime] = None
        self._browsers: Dict[str, Dict[str, Any]] = {}

    def update_status(self, payload: Dict[str, Any]) -> None:
        """Store the latest status payload from an extension heartbeat.

        Args:
            payload: JSON dictionary containing extension state details.
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            self._latest_status = dict(payload)
            self._last_received_at = now

            browser_name = str(payload.get("browser", "browser")).strip().lower()
            self._browsers[browser_name] = {
                "payload": dict(payload),
                "received_at": now,
            }

    def get_status(self, browser: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return the latest reported status including reception timestamp.

        Args:
            browser: Optional specific browser name to query (e.g. 'chrome', 'edge').

        Returns:
            Dictionary with extension payload and '_received_at' ISO timestamp,
            or None if no status heartbeat has been received yet.
        """
        with self._lock:
            if browser:
                browser_key = browser.strip().lower()
                entry = self._browsers.get(browser_key)
                if not entry:
                    return None
                return {
                    **entry["payload"],
                    "_received_at": entry["received_at"].isoformat(),
                }

            if not self._latest_status:
                return None
            return {
                **self._latest_status,
                "_received_at": (
                    self._last_received_at.isoformat()
                    if self._last_received_at
                    else None
                ),
            }

    def get_connected_browsers(self, timeout_seconds: float = 60.0) -> list[Dict[str, Any]]:
        """Return status dictionaries of all browsers with active heartbeats within timeout window."""
        with self._lock:
            if not self._last_received_at:
                return []
            now = datetime.now(timezone.utc)
            if (now - self._last_received_at).total_seconds() > timeout_seconds:
                return []
            active: list[Dict[str, Any]] = []
            for b_name, entry in self._browsers.items():
                elapsed = (now - entry["received_at"]).total_seconds()
                if elapsed <= timeout_seconds:
                    active.append({
                        **entry["payload"],
                        "_received_at": entry["received_at"].isoformat(),
                    })
            return active

    def is_connected(self, timeout_seconds: float = 60.0, browser: Optional[str] = None) -> bool:
        """Check whether an extension heartbeat was received within the timeout window.

        Args:
            timeout_seconds: Maximum allowed elapsed seconds since the last heartbeat.
            browser: Optional specific browser name to check.

        Returns:
            True if a pulse was received within timeout_seconds, False otherwise.
        """
        with self._lock:
            if not self._last_received_at:
                return False
            now = datetime.now(timezone.utc)
            if (now - self._last_received_at).total_seconds() > timeout_seconds:
                return False

            if browser:
                browser_key = browser.strip().lower()
                entry = self._browsers.get(browser_key)
                if not entry:
                    return False
                return (now - entry["received_at"]).total_seconds() <= timeout_seconds

            return True


    def clear(self) -> None:
        """Reset the status store to its initial empty state."""
        with self._lock:
            self._latest_status = None
            self._last_received_at = None
            self._browsers.clear()

