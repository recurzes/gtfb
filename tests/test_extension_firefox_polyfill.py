"""Tests for Firefox WebExtension Polyfill & Cross-Browser Compatibility (feat/ext-firefox-polyfill)."""

import json
from pathlib import Path
import subprocess
import pytest

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"
SRC_DIR = EXTENSION_DIR / "src"
LIB_DIR = EXTENSION_DIR / "lib"


def test_firefox_polyfill_files_exist():
    """Verify browser-polyfill vendored files and compat.js exist and are valid."""
    min_polyfill = LIB_DIR / "browser-polyfill.min.js"
    polyfill = LIB_DIR / "browser-polyfill.js"
    compat_js = SRC_DIR / "compat.js"

    assert min_polyfill.is_file(), "browser-polyfill.min.js must exist in extension/lib/"
    assert polyfill.is_file(), "browser-polyfill.js must exist in extension/lib/"
    assert compat_js.is_file(), "compat.js must exist in extension/src/"

    assert min_polyfill.stat().st_size > 5000, "browser-polyfill.min.js appears truncated"
    assert polyfill.stat().st_size > 10000, "browser-polyfill.js appears truncated"

    compat_content = compat_js.read_text(encoding="utf-8")
    assert "extApi" in compat_content
    assert "getExtApi" in compat_content


def test_manifest_firefox_gecko_settings():
    """Verify manifest.json contains Firefox browser_specific_settings and background scripts."""
    manifest_path = EXTENSION_DIR / "manifest.json"
    assert manifest_path.is_file()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Manifest V3 base keys
    assert manifest.get("manifest_version") == 3
    assert manifest.get("name") == "GTFB — Anti-Distraction Suite"
    assert manifest.get("version") == "1.0.0"

    # 2. Firefox Gecko settings
    gecko_settings = manifest.get("browser_specific_settings", {}).get("gecko", {})
    assert gecko_settings.get("id") == "gtfb@local.dev", "Gecko ID must be gtfb@local.dev"
    assert gecko_settings.get("strict_min_version") == "109.0", "Gecko strict_min_version must be 109.0"

    # 3. Background service worker compatibility for Firefox & Chromium
    background = manifest.get("background", {})
    assert background.get("service_worker") == "src/background.js"
    assert background.get("type") == "module"
    worker_file = EXTENSION_DIR / "src" / "background.js"
    assert worker_file.is_file(), f"Background worker script not found: {worker_file}"



def test_node_compat_api_resolution():
    """Execute compat.js in Node.js to verify dynamic resolution across browser vs chrome environments."""
    compat_path = SRC_DIR / "compat.js"

    js_test_script = f"""
    const {{ extApi, getExtApi }} = await import('{compat_path.as_uri()}');

    // 1. Initial state with neither browser nor chrome: safe fallback
    delete globalThis.browser;
    delete globalThis.chrome;
    const initialApi = getExtApi();
    if (typeof initialApi !== 'object' || initialApi === null) {{
      throw new Error("getExtApi() should return an empty object fallback when neither is defined");
    }}
    if (extApi.storage !== undefined) {{
      throw new Error("extApi.storage should be undefined when no global is set");
    }}

    // 2. Set chrome global (Chromium environment)
    globalThis.chrome = {{
      storage: {{ local: {{ marker: "chrome-storage" }} }},
      runtime: {{ id: "chrome-ext-id" }}
    }};

    if (extApi.storage?.local?.marker !== "chrome-storage") {{
      throw new Error("extApi failed to resolve chrome.storage.local");
    }}
    if (extApi.runtime?.id !== "chrome-ext-id") {{
      throw new Error("extApi failed to resolve chrome.runtime.id");
    }}

    // 3. Set browser global (Firefox environment) - browser should take priority
    globalThis.browser = {{
      storage: {{ local: {{ marker: "firefox-browser-storage" }} }},
      runtime: {{ id: "firefox-ext-id" }}
    }};

    if (extApi.storage?.local?.marker !== "firefox-browser-storage") {{
      throw new Error("extApi should prioritize browser over chrome when both exist");
    }}
    if (extApi.runtime?.id !== "firefox-ext-id") {{
      throw new Error("extApi should prioritize browser runtime");
    }}

    // 4. Remove chrome global - should still work with browser only
    delete globalThis.chrome;
    if (extApi.storage?.local?.marker !== "firefox-browser-storage") {{
      throw new Error("extApi failed to resolve when only browser global exists");
    }}

    console.log("COMPAT_RESOLUTION_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node compat resolution test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "COMPAT_RESOLUTION_TESTS_PASSED" in res.stdout


def test_node_firefox_storage_and_rules_promise_mode():
    """Verify storage.js and rules.js work in pure Firefox Promise-based browser.* environment."""
    storage_path = SRC_DIR / "storage.js"
    rules_path = SRC_DIR / "rules.js"

    js_test_script = f"""
    let storageState = {{}};
    let dynamicRulesState = [];

    // Mock purely Firefox W3C browser.* namespace without chrome.*
    delete globalThis.chrome;
    globalThis.browser = {{
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
        getDynamicRules: async () => dynamicRulesState,
        updateDynamicRules: async (args) => {{
          if (args.removeRuleIds) {{
            dynamicRulesState = dynamicRulesState.filter(r => !args.removeRuleIds.includes(r.id));
          }}
          if (args.addRules && args.addRules.length > 0) {{
            dynamicRulesState.push(...args.addRules);
          }}
        }}
      }}
    }};

    const {{
      getCachedConfig,
      saveCachedConfig,
      getActiveDomains,
      getApiPort,
      setApiPort,
      getLastSyncedAt
    }} = await import('{storage_path.as_uri()}');

    const {{
      compileBlockRules,
      applyBlockRules,
      clearBlockRules,
      syncAndApplyRules
    }} = await import('{rules_path.as_uri()}');

    // 1. Storage defaults in Firefox environment
    const config = await getCachedConfig();
    if (!config || config.profile_name !== "Default") {{
      throw new Error("Firefox mode: getCachedConfig did not return default config");
    }}
    if (!storageState.cachedConfig) {{
      throw new Error("Firefox mode: default config not written to storage");
    }}

    // 2. Storage set and get
    await setApiPort(8770);
    const port = await getApiPort();
    if (port !== 8770) {{
      throw new Error(`Firefox mode: getApiPort returned ${{port}}, expected 8770`);
    }}

    const lastSynced = await getLastSyncedAt();
    if (!lastSynced) {{
      throw new Error("Firefox mode: getLastSyncedAt returned null");
    }}

    // 3. Dynamic rules in Firefox declarativeNetRequest
    const rules = await applyBlockRules(["firefox.com", "mozilla.org"]);
    if (rules.length !== 2 || dynamicRulesState.length !== 2) {{
      throw new Error(`Firefox mode: Expected 2 dynamic rules, got ${{dynamicRulesState.length}}`);
    }}
    if (dynamicRulesState[0].condition.urlFilter !== "||firefox.com" ||
        dynamicRulesState[1].condition.urlFilter !== "||mozilla.org") {{
      throw new Error("Firefox mode: Dynamic rule filters mismatch");
    }}

    // 4. Sync and apply rules from custom profile
    const customConfig = {{
      version: 1,
      profile_name: "Dev Profile",
      block_rules: [
        {{ domains: ["news.ycombinator.com", "reddit.com"], active: true }},
        {{ domains: ["twitter.com"], active: false }}
      ]
    }};
    const applied = await syncAndApplyRules(customConfig);
    if (applied.length !== 2 || dynamicRulesState.length !== 2) {{
      throw new Error(`Firefox mode: syncAndApplyRules expected 2 rules, got ${{dynamicRulesState.length}}`);
    }}

    // 5. Clear rules
    await clearBlockRules();
    if (dynamicRulesState.length !== 0) {{
      throw new Error("Firefox mode: clearBlockRules did not empty dynamic rules");
    }}

    console.log("FIREFOX_STORAGE_RULES_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node Firefox storage & rules test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "FIREFOX_STORAGE_RULES_TESTS_PASSED" in res.stdout


def test_node_firefox_background_and_sync_execution():
    """Verify background.js and sync.js function with alarms, actions, and messages in Firefox mode."""
    bg_path = SRC_DIR / "background.js"
    sync_path = SRC_DIR / "sync.js"

    js_test_script = f"""
    let storageState = {{
      isBlockingActive: false,
      apiPort: 8765
    }};
    let dynamicRulesState = [];
    let badgeState = {{ text: "", color: "" }};
    let alarmsCreated = [];

    delete globalThis.chrome;
    globalThis.browser = {{
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
        getDynamicRules: async () => dynamicRulesState,
        updateDynamicRules: async (args) => {{
          if (args.removeRuleIds) {{
            dynamicRulesState = dynamicRulesState.filter(r => !args.removeRuleIds.includes(r.id));
          }}
          if (args.addRules && args.addRules.length > 0) {{
            dynamicRulesState.push(...args.addRules);
          }}
        }}
      }},
      action: {{
        setBadgeText: async (details) => {{ badgeState.text = details.text; }},
        setBadgeBackgroundColor: async (details) => {{ badgeState.color = details.color; }}
      }},
      alarms: {{
        create: (name, opts) => {{ alarmsCreated.push({{ name, opts }}); }},
        onAlarm: {{ addListener: () => {{}} }}
      }},
      runtime: {{
        getManifest: () => ({{ version: "1.0.0" }}),
        onMessage: {{ addListener: () => {{}} }},
        onInstalled: {{ addListener: () => {{}} }},
        onStartup: {{ addListener: () => {{}} }}
      }}
    }};

    const {{
      handleToggle,
      getBlockingStatus,
      startLockTimer,
      evaluateCurrentSchedule,
      setupScheduleAlarm
    }} = await import('{bg_path.as_uri()}');

    const {{
      getSyncStatus,
      setupSyncAlarm
    }} = await import('{sync_path.as_uri()}');

    // 1. Alarms registration
    setupScheduleAlarm();
    setupSyncAlarm(5);
    if (!alarmsCreated.some(a => a.name === "gtfb-schedule-check")) {{
      throw new Error("Firefox mode: schedule alarm not registered");
    }}
    if (!alarmsCreated.some(a => a.name === "gtfb-poll-sync")) {{
      throw new Error("Firefox mode: sync alarm not registered");
    }}

    // 2. Manual toggle enable
    const toggleRes = await handleToggle(true);
    if (!toggleRes.success || !toggleRes.isBlockingActive) {{
      throw new Error("Firefox mode: handleToggle(true) failed");
    }}
    if (badgeState.text !== "ON" || badgeState.color !== "#22C55E") {{
      throw new Error(`Firefox mode: Badge state mismatch on enable: ${{JSON.stringify(badgeState)}}`);
    }}
    if (dynamicRulesState.length === 0) {{
      throw new Error("Firefox mode: Blocking rules not applied on toggle enable");
    }}

    // 3. Focus lock timer
    const lockRes = await startLockTimer(30);
    if (!lockRes.success || !lockRes.isLocked) {{
      throw new Error("Firefox mode: startLockTimer failed");
    }}
    if (badgeState.text !== "LOCK" || badgeState.color !== "#8B5CF6") {{
      throw new Error(`Firefox mode: Badge state mismatch on lock: ${{JSON.stringify(badgeState)}}`);
    }}

    // 4. Attempt toggle disable during lock - MUST fail
    const rejectRes = await handleToggle(false);
    if (rejectRes.success !== false) {{
      throw new Error("Firefox mode: handleToggle(false) should be rejected while focus lock is active");
    }}

    // 5. Query blocking status
    const status = await getBlockingStatus();
    if (!status.isLocked || !status.isBlockingActive || status.remainingSeconds <= 0) {{
      throw new Error("Firefox mode: getBlockingStatus returned invalid locked status");
    }}

    // 6. Query sync status
    const syncStatus = await getSyncStatus();
    if (syncStatus.apiPort !== 8765) {{
      throw new Error(`Firefox mode: getSyncStatus apiPort mismatch: ${{syncStatus.apiPort}}`);
    }}

    console.log("FIREFOX_BG_SYNC_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node Firefox bg & sync test failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "FIREFOX_BG_SYNC_TESTS_PASSED" in res.stdout
