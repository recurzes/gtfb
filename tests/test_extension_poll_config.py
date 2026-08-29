"""Tests for Extension Config Polling and Sync Client (feat/ext-poll-config)."""

import json
from pathlib import Path
import socket
import subprocess
import pytest

from gtfb.api import APIServer
from gtfb.config.models import AppCloseSchedule, BlockRule, ConfigProfile, OverridePolicy

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"
SRC_DIR = EXTENSION_DIR / "src"


def get_free_port() -> int:
    """Find and return an ephemeral open port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_sync_files_exist():
    """Verify sync.js, storage.js, background.js, popup.js, and manifest.json exist."""
    assert (SRC_DIR / "sync.js").is_file(), "sync.js must exist in extension/src/"
    assert (SRC_DIR / "storage.js").is_file(), "storage.js must exist in extension/src/"
    assert (SRC_DIR / "background.js").is_file(), "background.js must exist in extension/src/"
    assert (SRC_DIR / "popup.js").is_file(), "popup.js must exist in extension/src/"
    assert (EXTENSION_DIR / "manifest.json").is_file(), "manifest.json must exist in extension/"


def test_node_fetch_config_success_default_port():
    """Execute sync.js in Node.js to verify successful sync on default port 8765."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{}};

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
      }}
    }};

    const mockProfile = {{
      version: 1,
      profile_name: "DesktopSyncedProfile",
      app_close_schedule: {{ target_hour: 23, target_minute: 15, enabled: true }},
      block_rules: [
        {{ domains: ["facebook.com", "instagram.com"], start_hour: 23, start_minute: 15, end_hour: 7, end_minute: 0, active: true }}
      ]
    }};

    // Mock global fetch
    globalThis.fetch = async (url, options) => {{
      if (url === "http://127.0.0.1:8765/config") {{
        return {{
          ok: true,
          status: 200,
          json: async () => mockProfile
        }};
      }}
      throw new Error("Connection refused on " + url);
    }};

    const {{
      START_PORT,
      MAX_PORT,
      SYNC_ALARM_NAME,
      fetchConfigFromApp,
      getSyncStatus
    }} = await import('{sync_path.as_uri()}');

    if (START_PORT !== 8765 || MAX_PORT !== 8775) {{
      throw new Error(`Port constants mismatch: START_PORT=${{START_PORT}}, MAX_PORT=${{MAX_PORT}}`);
    }}
    if (SYNC_ALARM_NAME !== "gtfb-poll-sync") {{
      throw new Error(`Alarm name mismatch: ${{SYNC_ALARM_NAME}}`);
    }}

    const syncResult = await fetchConfigFromApp();
    if (!syncResult.success || syncResult.port !== 8765) {{
      throw new Error("fetchConfigFromApp failed to return success on 8765: " + JSON.stringify(syncResult));
    }}

    if (!storageState.cachedConfig || storageState.cachedConfig.profile_name !== "DesktopSyncedProfile") {{
      throw new Error("cachedConfig was not updated in storage: " + JSON.stringify(storageState.cachedConfig));
    }}

    if (storageState.isConnected !== true) {{
      throw new Error("isConnected was not set to true in storage");
    }}
    if (storageState.apiPort !== 8765) {{
      throw new Error("apiPort was not recorded as 8765");
    }}
    if (!storageState.lastSyncSuccess || typeof storageState.lastSyncSuccess !== "number") {{
      throw new Error("lastSyncSuccess timestamp was not recorded");
    }}

    const status = await getSyncStatus();
    if (!status.isConnected || status.apiPort !== 8765 || !status.lastSyncSuccess) {{
      throw new Error("getSyncStatus returned invalid status: " + JSON.stringify(status));
    }}

    console.log("FETCH_CONFIG_DEFAULT_PORT_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node sync tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "FETCH_CONFIG_DEFAULT_PORT_PASSED" in res.stdout


def test_node_fetch_config_port_fallback():
    """Verify poller scans fallback ports when primary port 8765 is unavailable."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{}};

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
      }}
    }};

    const fallbackProfile = {{
      version: 1,
      profile_name: "FallbackPortProfile",
      block_rules: [{{ domains: ["fallback.com"], active: true }}]
    }};

    const attemptedPorts = [];

    // Mock global fetch: 8765 and 8766 fail, 8767 succeeds
    globalThis.fetch = async (url, options) => {{
      const match = url.match(/:(\\d+)\\//);
      const port = match ? parseInt(match[1], 10) : 0;
      attemptedPorts.push(port);

      if (port === 8767) {{
        return {{
          ok: true,
          status: 200,
          json: async () => fallbackProfile
        }};
      }}
      throw new Error(`ECONNREFUSED on port ${{port}}`);
    }};

    const {{ fetchConfigFromApp }} = await import('{sync_path.as_uri()}');

    const syncResult = await fetchConfigFromApp();
    if (!syncResult.success || syncResult.port !== 8767) {{
      throw new Error(`Expected fallback success on 8767, got: ${{JSON.stringify(syncResult)}}`);
    }}

    if (storageState.isConnected !== true || storageState.apiPort !== 8767) {{
      throw new Error(`Storage state mismatch: isConnected=${{storageState.isConnected}}, apiPort=${{storageState.apiPort}}`);
    }}
    if (storageState.cachedConfig?.profile_name !== "FallbackPortProfile") {{
      throw new Error("cachedConfig profile_name mismatch: " + JSON.stringify(storageState.cachedConfig));
    }}

    if (!attemptedPorts.includes(8765) || !attemptedPorts.includes(8766) || !attemptedPorts.includes(8767)) {{
      throw new Error("Did not scan expected ports: " + JSON.stringify(attemptedPorts));
    }}

    console.log("FETCH_CONFIG_PORT_FALLBACK_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node fallback tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "FETCH_CONFIG_PORT_FALLBACK_PASSED" in res.stdout


def test_node_fetch_config_offline_graceful_handling():
    """Verify graceful handling and setting isConnected: false when desktop app is offline."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{
      isConnected: true,
      cachedConfig: {{ version: 1, profile_name: "PreviouslyCached" }}
    }};

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
      }}
    }};

    // All ports reject
    globalThis.fetch = async (url) => {{
      throw new Error("ECONNREFUSED connect 127.0.0.1");
    }};

    const {{ fetchConfigFromApp, getSyncStatus }} = await import('{sync_path.as_uri()}');

    const syncResult = await fetchConfigFromApp(8765, 8768, 100);
    if (syncResult.success !== false) {{
      throw new Error("Expected success: false for offline app, got: " + JSON.stringify(syncResult));
    }}

    if (storageState.isConnected !== false) {{
      throw new Error("isConnected must be false in storage when offline");
    }}
    // Previously cached config should remain intact
    if (storageState.cachedConfig?.profile_name !== "PreviouslyCached") {{
      throw new Error("Previous cachedConfig must not be wiped when offline");
    }}

    const status = await getSyncStatus();
    if (status.isConnected !== false) {{
      throw new Error("getSyncStatus returned isConnected: true when offline");
    }}

    console.log("FETCH_CONFIG_OFFLINE_GRACEFUL_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node offline tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "FETCH_CONFIG_OFFLINE_GRACEFUL_PASSED" in res.stdout


def test_node_fetch_config_timeout_abort():
    """Verify timeout aborts stalled connection attempts and moves forward."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{}};

    globalThis.chrome = {{
      storage: {{
        local: {{
          get: async () => storageState,
          set: async (items) => {{ Object.assign(storageState, items); }}
        }}
      }}
    }};

    // Port 8765 stalls until signal abort; port 8766 succeeds
    globalThis.fetch = (url, options) => {{
      return new Promise((resolve, reject) => {{
        if (url.includes(":8765/")) {{
          if (options && options.signal) {{
            options.signal.addEventListener("abort", () => {{
              const abortErr = new Error("The operation was aborted");
              abortErr.name = "AbortError";
              reject(abortErr);
            }});
          }}
          // Do not resolve or reject naturally, wait for signal
        }} else if (url.includes(":8766/")) {{
          resolve({{
            ok: true,
            status: 200,
            json: async () => ({{ version: 1, profile_name: "AfterTimeout" }})
          }});
        }} else {{
          reject(new Error("Refused"));
        }}
      }});
    }};

    const {{ fetchConfigFromApp }} = await import('{sync_path.as_uri()}');

    // Run with small timeout (100ms)
    const startTime = Date.now();
    const syncResult = await fetchConfigFromApp(8765, 8766, 100);
    const elapsed = Date.now() - startTime;

    if (!syncResult.success || syncResult.port !== 8766) {{
      throw new Error(`Expected timeout recovery on port 8766, got: ${{JSON.stringify(syncResult)}}`);
    }}
    if (elapsed > 2000) {{
      throw new Error(`Took too long (${{elapsed}}ms) to recover from timeout`);
    }}

    console.log("FETCH_CONFIG_TIMEOUT_ABORT_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node timeout tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "FETCH_CONFIG_TIMEOUT_ABORT_PASSED" in res.stdout


def test_node_background_alarms_and_startup():
    """Verify background.js registers alarms, handles gtfb-poll-sync alarm and onStartup/onInstalled."""
    bg_path = SRC_DIR / "background.js"

    js_test_script = f"""
    let storageState = {{}};
    let registeredAlarms = {{}};
    let alarmListeners = [];
    let messageListeners = [];
    let installListeners = [];
    let startupListeners = [];

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
        getDynamicRules: async () => [],
        updateDynamicRules: async () => {{}}
      }},
      alarms: {{
        create: (name, options) => {{
          registeredAlarms[name] = options;
        }},
        onAlarm: {{
          addListener: (fn) => alarmListeners.push(fn)
        }}
      }},
      runtime: {{
        onMessage: {{
          addListener: (fn) => messageListeners.push(fn)
        }},
        onInstalled: {{
          addListener: (fn) => installListeners.push(fn)
        }},
        onStartup: {{
          addListener: (fn) => startupListeners.push(fn)
        }}
      }}
    }};

    let syncFetchCalled = false;
    globalThis.fetch = async (url) => {{
      syncFetchCalled = true;
      return {{
        ok: true,
        status: 200,
        json: async () => ({{
          version: 1,
          profile_name: "BackgroundSyncProfile",
          block_rules: []
        }})
      }};
    }};

    const bg = await import('{bg_path.as_uri()}');

    // 1. Verify alarms registered
    if (!registeredAlarms["gtfb-schedule-check"] || !registeredAlarms["gtfb-poll-sync"]) {{
      throw new Error("Missing alarm registrations: " + JSON.stringify(registeredAlarms));
    }}
    if (registeredAlarms["gtfb-poll-sync"].periodInMinutes !== 1) {{
      throw new Error("gtfb-poll-sync periodInMinutes must be 1");
    }}

    // 2. Trigger alarm listener with gtfb-poll-sync
    syncFetchCalled = false;
    for (const listener of alarmListeners) {{
      await listener({{ name: "gtfb-poll-sync" }});
    }}
    if (!syncFetchCalled || storageState.cachedConfig?.profile_name !== "BackgroundSyncProfile") {{
      throw new Error("gtfb-poll-sync alarm did not trigger fetchConfigFromApp");
    }}

    // 3. Test runtime message handling for SYNC_CONFIG
    let msgResponse = null;
    const msgHandler = messageListeners[0];
    const responded = msgHandler({{ action: "SYNC_CONFIG" }}, {{}}, (res) => {{ msgResponse = res; }});
    if (!responded) {{
      throw new Error("SYNC_CONFIG message handler must return true for async response");
    }}
    await new Promise(r => setTimeout(r, 50));
    if (!msgResponse || !msgResponse.success || msgResponse.config?.profile_name !== "BackgroundSyncProfile") {{
      throw new Error("SYNC_CONFIG message handler response mismatch: " + JSON.stringify(msgResponse));
    }}

    // 4. Test runtime message handling for GET_SYNC_STATUS
    let statusResponse = null;
    msgHandler({{ action: "GET_SYNC_STATUS" }}, {{}}, (res) => {{ statusResponse = res; }});
    await new Promise(r => setTimeout(r, 50));
    if (!statusResponse || statusResponse.isConnected !== true) {{
      throw new Error("GET_SYNC_STATUS message response mismatch: " + JSON.stringify(statusResponse));
    }}

    // 5. Test onInstalled listener
    storageState.cachedConfig = null;
    for (const listener of installListeners) {{
      await listener({{ reason: "install" }});
    }}
    if (!storageState.cachedConfig) {{
      throw new Error("onInstalled failed to trigger initial sync");
    }}

    // 6. Test onStartup listener
    storageState.cachedConfig = null;
    for (const listener of startupListeners) {{
      await listener();
    }}
    if (!storageState.cachedConfig) {{
      throw new Error("onStartup failed to trigger initial sync");
    }}

    console.log("BACKGROUND_ALARMS_AND_STARTUP_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node background tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "BACKGROUND_ALARMS_AND_STARTUP_PASSED" in res.stdout


def test_node_popup_sync_status_ui():
    """Verify popup.js updates syncStatus element when connected vs standalone."""
    popup_path = SRC_DIR / "popup.js"

    js_test_script = f"""
    let storageState = {{
      isConnected: true,
      apiPort: 8765,
      lastSyncSuccess: Date.now(),
      cachedConfig: {{
        version: 1,
        profile_name: "Default",
        block_rules: [{{ domains: ["test.com"], active: true }}]
      }}
    }};

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
        }},
        onChanged: {{
          addListener: () => {{}}
        }}
      }}
    }};

    let syncStatusElem = {{
      className: "",
      textContent: "",
      title: ""
    }};

    globalThis.document = {{
      getElementById: (id) => {{
        if (id === "syncStatus") return syncStatusElem;
        return null;
      }}
    }};

    const {{ refreshSyncStatus }} = await import('{popup_path.as_uri()}');

    // 1. Connected state
    await refreshSyncStatus();
    if (syncStatusElem.className !== "status-indicator connected" || syncStatusElem.textContent !== "Synced") {{
      throw new Error(`Expected Synced state, got: class='${{syncStatusElem.className}}', text='${{syncStatusElem.textContent}}'`);
    }}

    // 2. Disconnected / Standalone state
    storageState.isConnected = false;
    await refreshSyncStatus();
    if (syncStatusElem.className !== "status-indicator standalone" || syncStatusElem.textContent !== "Standalone") {{
      throw new Error(`Expected Standalone state, got: class='${{syncStatusElem.className}}', text='${{syncStatusElem.textContent}}'`);
    }}

    console.log("POPUP_SYNC_STATUS_UI_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node popup UI tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "POPUP_SYNC_STATUS_UI_PASSED" in res.stdout


def test_live_api_server_extension_sync_integration():
    """Start real APIServer and run Node sync client against live HTTP endpoint."""
    port = get_free_port()
    live_profile = ConfigProfile(
        profile_name="LivePyAPISyncTest",
        app_close_schedule=AppCloseSchedule(
            target_hour=23,
            target_minute=45,
            enabled=True,
        ),
        block_rules=[
            BlockRule(
                domains=["live-site-1.com", "live-site-2.org"],
                start_hour=23,
                start_minute=45,
                end_hour=6,
                end_minute=30,
                active=True,
            )
        ],
        override_policy=OverridePolicy(
            friction_type="math",
            cooldown_minutes=20,
        ),
    )

    server = APIServer(
        host="127.0.0.1",
        port=port,
        config_provider=lambda: live_profile,
    )
    server.start()

    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{}};

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
      }}
    }};

    const {{ fetchConfigFromApp, getSyncStatus }} = await import('{sync_path.as_uri()}');

    // Run against the live Python APIServer on port {port}
    const result = await fetchConfigFromApp({port}, {port});
    if (!result.success || result.port !== {port}) {{
      throw new Error(`Failed to sync from live server on port {port}: ${{JSON.stringify(result)}}`);
    }}

    const cached = storageState.cachedConfig;
    if (!cached || cached.profile_name !== "LivePyAPISyncTest") {{
      throw new Error("Synced profile name mismatch: " + JSON.stringify(cached));
    }}
    if (!cached.block_rules || cached.block_rules.length !== 1) {{
      throw new Error("Synced block_rules mismatch: " + JSON.stringify(cached.block_rules));
    }}
    if (!cached.block_rules[0].domains.includes("live-site-1.com")) {{
      throw new Error("Synced domains missing live-site-1.com: " + JSON.stringify(cached.block_rules[0].domains));
    }}

    const status = await getSyncStatus();
    if (!status.isConnected || status.apiPort !== {port}) {{
      throw new Error("Sync status mismatch after live fetch: " + JSON.stringify(status));
    }}

    console.log("LIVE_FASTAPI_EXTENSION_SYNC_INTEGRATION_PASSED");
    """

    try:
        res = subprocess.run(
            ["node", "--input-type=module", "-e", js_test_script],
            capture_output=True,
            text=True,
            check=False
        )

        assert res.returncode == 0, f"Live sync integration failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        assert "LIVE_FASTAPI_EXTENSION_SYNC_INTEGRATION_PASSED" in res.stdout
    finally:
        server.stop()
