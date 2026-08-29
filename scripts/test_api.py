#!/usr/bin/env python3
"""GTFB Local API Verification Script.

Tests all localhost API endpoints against a running GTFB desktop instance.
Uses only the Python standard library with zero external dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, Optional, Tuple
import urllib.error
import urllib.request

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def get_default_config_dir(app_name: str = "GTFB") -> Path:
    """Return OS-standard user configuration directory without importing gtfb."""
    if sys.platform.startswith("win"):
        app_data = os.environ.get("APPDATA")
        if app_data:
            return Path(app_data) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    else:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / app_name.lower()
        return Path.home() / ".config" / app_name.lower()


def discover_base_url(
    host: Optional[str] = None,
    port: Optional[int] = None,
    base_url: Optional[str] = None,
    config_dir: Optional[str | Path] = None,
) -> str:
    """Resolve the base URL for the GTFB API via arguments or api_port.json discovery."""
    if base_url:
        return base_url.rstrip("/")

    target_host = host or DEFAULT_HOST

    if port is not None:
        return f"http://{target_host}:{port}"

    # Search config_dir or standard OS config directories for api_port.json
    candidate_dirs = []
    if config_dir:
        candidate_dirs.append(Path(config_dir))
    candidate_dirs.append(get_default_config_dir())
    candidate_dirs.append(Path.cwd())

    for c_dir in candidate_dirs:
        port_file = c_dir / "api_port.json"
        if port_file.is_file():
            try:
                with open(port_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                discovered_port = data.get("port")
                discovered_host = data.get("host") or target_host
                if isinstance(discovered_port, int) and 1 <= discovered_port <= 65535:
                    return f"http://{discovered_host}:{discovered_port}"
            except Exception:
                pass

    return f"http://{target_host}:{DEFAULT_PORT}"


def make_request(
    base_url: str,
    path: str,
    method: str = "GET",
    data: Optional[Dict[str, Any] | list[Any]] = None,
    raw_body: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Tuple[int, Dict[str, str], bytes]:
    """Execute an HTTP request and return (status_code, headers, response_body_bytes)."""
    req_headers = dict(headers or {})
    url = f"{base_url}{path}"

    body_bytes = None
    if raw_body is not None:
        body_bytes = raw_body
        if "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json"
    elif data is not None:
        body_bytes = json.dumps(data).encode("utf-8")
        if "Content-Type" not in req_headers:
            req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body_bytes, method=method, headers=req_headers)

    try:
        with urllib.request.urlopen(req, timeout=2.0) as res:
            res_headers = {k: v for k, v in res.headers.items()}
            return res.status, res_headers, res.read()
    except urllib.error.HTTPError as e:
        err_headers = {k: v for k, v in e.headers.items()}
        return e.code, err_headers, e.read()


def run_tests(base_url: str) -> bool:
    """Run all API endpoint verification tests against base_url.

    Returns True if all tests pass, False otherwise.
    """
    print(f"[*] Testing GTFB Local API at {base_url}...\n")
    all_passed = True

    # --- 1. Health Check ---
    print("[1] Testing GET /health...")
    try:
        status, headers, body = make_request(base_url, "/health")
        assert status == 200, f"Expected 200, got {status}"
        data = json.loads(body.decode("utf-8"))
        assert data.get("status") == "ok", f"Expected status 'ok', got {data.get('status')}"
        assert data.get("app") == "gtfb", f"Expected app 'gtfb', got {data.get('app')}"
        print(f"    -> PASS: status={status}, app={data.get('app')}, version={data.get('version')}")
    except urllib.error.URLError as err:
        print(f"    -> FAIL: Connection error ({err.reason})")
        print(f"\n[ERROR] Server at {base_url} is unreachable. Ensure the GTFB application is running.")
        print("\n" + "=" * 50)
        print("[FAILURE] Cannot connect to GTFB Local API server!\n")
        return False
    except Exception as err:
        print(f"    -> FAIL: {err}")
        all_passed = False

    # --- 2. Configuration Endpoint ---
    print("\n[2] Testing GET /config...")
    try:
        status, headers, body = make_request(base_url, "/config")
        assert status == 200, f"Expected 200, got {status}"
        data = json.loads(body.decode("utf-8"))
        assert "app_close_schedule" in data, "Missing 'app_close_schedule' in config"
        assert "block_rules" in data, "Missing 'block_rules' in config"
        rules_count = len(data.get("block_rules", []))
        print(f"    -> PASS: status={status}, rules_count={rules_count}, has_schedule={'app_close_schedule' in data}")
    except Exception as err:
        print(f"    -> FAIL: {err}")
        all_passed = False

    # --- 3. Extension Status Report ---
    print("\n[3] Testing POST /status (valid telemetry)...")
    try:
        payload = {
            "browser": "test-runner",
            "version": "1.0.0",
            "blocking_active": True,
            "rules_count": 5,
        }
        status, headers, body = make_request(base_url, "/status", method="POST", data=payload)
        assert status == 200, f"Expected 200, got {status}"
        data = json.loads(body.decode("utf-8"))
        assert data.get("status") == "received", f"Expected 'received', got {data.get('status')}"
        print(f"    -> PASS: status={status}, response={data}")
    except Exception as err:
        print(f"    -> FAIL: {err}")
        all_passed = False

    # --- 4. CORS Preflight (OPTIONS) ---
    print("\n[4] Testing OPTIONS /health (CORS Preflight)...")
    try:
        status, headers, _ = make_request(base_url, "/health", method="OPTIONS")
        assert status == 204, f"Expected 204, got {status}"
        allow_origin = headers.get("Access-Control-Allow-Origin") or headers.get("access-control-allow-origin")
        allow_methods = headers.get("Access-Control-Allow-Methods") or headers.get("access-control-allow-methods")
        allow_headers = headers.get("Access-Control-Allow-Headers") or headers.get("access-control-allow-headers")
        assert allow_origin == "*", f"Expected CORS origin '*', got '{allow_origin}'"
        assert allow_methods and "GET" in allow_methods and "POST" in allow_methods, f"Invalid CORS methods: {allow_methods}"
        assert allow_headers and "Content-Type" in allow_headers, f"Invalid CORS headers: {allow_headers}"
        print(f"    -> PASS: status={status}, Origin={allow_origin}, Methods={allow_methods}")
    except Exception as err:
        print(f"    -> FAIL: {err}")
        all_passed = False

    # --- 5. Error Handling: 404 Route ---
    print("\n[5] Testing GET /nonexistent (404 Not Found)...")
    try:
        status, headers, body = make_request(base_url, "/nonexistent")
        assert status == 404, f"Expected 404, got {status}"
        data = json.loads(body.decode("utf-8"))
        assert "error" in data, "Expected 'error' in 404 body"
        print(f"    -> PASS: status={status}, response={data}")
    except Exception as err:
        print(f"    -> FAIL: {err}")
        all_passed = False

    # --- 6. Error Handling: Bad JSON ---
    print("\n[6] Testing POST /status with invalid JSON (400 Bad Request)...")
    try:
        status, headers, body = make_request(
            base_url,
            "/status",
            method="POST",
            raw_body=b"{invalid-json-payload",
        )
        assert status == 400, f"Expected 400, got {status}"
        data = json.loads(body.decode("utf-8"))
        assert "error" in data, "Expected 'error' in 400 body"
        print(f"    -> PASS: status={status}, response={data}")
    except Exception as err:
        print(f"    -> FAIL: {err}")
        all_passed = False

    # --- 7. Error Handling: Non-dict JSON Root ---
    print("\n[7] Testing POST /status with non-dict array (400 Bad Request)...")
    try:
        status, headers, body = make_request(
            base_url,
            "/status",
            method="POST",
            data=[1, 2, 3],  # type: ignore[arg-type]
        )
        assert status == 400, f"Expected 400, got {status}"
        data = json.loads(body.decode("utf-8"))
        assert "error" in data, "Expected 'error' in 400 body"
        print(f"    -> PASS: status={status}, response={data}")
    except Exception as err:
        print(f"    -> FAIL: {err}")
        all_passed = False

    # --- 8. Error Handling: Oversized Payload ---
    print("\n[8] Testing POST /status with >64KB body (413 Payload Too Large)...")
    try:
        oversized_payload = b'{"data":"' + (b"A" * 70000) + b'"}'
        status, headers, body = make_request(
            base_url,
            "/status",
            method="POST",
            raw_body=oversized_payload,
        )
        assert status == 413, f"Expected 413, got {status}"
        data = json.loads(body.decode("utf-8"))
        assert "error" in data, "Expected 'error' in 413 body"
        print(f"    -> PASS: status={status}, response={data}")
    except Exception as err:
        print(f"    -> FAIL: {err}")
        all_passed = False

    # Final Summary
    print("\n" + "=" * 50)
    if all_passed:
        print("[SUCCESS] All GTFB Local API endpoints verified successfully!\n")
        return True
    else:
        print("[FAILURE] One or more GTFB Local API tests failed!\n")
        return False


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for running the API verification suite."""
    parser = argparse.ArgumentParser(
        description="Verify GTFB Local API endpoints against a running desktop instance."
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Explicit base URL (e.g. http://127.0.0.1:8765)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Target host (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Explicit port number (e.g. 8765)",
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        default=None,
        help="Path to directory containing api_port.json for port discovery",
    )

    args = parser.parse_args(argv)
    base_url = discover_base_url(
        host=args.host,
        port=args.port,
        base_url=args.base_url,
        config_dir=args.config_dir,
    )

    try:
        success = run_tests(base_url)
        return 0 if success else 1
    except urllib.error.URLError as e:
        print(f"\n[ERROR] Connection error: Could not reach GTFB API at {base_url}: {e}")
        print("Ensure the GTFB desktop application is running and API server is active.")
        return 1
    except KeyboardInterrupt:
        print("\n[!] Test interrupted by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
