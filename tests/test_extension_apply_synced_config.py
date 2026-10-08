"""Tests for Dynamic Rule Compilation & Real-Time Schedule Application (feat/ext-apply-synced-config)."""

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


def test_rules_and_sync_files_exist():
    """Verify rules.js, sync.js, background.js, and storage.js exist."""
    assert (SRC_DIR / "rules.js").is_file(), "rules.js must exist in extension/src/"
    assert (SRC_DIR / "sync.js").is_file(), "sync.js must exist in extension/src/"
    assert (SRC_DIR / "background.js").is_file(), "background.js must exist in extension/src/"
    assert (SRC_DIR / "storage.js").is_file(), "storage.js must exist in extension/src/"


def test_node_sync_and_apply_rules_unit():
    """Execute syncAndApplyRules in Node.js to verify rule compilation and dynamic rule application."""
    rules_path = SRC_DIR / "rules.js"

    js_test_script = f"""
    let dynamicRules = [
      {{ id: 999, priority: 1, action: {{ type: "block" }}, condition: {{ urlFilter: "old.com" }} }}
    ];
    let lastUpdateArgs = null;

    globalThis.chrome = {{
      declarativeNetRequest: {{
        getDynamicRules: async () => dynamicRules,
        updateDynamicRules: async (args) => {{
          lastUpdateArgs = args;
          dynamicRules = dynamicRules.filter(r => !args.removeRuleIds.includes(r.id));
          if (args.addRules && args.addRules.length > 0) {{
            dynamicRules.push(...args.addRules);
          }}
        }}
      }}
    }};

    const {{
      syncAndApplyRules,
      compileBlockRules,
      sanitizeDomain
    }} = await import('{rules_path.as_uri()}');

    // 1. Test compileBlockRules includes domain query param
    const compiled = compileBlockRules(["reddit.com", "HTTPS://YOUTUBE.COM/watch?v=123"]);
    if (compiled.length !== 2) {{
      throw new Error(`Expected 2 compiled rules, got ${{compiled.length}}`);
    }}
    if (compiled[0].action.redirect.extensionPath !== "/src/blocked.html?domain=reddit.com") {{
      throw new Error(`Redirect path mismatch: ${{compiled[0].action.redirect.extensionPath}}`);
    }}
    if (compiled[1].action.redirect.extensionPath !== "/src/blocked.html?domain=youtube.com") {{
      throw new Error(`Redirect path mismatch for youtube: ${{compiled[1].action.redirect.extensionPath}}`);
    }}
    if (compiled[1].condition.urlFilter !== "||youtube.com^") {{
      throw new Error(`urlFilter mismatch: ${{compiled[1].condition.urlFilter}}`);
    }}

    // 2. Test syncAndApplyRules with config profile
    const testConfig = {{
      version: 1,
      profile_name: "TestProfile",
      block_rules: [
        {{
          domains: ["news.ycombinator.com", "reddit.com"],
          start_hour: 22,
          start_minute: 0,
          end_hour: 6,
          end_minute: 0,
          active: true
        }},
        {{
          domains: ["reddit.com", "twitter.com"], // duplicate reddit.com
          start_hour: 9,
          start_minute: 0,
          end_hour: 17,
          end_minute: 0,
          active: true
        }},
        {{
          domains: ["facebook.com"], // inactive rule: should NOT be blocked
          start_hour: 12,
          start_minute: 0,
          end_hour: 13,
          end_minute: 0,
          active: false
        }}
      ]
    }};

    const appliedRules = await syncAndApplyRules(testConfig);

    if (!lastUpdateArgs.removeRuleIds.includes(999)) {{
      throw new Error("syncAndApplyRules did not remove previous rule 999");
    }}
    if (appliedRules.length !== 3) {{
      throw new Error(`Expected 3 unique active rules, got ${{appliedRules.length}}`);
    }}
    if (dynamicRules.length !== 3) {{
      throw new Error(`dynamicRules count mismatch: ${{dynamicRules.length}}`);
    }}

    const filters = dynamicRules.map(r => r.condition.urlFilter);
    if (!filters.includes("||news.ycombinator.com^") ||
        !filters.includes("||reddit.com^") ||
        !filters.includes("||twitter.com^")) {{
      throw new Error(`Applied filters mismatch: ${{JSON.stringify(filters)}}`);
    }}
    if (filters.includes("||facebook.com^")) {{
      throw new Error("Inactive rule domain facebook.com must NOT be in dynamic rules");
    }}

    // Check redirect paths
    const hnRule = dynamicRules.find(r => r.condition.urlFilter === "||news.ycombinator.com^");
    if (!hnRule || hnRule.action.redirect.extensionPath !== "/src/blocked.html?domain=news.ycombinator.com") {{
      throw new Error(`HN rule redirect invalid: ${{JSON.stringify(hnRule)}}`);
    }}

    console.log("SYNC_AND_APPLY_RULES_UNIT_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "SYNC_AND_APPLY_RULES_UNIT_PASSED" in res.stdout


def test_node_sync_poll_dynamic_rule_updates_and_removal():
    """Verify that fetching updated config dynamically compiles and swaps rules without browser reload."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{
      isBlockingActive: true,
      cachedConfig: null
    }};
    let dynamicRules = [];
    let badgeState = {{ text: "ON", color: "#22C55E" }};

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
        onStartup: {{ addListener: () => {{}} }}
      }}
    }};

    let currentServerProfile = {{
      version: 1,
      profile_name: "InitialProfile",
      app_close_schedule: {{ target_hour: 22, target_minute: 0, enabled: true }},
      block_rules: [
        {{
          domains: ["site-a.com", "site-b.com"],
          start_hour: 0,
          start_minute: 0,
          end_hour: 23,
          end_minute: 59,
          active: true
        }}
      ]
    }};

    globalThis.fetch = async (url) => {{
      return {{
        ok: true,
        status: 200,
        json: async () => currentServerProfile
      }};
    }};

    const {{ fetchConfigFromApp }} = await import('{sync_path.as_uri()}');

    // 1. Initial sync poll: compiles site-a.com and site-b.com
    const sync1 = await fetchConfigFromApp(8765, 8765);
    if (!sync1.success) throw new Error("Sync 1 failed");

    if (dynamicRules.length !== 2) {{
      throw new Error(`Expected 2 dynamic rules after initial sync, got ${{dynamicRules.length}}`);
    }}
    let domainFilters = dynamicRules.map(r => r.condition.urlFilter);
    if (!domainFilters.includes("||site-a.com^") || !domainFilters.includes("||site-b.com^")) {{
      throw new Error(`Domain filters mismatch after sync 1: ${{JSON.stringify(domainFilters)}}`);
    }}

    // 2. User adds news.ycombinator.com and removes site-b.com in Desktop app
    currentServerProfile = {{
      version: 2,
      profile_name: "UpdatedProfile",
      app_close_schedule: {{ target_hour: 22, target_minute: 0, enabled: true }},
      block_rules: [
        {{
          domains: ["site-a.com", "news.ycombinator.com"],
          start_hour: 0,
          start_minute: 0,
          end_hour: 23,
          end_minute: 59,
          active: true
        }}
      ]
    }};

    // Next sync pulse
    const sync2 = await fetchConfigFromApp(8765, 8765);
    if (!sync2.success) throw new Error("Sync 2 failed");

    if (dynamicRules.length !== 2) {{
      throw new Error(`Expected 2 dynamic rules after sync 2, got ${{dynamicRules.length}}`);
    }}
    domainFilters = dynamicRules.map(r => r.condition.urlFilter);
    if (!domainFilters.includes("||site-a.com^") || !domainFilters.includes("||news.ycombinator.com^")) {{
      throw new Error(`Domain filters mismatch after sync 2: ${{JSON.stringify(domainFilters)}}`);
    }}
    if (domainFilters.includes("||site-b.com^")) {{
      throw new Error("Removed domain site-b.com must not be present in dynamic rules!");
    }}

    // Check redirect parameter for newly added domain
    const hnRule = dynamicRules.find(r => r.condition.urlFilter === "||news.ycombinator.com^");
    if (hnRule.action.redirect.extensionPath !== "/src/blocked.html?domain=news.ycombinator.com") {{
      throw new Error(`Redirect mismatch for HN: ${{hnRule.action.redirect.extensionPath}}`);
    }}

    console.log("SYNC_POLL_DYNAMIC_RULE_UPDATES_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "SYNC_POLL_DYNAMIC_RULE_UPDATES_PASSED" in res.stdout


def test_node_sync_poll_schedule_reevaluation():
    """Verify that updating bedtime schedule in desktop app recalculates extension blocking state immediately."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{
      isBlockingActive: false,
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
        onStartup: {{ addListener: () => {{}} }}
      }}
    }};

    const currentHour = new Date().getHours();
    const outsideHour = (currentHour + 6) % 24;
    const outsideEndHour = (currentHour + 8) % 24;

    // 1. Initial profile has schedule outside current time -> Blocking OFF
    let serverProfile = {{
      version: 1,
      profile_name: "DaytimeSchedule",
      block_rules: [
        {{
          domains: ["reddit.com"],
          start_hour: outsideHour,
          start_minute: 0,
          end_hour: outsideEndHour,
          end_minute: 0,
          active: true
        }}
      ]
    }};

    globalThis.fetch = async () => ({{
      ok: true,
      status: 200,
      json: async () => serverProfile
    }});

    const {{ fetchConfigFromApp }} = await import('{sync_path.as_uri()}');

    await fetchConfigFromApp(8765, 8765);

    if (storageState.isBlockingActive !== false) {{
      throw new Error("Blocking should be false when outside scheduled bedtime");
    }}
    if (badgeState.text !== "") {{
      throw new Error(`Badge text should be empty when outside schedule, got: '${{badgeState.text}}'`);
    }}
    if (dynamicRules.length !== 0) {{
      throw new Error("Dynamic rules should be empty when outside schedule");
    }}

    // 2. User updates bedtime in Desktop app to include current hour -> Blocking turns ON immediately
    serverProfile = {{
      version: 2,
      profile_name: "ActiveBedtimeSchedule",
      block_rules: [
        {{
          domains: ["reddit.com", "youtube.com"],
          start_hour: currentHour,
          start_minute: 0,
          end_hour: (currentHour + 2) % 24,
          end_minute: 0,
          active: true
        }}
      ]
    }};

    await fetchConfigFromApp(8765, 8765);

    if (storageState.isBlockingActive !== true) {{
      throw new Error("Blocking MUST be true after syncing active bedtime schedule");
    }}
    if (badgeState.text !== "ON") {{
      throw new Error(`Badge text must be 'ON' after entering schedule, got: '${{badgeState.text}}'`);
    }}
    if (dynamicRules.length !== 2) {{
      throw new Error(`Expected 2 dynamic rules applied, got ${{dynamicRules.length}}`);
    }}

    console.log("SYNC_POLL_SCHEDULE_REEVALUATION_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "SYNC_POLL_SCHEDULE_REEVALUATION_PASSED" in res.stdout


def test_node_sync_poll_focus_lock_preservation():
    """Verify that syncing new config during an active Focus Lock session updates rules while keeping lock intact."""
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    const now = Date.now();
    let storageState = {{
      isBlockingActive: true,
      lockedUntil: now + 30 * 60 * 1000, // Locked for 30 minutes
      cachedConfig: null
    }};
    let dynamicRules = [];
    let badgeState = {{ text: "LOCK", color: "#8B5CF6" }};

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
        onStartup: {{ addListener: () => {{}} }}
      }}
    }};

    let serverProfile = {{
      version: 1,
      profile_name: "FocusLockSync",
      block_rules: [
        {{
          domains: ["distraction1.com", "distraction2.com", "distraction3.com"],
          start_hour: 0,
          start_minute: 0,
          end_hour: 1,
          end_minute: 0,
          active: true
        }}
      ]
    }};

    globalThis.fetch = async () => ({{
      ok: true,
      status: 200,
      json: async () => serverProfile
    }});

    const {{ fetchConfigFromApp }} = await import('{sync_path.as_uri()}');

    await fetchConfigFromApp(8765, 8765);

    // Dynamic rules should be updated to all 3 domains
    if (dynamicRules.length !== 3) {{
      throw new Error(`Expected 3 dynamic rules applied during focus lock, got ${{dynamicRules.length}}`);
    }}
    // Focus lock should still be active
    if (!storageState.lockedUntil || storageState.lockedUntil <= now) {{
      throw new Error("lockedUntil was unexpectedly cleared during config sync!");
    }}

    console.log("SYNC_POLL_FOCUS_LOCK_PRESERVATION_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "SYNC_POLL_FOCUS_LOCK_PRESERVATION_PASSED" in res.stdout


def test_live_api_server_sync_and_apply_rules_integration():
    """End-to-end integration test with live APIServer verifying real-time dynamic rule application and redirects."""
    port = get_free_port()
    initial_profile = ConfigProfile(
        profile_name="LiveSyncDynamicRulesProfile",
        app_close_schedule=AppCloseSchedule(
            target_hour=22,
            target_minute=0,
            enabled=True,
        ),
        block_rules=[
            BlockRule(
                domains=["live-site-a.com", "live-site-b.com"],
                start_hour=0,
                start_minute=0,
                end_hour=23,
                end_minute=59,
                active=True,
            )
        ],
        override_policy=OverridePolicy(
            friction_type="math",
            cooldown_minutes=15,
        ),
    )

    current_profile = initial_profile

    server = APIServer(
        host="127.0.0.1",
        port=port,
        config_provider=lambda: current_profile,
    )
    server.start()

    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{
      isBlockingActive: false,
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
        onStartup: {{ addListener: () => {{}} }}
      }}
    }};

    const {{ fetchConfigFromApp, getSyncStatus }} = await import('{sync_path.as_uri()}');

    // 1. Initial live fetch
    const res1 = await fetchConfigFromApp({port}, {port});
    if (!res1.success || res1.port !== {port}) {{
      throw new Error(`Live sync 1 failed: ${{JSON.stringify(res1)}}`);
    }}

    if (dynamicRules.length !== 2) {{
      throw new Error(`Expected 2 live dynamic rules, got ${{dynamicRules.length}}`);
    }}
    if (storageState.isBlockingActive !== true) {{
      throw new Error("isBlockingActive should be true for all-day schedule");
    }}
    if (badgeState.text !== "ON") {{
      throw new Error(`Expected badge ON, got ${{badgeState.text}}`);
    }}

    // Check redirect url includes query parameter
    const ruleA = dynamicRules.find(r => r.condition.urlFilter === "||live-site-a.com^");
    if (!ruleA || ruleA.action.redirect.extensionPath !== "/src/blocked.html?domain=live-site-a.com") {{
      throw new Error(`Redirect url invalid for ruleA: ${{JSON.stringify(ruleA)}}`);
    }}

    console.log("LIVE_SYNC_DYNAMIC_RULES_INTEGRATION_PASSED");
    """

    try:
        res = subprocess.run(
            ["node", "--input-type=module", "-e", js_test_script],
            capture_output=True,
            text=True,
            check=False
        )

        assert res.returncode == 0, f"Live sync integration failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
        assert "LIVE_SYNC_DYNAMIC_RULES_INTEGRATION_PASSED" in res.stdout
    finally:
        server.stop()
