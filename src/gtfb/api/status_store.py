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

    def update_status(self, payload: Dict[str, Any]) -> None:
        """Store the latest status payload from an extension heartbeat.

        Args:
            payload: JSON dictionary containing extension state details.
        """
        with self._lock:
            self._latest_status = dict(payload)
            self._last_received_at = datetime.now(timezone.utc)

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Return the latest reported status including reception timestamp.

        Returns:
            Dictionary with extension payload and '_received_at' ISO timestamp,
            or None if no status heartbeat has been received yet.
        """
        with self._lock:
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

    def is_connected(self, timeout_seconds: float = 60.0) -> bool:
        """Check whether an extension heartbeat was received within the timeout window.

        Args:
            timeout_seconds: Maximum allowed elapsed seconds since the last heartbeat.

        Returns:
            True if a pulse was received within timeout_seconds, False otherwise.
        """
        with self._lock:
            if not self._last_received_at:
                return False
            elapsed = (datetime.now(timezone.utc) - self._last_received_at).total_seconds()
            return elapsed <= timeout_seconds

    def clear(self) -> None:
        """Reset the status store to its initial empty state."""
        with self._lock:
            self._latest_status = None
            self._last_received_at = None
