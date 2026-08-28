"""HTTP request handler for GTFB local API server."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
import json
import logging
from typing import Any, Dict
from urllib.parse import urlparse

logger = logging.getLogger("gtfb.api")


class GTFBRequestHandler(BaseHTTPRequestHandler):
    """Base request handler for GTFB embedded localhost API with CORS support."""

    def _send_cors_headers(self) -> None:
        """Attach standard Cross-Origin Resource Sharing (CORS) headers."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _send_json_response(self, status_code: int, data: Dict[str, Any]) -> None:
        """Send a JSON HTTP response with CORS headers and Content-Length."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        """Handle incoming HTTP GET requests."""
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json_response(
                200,
                {
                    "status": "ok",
                    "app": "gtfb",
                    "version": "1.0.0",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            self._send_json_response(404, {"error": "Not Found", "path": self.path})

    def log_message(self, format: str, *args: Any) -> None:
        """Forward server access logs to Python logging system instead of stderr."""
        try:
            message = format % args if args else format
        except Exception:
            message = format
        logger.debug("API %s - %s", self.address_string(), message)

