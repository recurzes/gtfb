"""HTTP request handler for GTFB local API server."""

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
import json
import logging
import queue
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger("gtfb.api")


class GTFBRequestHandler(BaseHTTPRequestHandler):
    """Base request handler for GTFB embedded localhost API with CORS support."""

    config_provider: Optional[Callable[[], Any]] = None
    status_store: Optional[Any] = None

    def handle(self) -> None:
        """Handle multiple requests until disconnected, ignoring normal client connection aborts."""
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError, OSError) as err:
            logger.debug("Client connection closed: %s", err)


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
        elif parsed.path == "/events":
            try:
                server_inst = getattr(self.server, "api_server_instance", None)
                provider = (
                    getattr(self.server, "config_provider", None)
                    or self.config_provider
                )
                if provider is not None:
                    cfg = provider()
                    if isinstance(cfg, dict):
                        config_data = cfg
                    elif hasattr(cfg, "to_dict"):
                        config_data = cfg.to_dict()
                    else:
                        config_data = dict(cfg)
                else:
                    from gtfb.config.storage import get_config_path, load_config_resilient

                    config_data = load_config_resilient(get_config_path()).to_dict()

                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self._send_cors_headers()
                self.end_headers()

                # Send initial state event
                init_msg = json.dumps({
                    "type": "init",
                    "config": config_data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                self.wfile.write(f"data: {init_msg}\n\n".encode("utf-8"))
                self.wfile.flush()

                client_q: queue.Queue = queue.Queue()
                if server_inst is not None:
                    server_inst.register_sse_client(client_q)

                try:
                    while True:
                        try:
                            event = client_q.get(timeout=15.0)
                            if event is None:
                                break
                            payload = json.dumps(event)
                            self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                            self.wfile.flush()
                        except queue.Empty:
                            # Keepalive comment
                            self.wfile.write(b": ping\n\n")
                            self.wfile.flush()
                finally:
                    if server_inst is not None:
                        server_inst.unregister_sse_client(client_q)

            except (ConnectionResetError, BrokenPipeError, OSError) as err:
                logger.debug("SSE client disconnected: %s", err)
            except Exception as err:
                logger.exception("Error in /events SSE stream: %s", err)

        elif parsed.path == "/config":
            try:
                provider = (
                    getattr(self.server, "config_provider", None)
                    or self.config_provider
                )
                if provider is not None:
                    cfg = provider()
                    if isinstance(cfg, dict):
                        config_data = cfg
                    elif hasattr(cfg, "to_dict"):
                        config_data = cfg.to_dict()
                    else:
                        config_data = dict(cfg)
                else:
                    from gtfb.config.storage import get_config_path, load_config_resilient

                    config_data = load_config_resilient(get_config_path()).to_dict()

                self._send_json_response(200, config_data)
            except Exception as err:
                logger.exception("Error processing /config request: %s", err)
                self._send_json_response(
                    500,
                    {
                        "error": "Internal Server Error",
                        "message": str(err),
                    },
                )
        else:
            self._send_json_response(404, {"error": "Not Found", "path": self.path})


    def do_POST(self) -> None:
        """Handle incoming HTTP POST requests."""
        parsed = urlparse(self.path)
        if parsed.path == "/status":
            try:
                content_length_header = self.headers.get("Content-Length")
                if content_length_header is None:
                    self._send_json_response(400, {"error": "Missing Content-Length header"})
                    return

                try:
                    content_length = int(content_length_header)
                except ValueError:
                    self._send_json_response(400, {"error": "Invalid Content-Length header"})
                    return

                if content_length < 0:
                    self._send_json_response(400, {"error": "Invalid Content-Length"})
                    return

                if content_length > 65536:
                    try:
                        self.rfile.read(content_length)
                    except Exception:
                        pass
                    self._send_json_response(413, {"error": "Payload too large"})
                    return

                body = self.rfile.read(content_length).decode("utf-8")
                payload = json.loads(body)

                if not isinstance(payload, dict):
                    self._send_json_response(400, {"error": "Invalid JSON payload: root must be an object"})
                    return

                store = (
                    getattr(self.server, "status_store", None)
                    or self.status_store
                )
                if store is not None:
                    store.update_status(payload)

                self._send_json_response(200, {"status": "received"})
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json_response(400, {"error": "Invalid JSON"})
            except Exception as err:
                logger.exception("Error processing /status POST request: %s", err)
                self._send_json_response(500, {"error": str(err)})
        else:
            self._send_json_response(404, {"error": "Not Found", "path": self.path})

    def log_message(self, format: str, *args: Any) -> None:
        """Forward server access logs to Python logging system instead of stderr."""
        try:
            message = format % args if args else format
        except Exception:
            message = format
        logger.debug("API %s - %s", self.address_string(), message)

