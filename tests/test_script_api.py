"""Unit and integration tests for scripts/test_api.py verification runner."""

import json
from pathlib import Path
import socket
import sys
from typing import Generator, Tuple
import pytest

from gtfb.api.server import APIServer
from gtfb.config.models import BlockRule, ConfigProfile
from scripts.test_api import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    discover_base_url,
    get_default_config_dir,
    main,
    make_request,
    run_tests,
)


def _get_free_port() -> int:
    """Find a random available port on loopback."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def running_api_server(tmp_path: Path) -> Generator[Tuple[APIServer, int, str], None, None]:
    """Fixture that spins up an APIServer on a free port with sample config."""
    free_port = _get_free_port()
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    profile = ConfigProfile(
        block_rules=[
            BlockRule(
                domains=["example.com"],
                start_hour=22,
                start_minute=0,
                end_hour=6,
                end_minute=0,
                active=True,
            )
        ]
    )

    server = APIServer(
        host="127.0.0.1",
        port=free_port,
        config_provider=lambda: profile,
        config_dir=config_dir,
    )
    server.start()
    base_url = f"http://127.0.0.1:{server.bound_port}"

    yield server, server.bound_port, base_url

    server.stop()


def test_discover_base_url_explicit_base_url():
    """Explicit base_url parameter should take precedence."""
    assert discover_base_url(base_url="http://localhost:9999/") == "http://localhost:9999"


def test_discover_base_url_explicit_port():
    """Explicit port parameter should format standard URL."""
    assert discover_base_url(host="127.0.0.1", port=8888) == "http://127.0.0.1:8888"


def test_discover_base_url_from_file(tmp_path: Path):
    """Port should be discovered from api_port.json in config directory."""
    port_file = tmp_path / "api_port.json"
    port_file.write_text(json.dumps({"port": 8770, "host": "127.0.0.1"}), encoding="utf-8")

    discovered = discover_base_url(config_dir=tmp_path)
    assert discovered == "http://127.0.0.1:8770"


def test_discover_base_url_fallback(tmp_path: Path):
    """When no port file exists, it should fall back to DEFAULT_PORT."""
    discovered = discover_base_url(config_dir=tmp_path / "nonexistent")
    assert str(DEFAULT_PORT) in discovered


def test_get_default_config_dir():
    """Ensure get_default_config_dir returns a valid Path without error."""
    path = get_default_config_dir()
    assert isinstance(path, Path)
    assert "GTFB" in str(path) or "gtfb" in str(path)


def test_run_tests_against_live_server(running_api_server):
    """Run full test suite against active APIServer."""
    server, port, base_url = running_api_server
    assert run_tests(base_url) is True


def test_make_request_get_and_post(running_api_server):
    """Verify make_request returns expected status codes and payloads."""
    server, port, base_url = running_api_server

    # GET /health
    status, headers, body = make_request(base_url, "/health")
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert data["status"] == "ok"

    # POST /status
    status, headers, body = make_request(
        base_url,
        "/status",
        method="POST",
        data={"browser": "chrome", "version": "1.0.0"},
    )
    assert status == 200
    data = json.loads(body.decode("utf-8"))
    assert data["status"] == "received"


def test_cli_main_success(running_api_server):
    """main() should return 0 when targeting a running server."""
    server, port, base_url = running_api_server
    exit_code = main(["--base-url", base_url])
    assert exit_code == 0


def test_cli_main_failure_unreachable():
    """main() should return non-zero when targeting an unused port."""
    unused_port = _get_free_port()
    exit_code = main(["--port", str(unused_port)])
    assert exit_code != 0
