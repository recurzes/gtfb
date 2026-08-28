"""Embedded HTTP server for GTFB localhost communication."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import logging
import threading
from typing import Any, Callable, Optional, Type

from gtfb.api.handler import GTFBRequestHandler

logger = logging.getLogger("gtfb.api")

DEFAULT_PORT = 8765


def _is_loopback_host(host: str) -> bool:
    """Validate if a host string resolves to a loopback address."""
    if host.lower() in {"127.0.0.1", "localhost", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return ip.is_loopback
    except ValueError:
        return False


class APIServer:
    """Lightweight local HTTP server bound strictly to loopback interfaces."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
        handler_cls: Type[BaseHTTPRequestHandler] = GTFBRequestHandler,
        config_provider: Optional[Callable[[], Any]] = None,
    ) -> None:
        if not _is_loopback_host(host):
            raise ValueError(
                f"Security violation: APIServer must bind strictly to loopback interface (127.0.0.1 / localhost), got: '{host}'"
            )
        self.host = host
        self.port = port
        self.handler_cls = handler_cls
        self.config_provider = config_provider
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        """Check if server thread is actively running."""
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the local HTTP server in a background daemon thread."""
        if self.is_running:
            logger.warning("APIServer is already running.")
            return

        self.server = HTTPServer((self.host, self.port), self.handler_cls)
        if self.config_provider is not None:
            self.server.config_provider = self.config_provider
        self._thread = threading.Thread(
            target=self.server.serve_forever,
            name="APIServerThread",
            daemon=True,
        )
        self._thread.start()
        logger.info("Local API server running at http://%s:%s", self.host, self.port)

    def stop(self) -> None:
        """Gracefully stop and close the local HTTP server."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception as err:
                logger.debug("Error during server shutdown/close: %s", err)
            finally:
                self.server = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("Local API server stopped.")
