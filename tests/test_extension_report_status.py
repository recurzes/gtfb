"""Tests for Extension Outbound Status Reporting (feat/ext-report-status)."""

import json
from pathlib import Path
import socket
import subprocess
import pytest

from gtfb.api import APIServer, ExtensionStatusStore
from gtfb.config.models import AppCloseSchedule, BlockRule, ConfigProfile, OverridePolicy

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"
SRC_DIR = EXTENSION_DIR / "src"


def get_free_port() -> int:
    """Find and return an ephemeral open port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_status_reporting_files_and_exports_exist():
    """Verify sync.js and background.js export reportStatusToApp."""
    sync_path = SRC_DIR / "sync.js"
    bg_path = SRC_DIR / "background.js"
    assert sync_path.is_file(), "sync.js must exist in extension/src/"
    assert bg_path.is_file(), "background.js must exist in extension/src/"

    js_check_script = f"""
    const sync = await import('{sync_path.as_uri()}');
    const bg = await import('{bg_path.as_uri()}');

    if (typeof sync.reportStatusToApp !== 'function') {{
      throw new Error('sync.js must export reportStatusToApp function');
    }}
    if (typeof bg.reportStatusToApp !== 'function') {{
      throw new Error('background.js must export reportStatusToApp function');
    }}
    console.log("EXPORTS_CHECK_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_check_script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "EXPORTS_CHECK_PASSED" in res.stdout


def test_node_report_status_payload_schema_and_headers():
    """Verify reportStatusToApp builds correct payload schema and sends POST with JSON headers."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let capturedRequest = null;
    let storageState = {{
      isBlockingActive: true,
      apiPort: 8765
    }};
    let dynamicRules = [
      {{ id: 1, action: {{ type: "redirect" }}, condition: {{ urlFilter: "||reddit.com" }} }},
      {{ id: 2, action: {{ type: "redirect" }}, condition: {{ urlFilter: "||twitter.com" }} }},
      {{ id: 3, action: {{ type: "redirect" }}, condition: {{ urlFilter: "||youtube.com" }} }}
    ];

    globalThis.chrome = {{
      storage: {{
        local: {{
          get: async (keys) => {{
            const result = {{}};
            if (Array.isArray(keys)) {{
              keys.forEach(k => {{ result[k] = storageState[k]; }});
            }} else if (typeof keys === 'string') {{
              result[keys] = storageState[keys];
            }} else if (keys === null || keys === undefined) {{
              Object.assign(result, storageState);
            }}
            return result;
          }},
          set: async (items) => {{
            Object.assign(storageState, items);
          }}
        }}
      }},
      declarativeNetRequest: {{
        getDynamicRules: async () => dynamicRules
      }},
      runtime: {{
        getManifest: () => ({{ version: "1.2.3" }})
      }}
    }};

    if (typeof globalThis.navigator === "undefined") {{
      globalThis.navigator = {{}};
    }}
    Object.defineProperty(globalThis.navigator, "userAgent", {{
      value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      configurable: true,
      writable: true
    }});

    globalThis.fetch = async (url, options) => {{
      capturedRequest = {{
        url,
        method: options.method,
        headers: options.headers,
        body: JSON.parse(options.body),
        signal: options.signal
      }};
      return {{
        ok: true,
        status: 200,
        json: async () => ({{ status: "received" }})
      }};
    }};

    const {{ reportStatusToApp }} = await import('{sync_path.as_uri()}');

    const result = await reportStatusToApp(8765);
    if (!result.success) {{
      throw new Error(`reportStatusToApp failed: ${{JSON.stringify(result)}}`);
    }}

    if (!capturedRequest) {{
      throw new Error("fetch was not called by reportStatusToApp");
    }}
    if (capturedRequest.url !== "http://127.0.0.1:8765/status") {{
      throw new Error(`Unexpected request URL: ${{capturedRequest.url}}`);
    }}
    if (capturedRequest.method !== "POST") {{
      throw new Error(`Expected POST method, got: ${{capturedRequest.method}}`);
    }}
    if (capturedRequest.headers["Content-Type"] !== "application/json") {{
      throw new Error(`Expected application/json header, got: ${{JSON.stringify(capturedRequest.headers)}}`);
    }}

    const payload = capturedRequest.body;
    if (payload.browser !== "chrome") {{
      throw new Error(`Expected browser 'chrome', got: ${{payload.browser}}`);
    }}
    if (payload.version !== "1.2.3") {{
      throw new Error(`Expected version '1.2.3', got: ${{payload.version}}`);
    }}
    if (payload.blocking_active !== true) {{
      throw new Error(`Expected blocking_active true, got: ${{payload.blocking_active}}`);
    }}
    if (payload.rules_count !== 3) {{
      throw new Error(`Expected rules_count 3, got: ${{payload.rules_count}}`);
    }}
    if (!payload.timestamp || isNaN(Date.parse(payload.timestamp))) {{
      throw new Error(`Invalid ISO timestamp: ${{payload.timestamp}}`);
    }}

    console.log("PAYLOAD_SCHEMA_TEST_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "PAYLOAD_SCHEMA_TEST_PASSED" in res.stdout


def test_node_browser_vendor_detection():
    """Verify Edge, Firefox, and Chrome browser detection from navigator.userAgent."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let capturedPayload = null;

    globalThis.chrome = {{
      storage: {{
        local: {{
          get: async () => ({{ isBlockingActive: false, apiPort: 8765 }})
        }}
      }},
      declarativeNetRequest: {{
        getDynamicRules: async () => []
      }},
      runtime: {{
        getManifest: () => ({{ version: "1.0.0" }})
      }}
    }};

    if (typeof globalThis.navigator === "undefined") {{
      globalThis.navigator = {{}};
    }}

    globalThis.fetch = async (url, options) => {{
      capturedPayload = JSON.parse(options.body);
      return {{ ok: true, status: 200, json: async () => ({{ status: "received" }}) }};
    }};

    const {{ reportStatusToApp }} = await import('{sync_path.as_uri()}');

    // 1. Edge detection
    Object.defineProperty(globalThis.navigator, "userAgent", {{
      value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.2210.91",
      configurable: true,
      writable: true
    }});
    await reportStatusToApp(8765);
    if (capturedPayload.browser !== "edge") {{
      throw new Error(`Expected 'edge', got: ${{capturedPayload.browser}}`);
    }}

    // 2. Firefox detection
    Object.defineProperty(globalThis.navigator, "userAgent", {{
      value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
      configurable: true,
      writable: true
    }});
    await reportStatusToApp(8765);
    if (capturedPayload.browser !== "firefox") {{
      throw new Error(`Expected 'firefox', got: ${{capturedPayload.browser}}`);
    }}

    // 3. Chrome detection
    Object.defineProperty(globalThis.navigator, "userAgent", {{
      value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      configurable: true,
      writable: true
    }});
    await reportStatusToApp(8765);
    if (capturedPayload.browser !== "chrome") {{
      throw new Error(`Expected 'chrome', got: ${{capturedPayload.browser}}`);
    }}

    console.log("VENDOR_DETECTION_TEST_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "VENDOR_DETECTION_TEST_PASSED" in res.stdout


def test_node_offline_graceful_handling():
    """Verify reportStatusToApp handles fetch errors / closed desktop app gracefully without throwing."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    globalThis.chrome = {{
      storage: {{
        local: {{
          get: async () => ({{ isBlockingActive: true, apiPort: 8765 }})
        }}
      }},
      declarativeNetRequest: {{
        getDynamicRules: async () => []
      }},
      runtime: {{
        getManifest: () => ({{ version: "1.0.0" }})
      }}
    }};

    globalThis.fetch = async () => {{
      throw new Error("TypeError: fetch failed (ECONNREFUSED 127.0.0.1:8765)");
    }};

    const {{ reportStatusToApp }} = await import('{sync_path.as_uri()}');

    // Should NOT throw
    const res = await reportStatusToApp(8765);
    if (res.success !== false) {{
      throw new Error("Expected success: false when desktop app is unreachable");
    }}

    console.log("OFFLINE_GRACEFUL_HANDLING_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "OFFLINE_GRACEFUL_HANDLING_PASSED" in res.stdout


def test_node_handle_toggle_triggers_report_status():
    """Verify handleToggle triggers status reporting for both enable and disable actions."""
    bg_path = SRC_DIR / "background.js"

    js_test_script = f"""
    let reportedStatuses = [];
    let storageState = {{
      isBlockingActive: false,
      apiPort: 8765
    }};
    let dynamicRules = [];
    let badgeState = {{ text: "", color: "" }};

    globalThis.chrome = {{
      storage: {{
        local: {{
          get: async (keys) => {{
            const result = {{}};
            if (Array.isArray(keys)) {{
              keys.forEach(k => {{ result[k] = storageState[k]; }});
            }} else if (typeof keys === 'string') {{
              result[keys] = storageState[keys];
            }} else if (keys === null || keys === undefined) {{
              Object.assign(result, storageState);
            }}
            return result;
          }},
          set: async (items) => {{
            Object.assign(storageState, items);
          }}
        }}
      }},
      action: {{
        setBadgeText: async (details) => {{ badgeState.text = details.text; }},
        setBadgeBackgroundColor: async (details) => {{ badgeState.color = details.color; }}
      }},
      declarativeNetRequest: {{
        getDynamicRules: async () => dynamicRules,
        updateDynamicRules: async (args) => {{
          dynamicRules = dynamicRules.filter(r => !args.removeRuleIds.includes(r.id));
          if (args.addRules && args.addRules.length > 0) {{
            dynamicRules.push(...args.addRules);
          }}
        }}
      }},
      alarms: {{
        create: () => {{}},
        onAlarm: {{ addListener: () => {{}} }}
      }},
      runtime: {{
        onMessage: {{ addListener: () => {{}} }},
        onInstalled: {{ addListener: () => {{}} }},
        onStartup: {{ addListener: () => {{}} }},
        getManifest: () => ({{ version: "1.0.0" }})
      }}
    }};

    globalThis.fetch = async (url, options) => {{
      if (url.includes("/status")) {{
        reportedStatuses.push(JSON.parse(options.body));
        return {{ ok: true, status: 200, json: async () => ({{ status: "received" }}) }};
      }}
      return {{ ok: false, status: 404 }};
    }};

    const {{ handleToggle }} = await import('{bg_path.as_uri()}');

    // 1. Enable blocking
    await handleToggle(true);
    if (reportedStatuses.length !== 1) {{
      throw new Error(`Expected 1 status report after enable, got ${{reportedStatuses.length}}`);
    }}
    if (reportedStatuses[0].blocking_active !== true) {{
      throw new Error(`Expected blocking_active: true after enable, got: ${{reportedStatuses[0].blocking_active}}`);
    }}

    // 2. Disable blocking
    await handleToggle(false);
    if (reportedStatuses.length !== 2) {{
      throw new Error(`Expected 2 status reports after disable, got ${{reportedStatuses.length}}`);
    }}
    if (reportedStatuses[1].blocking_active !== false) {{
      throw new Error(`Expected blocking_active: false after disable, got: ${{reportedStatuses[1].blocking_active}}`);
    }}

    console.log("TOGGLE_STATUS_TRIGGER_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "TOGGLE_STATUS_TRIGGER_PASSED" in res.stdout


def test_node_sync_poll_triggers_report_status():
    """Verify fetchConfigFromApp triggers reportStatusToApp upon receiving new configuration."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let statusReports = [];
    let storageState = {{
      isBlockingActive: false,
      cachedConfig: null
    }};
    let dynamicRules = [];

    globalThis.chrome = {{
      storage: {{
        local: {{
          get: async (keys) => {{
            const result = {{}};
            if (Array.isArray(keys)) {{
              keys.forEach(k => {{ result[k] = storageState[k]; }});
            }} else if (typeof keys === 'string') {{
              result[keys] = storageState[keys];
            }} else if (keys === null || keys === undefined) {{
              Object.assign(result, storageState);
            }}
            return result;
          }},
          set: async (items) => {{
            Object.assign(storageState, items);
          }}
        }}
      }},
      action: {{
        setBadgeText: async () => {{}},
        setBadgeBackgroundColor: async () => {{}}
      }},
      declarativeNetRequest: {{
        getDynamicRules: async () => dynamicRules,
        updateDynamicRules: async (args) => {{
          dynamicRules = dynamicRules.filter(r => !args.removeRuleIds.includes(r.id));
          if (args.addRules && args.addRules.length > 0) {{
            dynamicRules.push(...args.addRules);
          }}
        }}
      }},
      alarms: {{
        create: () => {{}},
        onAlarm: {{ addListener: () => {{}} }}
      }},
      runtime: {{
        onMessage: {{ addListener: () => {{}} }},
        onInstalled: {{ addListener: () => {{}} }},
        onStartup: {{ addListener: () => {{}} }},
        getManifest: () => ({{ version: "1.0.0" }})
      }}
    }};

    const mockProfile = {{
      version: 1,
      profile_name: "StatusSyncProfile",
      block_rules: [
        {{
          domains: ["site1.com", "site2.com"],
          start_hour: 0,
          start_minute: 0,
          end_hour: 23,
          end_minute: 59,
          active: true
        }}
      ]
    }};

    globalThis.fetch = async (url, options) => {{
      if (url.includes("/config")) {{
        return {{
          ok: true,
          status: 200,
          json: async () => mockProfile
        }};
      }}
      if (url.includes("/status")) {{
        statusReports.push({{
          url,
          body: JSON.parse(options.body)
        }});
        return {{
          ok: true,
          status: 200,
          json: async () => ({{ status: "received" }})
        }};
      }}
      return {{ ok: false, status: 404 }};
    }};

    const {{ fetchConfigFromApp }} = await import('{sync_path.as_uri()}');

    const res = await fetchConfigFromApp(8765, 8765);
    if (!res.success) {{
      throw new Error("fetchConfigFromApp failed");
    }}

    if (statusReports.length === 0) {{
      throw new Error("Expected status report during sync, got 0");
    }}

    const lastReport = statusReports[statusReports.length - 1].body;
    if (lastReport.rules_count !== 2) {{
      throw new Error(`Expected 2 active dynamic rules reported, got ${{lastReport.rules_count}}`);
    }}
    if (lastReport.blocking_active !== true) {{
      throw new Error(`Expected blocking_active: true, got ${{lastReport.blocking_active}}`);
    }}

    console.log("SYNC_POLL_STATUS_TRIGGER_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"Node script failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "SYNC_POLL_STATUS_TRIGGER_PASSED" in res.stdout


def test_live_api_server_status_reporting_integration():
    """Live end-to-end integration test with real APIServer receiving POST /status from extension."""
    port = get_free_port()
    status_store = ExtensionStatusStore()
    server = APIServer(
        host="127.0.0.1",
        port=port,
        status_store=status_store,
    )
    server.start()

    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let dynamicRules = [
      {{ id: 1, action: {{ type: "redirect" }}, condition: {{ urlFilter: "||news.ycombinator.com" }} }},
      {{ id: 2, action: {{ type: "redirect" }}, condition: {{ urlFilter: "||reddit.com" }} }}
    ];

    globalThis.chrome = {{
      storage: {{
        local: {{
          get: async (keys) => ({{ isBlockingActive: true, apiPort: {port} }})
        }}
      }},
      declarativeNetRequest: {{
        getDynamicRules: async () => dynamicRules
      }},
      runtime: {{
        getManifest: () => ({{ version: "1.0.0" }})
      }}
    }};

    if (typeof globalThis.navigator === "undefined") {{
      globalThis.navigator = {{}};
    }}
    Object.defineProperty(globalThis.navigator, "userAgent", {{
      value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      configurable: true,
      writable: true
    }});

    const {{ reportStatusToApp }} = await import('{sync_path.as_uri()}');

    const res = await reportStatusToApp({port});
    if (!res.success) {{
      throw new Error(`Live reportStatusToApp failed: ${{JSON.stringify(res)}}`);
    }}

    console.log("LIVE_STATUS_REPORT_PASSED");
    """

    try:
        assert status_store.get_status() is None
        assert not status_store.is_connected()

        res = subprocess.run(
            ["node", "--input-type=module", "-e", js_test_script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"Live Node test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        assert "LIVE_STATUS_REPORT_PASSED" in res.stdout

        # Verify APIServer ExtensionStatusStore received the payload
        status = status_store.get_status()
        assert status is not None
        assert status["browser"] == "chrome"
        assert status["version"] == "1.0.0"
        assert status["blocking_active"] is True
        assert status["rules_count"] == 2
        assert "_received_at" in status
        assert status_store.is_connected(timeout_seconds=60)
    finally:
        server.stop()


def test_live_api_server_toggle_and_sync_integration():
    """Live end-to-end integration test verifying status updates in ExtensionStatusStore across sync & manual toggles."""
    port = get_free_port()
    status_store = ExtensionStatusStore()

    profile = ConfigProfile(
        profile_name="LiveToggleSyncProfile",
        app_close_schedule=AppCloseSchedule(target_hour=22, target_minute=0, enabled=True),
        block_rules=[
            BlockRule(
                domains=["live1.com", "live2.com", "live3.com"],
                start_hour=0,
                start_minute=0,
                end_hour=23,
                end_minute=59,
                active=True,
            )
        ],
    )

    server = APIServer(
        host="127.0.0.1",
        port=port,
        config_provider=lambda: profile,
        status_store=status_store,
    )
    server.start()

    bg_path = SRC_DIR / "background.js"

    js_test_script = f"""
    let storageState = {{
      isBlockingActive: false,
      apiPort: {port},
      cachedConfig: null
    }};
    let dynamicRules = [];
    let badgeState = {{ text: "", color: "" }};

    globalThis.chrome = {{
      storage: {{
        local: {{
          get: async (keys) => {{
            const result = {{}};
            if (Array.isArray(keys)) {{
              keys.forEach(k => {{ result[k] = storageState[k]; }});
            }} else if (typeof keys === 'string') {{
              result[keys] = storageState[keys];
            }} else if (keys === null || keys === undefined) {{
              Object.assign(result, storageState);
            }}
            return result;
          }},
          set: async (items) => {{
            Object.assign(storageState, items);
          }}
        }}
      }},
      action: {{
        setBadgeText: async (details) => {{ badgeState.text = details.text; }},
        setBadgeBackgroundColor: async (details) => {{ badgeState.color = details.color; }}
      }},
      declarativeNetRequest: {{
        getDynamicRules: async () => dynamicRules,
        updateDynamicRules: async (args) => {{
          dynamicRules = dynamicRules.filter(r => !args.removeRuleIds.includes(r.id));
          if (args.addRules && args.addRules.length > 0) {{
            dynamicRules.push(...args.addRules);
          }}
        }}
      }},
      alarms: {{
        create: () => {{}},
        onAlarm: {{ addListener: () => {{}} }}
      }},
      runtime: {{
        onMessage: {{ addListener: () => {{}} }},
        onInstalled: {{ addListener: () => {{}} }},
        onStartup: {{ addListener: () => {{}} }},
        getManifest: () => ({{ version: "1.0.0" }})
      }}
    }};

    if (typeof globalThis.navigator === "undefined") {{
      globalThis.navigator = {{}};
    }}
    Object.defineProperty(globalThis.navigator, "userAgent", {{
      value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
      configurable: true,
      writable: true
    }});

    const {{ fetchConfigFromApp, handleToggle }} = await import('{bg_path.as_uri()}');

    // 1. Initial sync poll: compiles 3 rules and reports status
    const syncRes = await fetchConfigFromApp({port}, {port});
    if (!syncRes.success) throw new Error("Sync failed");

    // 2. Manual toggle OFF: clears rules and reports status
    const toggleOff = await handleToggle(false);
    if (!toggleOff.success) throw new Error("Toggle off failed");

    console.log("LIVE_TOGGLE_SYNC_PASSED");
    """

    try:
        res = subprocess.run(
            ["node", "--input-type=module", "-e", js_test_script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 0, f"Live Node test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        assert "LIVE_TOGGLE_SYNC_PASSED" in res.stdout

        # Verify final state in status_store reflects toggle off
        final_status = status_store.get_status()
        assert final_status is not None
        assert final_status["browser"] == "edge"
        assert final_status["blocking_active"] is False
        assert final_status["rules_count"] == 0
    finally:
        server.stop()
