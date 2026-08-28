"""HTTP request handler for GTFB local API server."""

from http.server import BaseHTTPRequestHandler
import logging
from typing import Any

logger = logging.getLogger("gtfb.api")


class GTFBRequestHandler(BaseHTTPRequestHandler):
    """Base request handler for GTFB embedded localhost API with CORS support."""

    def _send_cors_headers(self) -> None:
        """Attach standard Cross-Origin Resource Sharing (CORS) headers."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Forward server access logs to Python logging system instead of stderr."""
        try:
            message = format % args if args else format
        except Exception:
            message = format
        logger.debug("API %s - %s", self.address_string(), message)
