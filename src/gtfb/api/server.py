"""Embedded HTTP server for GTFB localhost communication."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import logging
import os
from pathlib import Path
import threading
from typing import Any, Callable, Optional, Type, Union

from gtfb.api.handler import GTFBRequestHandler
from gtfb.api.status_store import ExtensionStatusStore
from gtfb.config.storage import get_config_dir

logger = logging.getLogger("gtfb.api")

DEFAULT_PORT = 8765
START_PORT = 8765
MAX_PORT = 8775


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
    """Lightweight local HTTP server bound strictly to loopback interfaces with port fallback."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        start_port: int = START_PORT,
        max_port: int = MAX_PORT,
        handler_cls: Type[BaseHTTPRequestHandler] = GTFBRequestHandler,
        config_provider: Optional[Callable[[], Any]] = None,
        status_store: Optional[ExtensionStatusStore] = None,
        config_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        if not _is_loopback_host(host):
            raise ValueError(
                f"Security violation: APIServer must bind strictly to loopback interface (127.0.0.1 / localhost), got: '{host}'"
            )
        self.host = host
        if port is not None:
            self.start_port = port
            self.max_port = port if max_port == MAX_PORT else max_port
        else:
            self.start_port = start_port
            self.max_port = max_port
        self.port = self.start_port
        self.bound_port: Optional[int] = None
        self.handler_cls = handler_cls
        self.config_provider = config_provider
        self.status_store: ExtensionStatusStore = (
            status_store if status_store is not None else ExtensionStatusStore()
        )
        self.config_dir: Optional[Path] = (
            Path(config_dir) if config_dir is not None else None
        )
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        """Check if server thread is actively running."""
        return self._thread is not None and self._thread.is_alive()

    def _get_port_file_path(self) -> Path:
        """Return the path to the api_port.json discovery file."""
        base_dir = self.config_dir if self.config_dir is not None else get_config_dir()
        return base_dir / "api_port.json"

    def _write_port_file(self, port: int) -> None:
        """Write the active port, host, PID, and timestamp to api_port.json."""
        port_file = self._get_port_file_path()
        port_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "port": port,
            "host": self.host,
            "pid": os.getpid(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(port_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _cleanup_port_file(self) -> None:
        """Safely remove the api_port.json file on shutdown."""
        port_file = self._get_port_file_path()
        if port_file.exists():
            try:
                port_file.unlink()
            except OSError as err:
                logger.debug("Error removing port file %s: %s", port_file, err)

    def start(self) -> None:
        """Start the local HTTP server in a background daemon thread with port fallback."""
        if self.is_running:
            logger.warning("APIServer is already running.")
            return

        self.server = None
        self.bound_port = None

        for port in range(self.start_port, self.max_port + 1):
            try:
                self.server = HTTPServer((self.host, port), self.handler_cls)
                self.bound_port = port
                self.port = port
                self._write_port_file(port)
                logger.info("Local API successfully bound to port %d", port)
                break
            except OSError as e:
                logger.warning("Port %d in use, attempting next port: %s", port, e)

        if not self.server or self.bound_port is None:
            raise RuntimeError(
                f"Could not bind local API server to any port in range {self.start_port}-{self.max_port}"
            )

        if self.config_provider is not None:
            self.server.config_provider = self.config_provider
        if self.status_store is not None:
            self.server.status_store = self.status_store

        self._thread = threading.Thread(
            target=self.server.serve_forever,
            name="APIServerThread",
            daemon=True,
        )
        self._thread.start()
        logger.info("Local API server running at http://%s:%s", self.host, self.bound_port)

    def stop(self) -> None:
        """Gracefully stop and close the local HTTP server and clean up port file."""
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
        self.bound_port = None
        self._cleanup_port_file()
        logger.info("Local API server stopped.")
