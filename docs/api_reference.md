# GTFB Local Desktop API Reference & Verification Guide

This document describes the GTFB desktop application's embedded localhost HTTP API and provides instructions and copy-paste snippets for manual and automated verification.

---

## 1. Overview & Architecture

The GTFB Local API acts as a high-performance, secure bridge between the GTFB desktop process and companion browser extensions (Chrome, Firefox, Edge, Brave, Safari).

### Key Architectural Characteristics
- **Strict Loopback Binding:** Only listens on loopback interfaces (`127.0.0.1` / `localhost`). External network requests are strictly rejected.
- **Port Allocation & Fallback:** Binds by default to port `8765`. If occupied, sequentially tries ports up to `8775`.
- **Discovery Mechanism:** Writes active connection info to `api_port.json` on startup and cleans it up on graceful shutdown.
- **CORS Support:** Returns permissive Cross-Origin Resource Sharing headers (`Access-Control-Allow-Origin: *`) allowing browser extension background service workers and content scripts to query the local API without restriction.
- **Lightweight & Threaded:** Runs in a background daemon thread with zero impact on UI responsiveness.

---

## 2. Port Discovery Mechanism

When GTFB launches, it creates `api_port.json` in the platform-standard user configuration directory:

| Operating System | Path |
| :--- | :--- |
| **Windows** | `%APPDATA%\GTFB\api_port.json` *(e.g. `C:\Users\<user>\AppData\Roaming\GTFB\api_port.json`)* |
| **macOS** | `~/Library/Application Support/GTFB/api_port.json` |
| **Linux / BSD** | `$XDG_CONFIG_HOME/gtfb/api_port.json` or `~/.config/gtfb/api_port.json` |

### `api_port.json` Schema

```json
{
  "port": 8765,
  "host": "127.0.0.1",
  "pid": 12345,
  "updated_at": "2026-08-29T02:08:39.123456+00:00"
}
```

Extensions and external scripts read this file to detect the active port. If missing, clients should fallback to `http://127.0.0.1:8765`.

---

## 3. Endpoints Specification

### 3.1. Health Check (`GET /health`)

Returns the operational status and version metadata of the GTFB desktop daemon.

- **Method:** `GET`
- **Path:** `/health`
- **Response Code:** `200 OK`
- **Content-Type:** `application/json`
- **Response Body Example:**
  ```json
  {
    "status": "ok",
    "app": "gtfb",
    "version": "1.0.0",
    "timestamp": "2026-08-29T02:08:39.123456+00:00"
  }
  ```

---

### 3.2. Fetch Configuration (`GET /config`)

Provides the active blocking rules and application close schedules to browser extensions.

- **Method:** `GET`
- **Path:** `/config`
- **Response Code:** `200 OK`
- **Content-Type:** `application/json`
- **Response Body Example:**
  ```json
  {
    "app_close_schedule": {
      "enabled": true,
      "close_time": "23:00",
      "warning_minutes": 5,
      "blocked_apps": ["discord.exe", "steam.exe"]
    },
    "block_rules": [
      {
        "name": "Social Media Block",
        "domains": ["x.com", "twitter.com", "instagram.com", "reddit.com"],
        "schedule": {
          "enabled": true,
          "start_time": "22:00",
          "end_time": "06:00",
          "days": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        }
      }
    ]
  }
  ```

---

### 3.3. Report Extension Status (`POST /status`)

Allows browser extensions to post periodic heartbeat and telemetry status back to the desktop application.

- **Method:** `POST`
- **Path:** `/status`
- **Headers:** `Content-Type: application/json`
- **Request Body Example:**
  ```json
  {
    "browser": "chrome",
    "version": "1.0.0",
    "blocking_active": true,
    "rules_count": 5
  }
  ```
- **Response Code:** `200 OK`
- **Content-Type:** `application/json`
- **Response Body:**
  ```json
  {
    "status": "received"
  }
  ```

#### Error Codes for `POST /status`:
- `400 Bad Request`: Missing or invalid `Content-Length`, malformed JSON body, or JSON root not an object.
- `413 Payload Too Large`: Request body exceeds maximum allowed size of 64KB (65,536 bytes).
- `500 Internal Server Error`: Unhandled server exception during state persistence.

---

### 3.4. CORS Preflight (`OPTIONS <path>`)

Handles browser preflight requests.

- **Method:** `OPTIONS`
- **Path:** `/health`, `/config`, `/status`, or any route
- **Response Code:** `204 No Content`
- **Headers Returned:**
  - `Access-Control-Allow-Origin: *`
  - `Access-Control-Allow-Methods: GET, POST, OPTIONS`
  - `Access-Control-Allow-Headers: Content-Type, Authorization`

---

### 3.5. 404 Route Not Found (`*`)

Any unrecognized path returns a 404 JSON object.

- **Response Code:** `404 Not Found`
- **Response Body Example:**
  ```json
  {
    "error": "Not Found",
    "path": "/unknown-route"
  }
  ```

---

## 4. Manual Verification Snippets

### Using `curl` (Linux / macOS / Git Bash / Windows Terminal)

```bash
# 1. Health Check
curl -i http://127.0.0.1:8765/health

# 2. Fetch Active Config
curl -i http://127.0.0.1:8765/config

# 3. Post Extension Status Telemetry
curl -i -X POST http://127.0.0.1:8765/status \
  -H "Content-Type: application/json" \
  -d '{"browser":"chrome","version":"1.0.0","blocking_active":true,"rules_count":5}'

# 4. CORS Preflight Check
curl -i -X OPTIONS http://127.0.0.1:8765/health

# 5. Verify 404 Route Handling
curl -i http://127.0.0.1:8765/nonexistent

# 6. Verify 400 Bad JSON Handling
curl -i -X POST http://127.0.0.1:8765/status \
  -H "Content-Type: application/json" \
  -d '{"bad_json: true'
```

---

### Using PowerShell (Windows)

```powershell
# 1. Health Check
Invoke-RestMethod -Uri "http://127.0.0.1:8765/health" -Method Get | ConvertTo-Json

# 2. Fetch Active Config
Invoke-RestMethod -Uri "http://127.0.0.1:8765/config" -Method Get | ConvertTo-Json -Depth 5

# 3. Post Extension Status Telemetry
$body = @{
    browser = "chrome"
    version = "1.0.0"
    blocking_active = $true
    rules_count = 5
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8765/status" -Method Post -Body $body -ContentType "application/json" | ConvertTo-Json

# 4. Check CORS Preflight Headers
$response = Invoke-WebRequest -Uri "http://127.0.0.1:8765/health" -Method Options
$response.Headers["Access-Control-Allow-Origin"]
$response.Headers["Access-Control-Allow-Methods"]
```

---

## 5. Automated Verification Script (`scripts/test_api.py`)

A zero-dependency test runner is included in `scripts/test_api.py`. It verifies all 8 core API capabilities and assertions automatically.

### Running the Script

```bash
# Auto-detect active port from api_port.json or fallback to 8765
python scripts/test_api.py

# Specify an explicit port
python scripts/test_api.py --port 8766

# Specify a custom base URL
python scripts/test_api.py --base-url http://127.0.0.1:8765

# Specify a custom config directory for port discovery
python scripts/test_api.py --config-dir /path/to/config
```

### Expected Output
```text
[*] Testing GTFB Local API at http://127.0.0.1:8765...

[1] Testing GET /health...
    -> PASS: status=200, app=gtfb, version=1.0.0

[2] Testing GET /config...
    -> PASS: status=200, rules_count=1, has_schedule=True

[3] Testing POST /status (valid telemetry)...
    -> PASS: status=200, response={'status': 'received'}

[4] Testing OPTIONS /health (CORS Preflight)...
    -> PASS: status=204, Origin=*, Methods=GET, POST, OPTIONS

[5] Testing GET /nonexistent (404 Not Found)...
    -> PASS: status=404, response={'error': 'Not Found', 'path': '/nonexistent'}

[6] Testing POST /status with invalid JSON (400 Bad Request)...
    -> PASS: status=400, response={'error': 'Invalid JSON'}

[7] Testing POST /status with non-dict array (400 Bad Request)...
    -> PASS: status=400, response={'error': 'Invalid JSON payload: root must be an object'}

[8] Testing POST /status with >64KB body (413 Payload Too Large)...
    -> PASS: status=413, response={'error': 'Payload too large'}

==================================================
[SUCCESS] All GTFB Local API endpoints verified successfully!
```
