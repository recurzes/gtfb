"""Tests for Extension Storage Cache Layer (feat/ext-storage-cache)."""

import json
from pathlib import Path
import subprocess
import pytest

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"
SRC_DIR = EXTENSION_DIR / "src"


def test_storage_files_exist():
    """Verify storage.js, rules.js, background.js, popup.js, and manifest.json exist."""
    assert (SRC_DIR / "storage.js").is_file(), "storage.js must exist in extension/src/"
    assert (SRC_DIR / "rules.js").is_file(), "rules.js must exist in extension/src/"
    assert (SRC_DIR / "background.js").is_file(), "background.js must exist in extension/src/"
    assert (SRC_DIR / "popup.js").is_file(), "popup.js must exist in extension/src/"
    assert (EXTENSION_DIR / "manifest.json").is_file(), "manifest.json must exist in extension/"


def test_manifest_storage_permission():
    """Verify manifest.json declares the 'storage' permission."""
    manifest_path = EXTENSION_DIR / "manifest.json"
    content = json.loads(manifest_path.read_text(encoding="utf-8"))
    permissions = content.get("permissions", [])
    assert "storage" in permissions, "manifest.json must include 'storage' in permissions"


def test_node_storage_module_crud_and_defaults():
    """Execute storage.js in Node.js to verify defaults, getters/setters, timestamps, and active domain extraction."""
    storage_path = SRC_DIR / "storage.js"

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

    const {{
      DEFAULT_CONFIG,
      DEFAULT_API_PORT,
      getCachedConfig,
      saveCachedConfig,
      getActiveDomains,
      getApiPort,
      setApiPort,
      getLastSyncedAt
    }} = await import('{storage_path.as_uri()}');

    // 1. Verify DEFAULT_CONFIG structure
    if (!DEFAULT_CONFIG.version || !DEFAULT_CONFIG.block_rules || !Array.isArray(DEFAULT_CONFIG.block_rules)) {{
      throw new Error("DEFAULT_CONFIG must contain version and block_rules array");
    }}
    if (DEFAULT_API_PORT !== 8765) {{
      throw new Error(`DEFAULT_API_PORT must be 8765, got ${{DEFAULT_API_PORT}}`);
    }}

    // 2. Empty storage fallback: getCachedConfig() initializes storage with DEFAULT_CONFIG
    const initialConfig = await getCachedConfig();
    if (!initialConfig || initialConfig.version !== 1) {{
      throw new Error("getCachedConfig() did not return DEFAULT_CONFIG on empty storage");
    }}
    if (!storageState.cachedConfig) {{
      throw new Error("getCachedConfig() did not persist DEFAULT_CONFIG to storage");
    }}
    if (!storageState.lastSyncedAt) {{
      throw new Error("saveCachedConfig should set lastSyncedAt timestamp");
    }}

    // 3. Verify getActiveDomains with default config
    const defaultDomains = await getActiveDomains();
    const expectedDefaults = ["reddit.com", "youtube.com", "x.com", "twitter.com", "instagram.com"];
    for (const d of expectedDefaults) {{
      if (!defaultDomains.includes(d)) {{
        throw new Error(`getActiveDomains missing default domain: ${{d}}`);
      }}
    }}

    // 4. Save custom configuration and verify active domain extraction and deduplication
    const customConfig = {{
      version: 2,
      profile_name: "Strict Work",
      app_close_schedule: {{ target_hour: 23, target_minute: 0, enabled: true }},
      block_rules: [
        {{
          domains: ["news.ycombinator.com", "reddit.com", "twitch.tv"],
          start_hour: 9,
          start_minute: 0,
          end_hour: 17,
          end_minute: 0,
          active: true
        }},
        {{
          domains: ["tiktok.com", "reddit.com"], // Duplicate reddit.com
          start_hour: 22,
          start_minute: 0,
          end_hour: 6,
          end_minute: 0,
          active: true
        }},
        {{
          domains: ["facebook.com", "instagram.com"],
          start_hour: 12,
          start_minute: 0,
          end_hour: 13,
          end_minute: 0,
          active: false // Inactive rule: domains should NOT be included
        }}
      ]
    }};

    const beforeSave = Date.now();
    await saveCachedConfig(customConfig);
    const afterSave = Date.now();

    const storedConfig = await getCachedConfig();
    if (storedConfig.profile_name !== "Strict Work" || storedConfig.version !== 2) {{
      throw new Error("Stored config mismatch after saveCachedConfig");
    }}

    const lastSynced = await getLastSyncedAt();
    if (!lastSynced || lastSynced < beforeSave || lastSynced > afterSave) {{
      throw new Error(`Invalid lastSyncedAt timestamp: ${{lastSynced}}`);
    }}

    const activeDomains = await getActiveDomains();
    if (activeDomains.length !== 4) {{
      throw new Error(`Expected 4 deduplicated active domains, got ${{activeDomains.length}}: ${{JSON.stringify(activeDomains)}}`);
    }}
    if (!activeDomains.includes("news.ycombinator.com") || !activeDomains.includes("reddit.com") ||
        !activeDomains.includes("twitch.tv") || !activeDomains.includes("tiktok.com")) {{
      throw new Error(`Active domains missing expected values: ${{JSON.stringify(activeDomains)}}`);
    }}
    if (activeDomains.includes("facebook.com") || activeDomains.includes("instagram.com")) {{
      throw new Error("Inactive rule domains MUST NOT be included in getActiveDomains");
    }}

    // 5. Test API Port getter/setter
    const defaultPort = await getApiPort();
    if (defaultPort !== 8765) {{
      throw new Error(`Expected default apiPort 8765, got ${{defaultPort}}`);
    }}

    await setApiPort(9000);
    const updatedPort = await getApiPort();
    if (updatedPort !== 9000 || storageState.apiPort !== 9000) {{
      throw new Error(`Expected updated apiPort 9000, got ${{updatedPort}}`);
    }}

    console.log("STORAGE_MODULE_CRUD_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node storage module tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "STORAGE_MODULE_CRUD_TESTS_PASSED" in res.stdout


def test_node_rules_with_storage_cache():
    """Verify rules.js queries getActiveDomains from storage cache when applying block rules."""
    rules_path = SRC_DIR / "rules.js"

    js_test_script = f"""
    let storageState = {{}};
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
      declarativeNetRequest: {{
        getDynamicRules: async () => dynamicRules,
        updateDynamicRules: async (args) => {{
          dynamicRules = dynamicRules.filter(r => !args.removeRuleIds.includes(r.id));
          if (args.addRules && args.addRules.length > 0) {{
            dynamicRules.push(...args.addRules);
          }}
        }}
      }}
    }};

    const {{ applyBlockRules, clearBlockRules }} = await import('{rules_path.as_uri()}');

    // 1. Initial call without pre-existing storage: should apply default domains
    await applyBlockRules();
    if (dynamicRules.length !== 5) {{
      throw new Error(`Expected 5 default dynamic rules, got ${{dynamicRules.length}}`);
    }}

    // 2. Update storage with custom domain list and re-apply rules
    storageState.cachedConfig = {{
      version: 1,
      profile_name: "Custom",
      block_rules: [
        {{
          domains: ["discord.com", "twitch.tv", "netflix.com"],
          start_hour: 22,
          start_minute: 0,
          end_hour: 6,
          end_minute: 0,
          active: true
        }}
      ]
    }};

    await applyBlockRules(); // No arguments -> pulls from storage
    if (dynamicRules.length !== 3) {{
      throw new Error(`Expected 3 custom rules from storage cache, got ${{dynamicRules.length}}`);
    }}

    const appliedFilters = dynamicRules.map(r => r.condition.urlFilter);
    if (!appliedFilters.includes("||discord.com^") ||
        !appliedFilters.includes("||twitch.tv^") ||
        !appliedFilters.includes("||netflix.com^")) {{
      throw new Error(`Rules do not match custom cachedConfig: ${{JSON.stringify(appliedFilters)}}`);
    }}

    // 3. Clear rules
    await clearBlockRules();
    if (dynamicRules.length !== 0) {{
      throw new Error("clearBlockRules did not clear dynamic rules");
    }}

    console.log("RULES_STORAGE_CACHE_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node rules storage cache tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "RULES_STORAGE_CACHE_TESTS_PASSED" in res.stdout


def test_node_storage_persistence_across_restarts():
    """Verify configuration persists across clean memory reloads simulating browser restarts."""
    bg_path = SRC_DIR / "background.js"

    js_test_script = f"""
    // Persistent storage state across simulated restarts
    const persistentStorage = {{
      cachedConfig: {{
        version: 1,
        profile_name: "Custom Late Night",
        app_close_schedule: {{ target_hour: 23, target_minute: 30, enabled: true }},
        block_rules: [
          {{
            domains: ["bilibili.com", "weibo.com"],
            start_hour: 23,
            start_minute: 30,
            end_hour: 7,
            end_minute: 0,
            active: true
          }}
        ]
      }},
      isBlockingActive: false,
      apiPort: 8765
    }};

    let badgeState = {{ text: "", color: "" }};
    let dynamicRules = [];

    function setupChromeMock() {{
      globalThis.chrome = {{
        storage: {{
          local: {{
            get: async (keys) => {{
              const result = {{}};
              if (Array.isArray(keys)) {{
                keys.forEach(k => {{ result[k] = persistentStorage[k]; }});
              }} else if (typeof keys === 'string') {{
                result[keys] = persistentStorage[keys];
              }} else if (keys === null || keys === undefined) {{
                Object.assign(result, persistentStorage);
              }}
              return result;
            }},
            set: async (items) => {{
              Object.assign(persistentStorage, items);
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
    }}

    setupChromeMock();

    // Import background service worker
    const {{ evaluateCurrentSchedule }} = await import('{bg_path.as_uri()}');

    // 1. Check time during custom window (23:45)
    const lateNight = new Date(2026, 7, 29, 23, 45, 0);
    await evaluateCurrentSchedule(lateNight);

    if (persistentStorage.isBlockingActive !== true) {{
      throw new Error("isBlockingActive not set to true for custom cachedConfig window");
    }}
    if (dynamicRules.length !== 2) {{
      throw new Error(`Expected 2 custom rules applied, got ${{dynamicRules.length}}`);
    }}
    const appliedDomains = dynamicRules.map(r => r.condition.urlFilter);
    if (!appliedDomains.includes("||bilibili.com^") || !appliedDomains.includes("||weibo.com^")) {{
      throw new Error(`Applied rules mismatch: ${{JSON.stringify(appliedDomains)}}`);
    }}

    // 2. Check time outside custom window (08:00 next morning)
    const nextMorning = new Date(2026, 7, 30, 8, 0, 0);
    await evaluateCurrentSchedule(nextMorning);

    if (persistentStorage.isBlockingActive !== false) {{
      throw new Error("isBlockingActive should be false outside window");
    }}
    if (dynamicRules.length !== 0) {{
      throw new Error("Dynamic rules should be cleared outside window");
    }}

    console.log("STORAGE_PERSISTENCE_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node storage persistence tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "STORAGE_PERSISTENCE_TESTS_PASSED" in res.stdout


def test_node_popup_domain_count_updates():
    """Verify popup.js refreshDomainCount reflects cached configuration domains."""
    popup_path = SRC_DIR / "popup.js"

    js_test_script = f"""
    let storageState = {{
      cachedConfig: {{
        version: 1,
        profile_name: "Multi-Rule",
        block_rules: [
          {{ domains: ["site1.com", "site2.com"], active: true }},
          {{ domains: ["site3.com"], active: true }},
          {{ domains: ["site4.com"], active: false }}
        ]
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

    let domainCountText = "";
    globalThis.document = {{
      getElementById: (id) => {{
        if (id === "domainCount") {{
          return {{
            set textContent(val) {{ domainCountText = val; }},
            get textContent() {{ return domainCountText; }}
          }};
        }}
        return null;
      }}
    }};

    const {{ refreshDomainCount }} = await import('{popup_path.as_uri()}');

    await refreshDomainCount();

    if (domainCountText !== "3 domains configured") {{
      throw new Error(`Expected '3 domains configured', got: '${{domainCountText}}'`);
    }}

    console.log("POPUP_DOMAIN_COUNT_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node popup domain count tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "POPUP_DOMAIN_COUNT_TESTS_PASSED" in res.stdout
