"""Tests for Mozilla Firefox Manual Verification & Cross-Browser Integration (feat/ext-firefox-manual-test)."""

from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import unittest
import urllib.request
import pytest

from gtfb.api import APIServer, ExtensionStatusStore
from gtfb.ui.tray import TrayApp

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
EXTENSION_DIR = PROJECT_ROOT / "extension"
SRC_DIR = EXTENSION_DIR / "src"
LIB_DIR = EXTENSION_DIR / "lib"


def get_free_port() -> int:
    """Find and return an ephemeral open port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_firefox_guide_file_exists_and_content():
    """Verify docs/firefox_guide.md exists and contains complete verification instructions."""
    guide_path = DOCS_DIR / "firefox_guide.md"
    assert guide_path.is_file(), "docs/firefox_guide.md must exist"

    content = guide_path.read_text(encoding="utf-8")
    assert len(content) > 1500, "firefox_guide.md appears truncated or incomplete"

    # Verify key sections and topics
    assert "about:debugging#/runtime/this-firefox" in content
    assert "Load Temporary Add-on" in content
    assert "gtfb@local.dev" in content
    assert "moz-extension://" in content
    assert "declarativeNetRequest" in content
    assert "blocked.html" in content
    assert "● Extension: Connected (Firefox — Active)" in content
    assert "Temporary Add-on Lifetime" in content
    assert "browser.declarativeNetRequest.getDynamicRules()" in content
    assert "Offline Enforcement" in content or "offline" in content.lower()


def test_manifest_firefox_compatibility_spec():
    """Verify manifest.json adheres strictly to Firefox MV3 and Gecko configuration requirements."""
    manifest_path = EXTENSION_DIR / "manifest.json"
    assert manifest_path.is_file()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("manifest_version") == 3
    assert manifest.get("name") == "GTFB — Anti-Distraction Suite"
    assert manifest.get("version") == "1.0.0"

    # Gecko configuration
    gecko = manifest.get("browser_specific_settings", {}).get("gecko", {})
    assert gecko.get("id") == "gtfb@local.dev"
    assert gecko.get("strict_min_version") == "109.0"

    # Permissions
    permissions = manifest.get("permissions", [])
    assert "declarativeNetRequest" in permissions
    assert "storage" in permissions
    assert "alarms" in permissions
    assert "*://*/*" in manifest.get("host_permissions", [])

    # Background service worker
    background = manifest.get("background", {})
    assert background.get("service_worker") == "src/background.js"
    assert background.get("type") == "module"
    worker_file = EXTENSION_DIR / "src" / "background.js"
    assert worker_file.is_file(), f"Background worker script not found: {worker_file}"



def test_firefox_node_runtime_simulation():
    """Execute complete simulated Firefox runtime workflow in Node.js."""
    rules_path = SRC_DIR / "rules.js"
    storage_path = SRC_DIR / "storage.js"
    sync_path = SRC_DIR / "sync.js"
    compat_path = SRC_DIR / "compat.js"

    js_test_script = f"""
    let storageState = {{}};
    let dynamicRulesState = [];

    // Simulate Firefox browser environment
    delete globalThis.chrome;
    if (typeof globalThis.navigator === "undefined") {{
      globalThis.navigator = {{}};
    }}
    Object.defineProperty(globalThis.navigator, "userAgent", {{
      value: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
      configurable: true,
      writable: true
    }});

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
      runtime: {{
        getManifest: () => ({{
          manifest_version: 3,
          name: "GTFB — Anti-Distraction Suite",
          version: "1.0.0",
          browser_specific_settings: {{
            gecko: {{ id: "gtfb@local.dev", strict_min_version: "109.0" }}
          }}
        }})
      }}
    }};

    // 1. Test compat.js resolution in Firefox
    const {{ getExtApi, extApi }} = await import('{compat_path.as_uri()}');
    const api = getExtApi();
    if (api !== globalThis.browser) {{
      throw new Error("getExtApi did not resolve globalThis.browser in Firefox environment");
    }}

    // 2. Test rules compilation and application
    const {{ compileBlockRules, applyBlockRules }} = await import('{rules_path.as_uri()}');
    const testDomains = ["reddit.com", "youtube.com", "twitch.tv"];
    const compiled = compileBlockRules(testDomains);
    if (compiled.length !== 3) {{
      throw new Error(`Expected 3 compiled rules, got ${{compiled.length}}`);
    }}
    if (compiled[0].action.redirect.extensionPath !== "/src/blocked.html?domain=reddit.com") {{
      throw new Error("Compiled rule extensionPath mismatch");
    }}

    const applied = await applyBlockRules(testDomains);
    if (applied.length !== 3 || dynamicRulesState.length !== 3) {{
      throw new Error("Failed to apply dynamic rules in simulated Firefox");
    }}

    // 3. Test storage caching
    const {{ saveCachedConfig, getCachedConfig, getActiveDomains }} = await import('{storage_path.as_uri()}');
    const testConfig = {{
      version: 1,
      profile_name: "Firefox Dev Profile",
      block_rules: [
        {{ domains: ["reddit.com", "youtube.com", "twitch.tv"], active: true }}
      ]
    }};
    await saveCachedConfig(testConfig);
    const cached = await getCachedConfig();
    if (cached.profile_name !== "Firefox Dev Profile") {{
      throw new Error("Cached profile name mismatch in Firefox storage");
    }}

    const activeDomains = await getActiveDomains();
    if (activeDomains.length !== 3 || !activeDomains.includes("twitch.tv")) {{
      throw new Error("Active domains mismatch in Firefox storage");
    }}

    // 4. Test status reporting payload generation with Firefox User Agent
    const {{ reportStatusToApp }} = await import('{sync_path.as_uri()}');
    // Mock fetch to capture payload
    let capturedPayload = null;
    globalThis.fetch = async (url, options) => {{
      if (url.includes("/status") && options.method === "POST") {{
        capturedPayload = JSON.parse(options.body);
        return {{ ok: true, status: 200, json: async () => ({{ status: "received" }}) }};
      }}
      return {{ ok: false, status: 404 }};
    }};

    storageState.isBlockingActive = true;
    const reportRes = await reportStatusToApp(8765);
    if (!reportRes.success) {{
      throw new Error("reportStatusToApp failed in Firefox simulation");
    }}
    if (!capturedPayload) {{
      throw new Error("No payload captured during reportStatusToApp");
    }}
    if (capturedPayload.browser !== "firefox") {{
      throw new Error(`Expected browser 'firefox', got '${{capturedPayload.browser}}'`);
    }}
    if (capturedPayload.blocking_active !== true) {{
      throw new Error("Expected blocking_active to be true");
    }}
    if (capturedPayload.rules_count !== 3) {{
      throw new Error(`Expected rules_count to be 3, got ${{capturedPayload.rules_count}}`);
    }}

    console.log("FIREFOX_SIMULATION_SUCCESSFUL");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert res.returncode == 0, f"Node Firefox simulation failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "FIREFOX_SIMULATION_SUCCESSFUL" in res.stdout


class TestFirefoxDesktopTrayIntegration(unittest.TestCase):
    """End-to-end integration test verifying desktop TrayApp correctly recognizes Firefox telemetry."""

    def setUp(self):
        self.port = get_free_port()
        self.status_store = ExtensionStatusStore()
        self.server = APIServer(
            host="127.0.0.1", port=self.port, status_store=self.status_store
        )
        self.tray_app = TrayApp(
            api_server=self.server, status_store=self.status_store
        )

    def tearDown(self):
        if self.server and self.server.is_running:
            self.server.stop()

    def test_firefox_heartbeat_and_tray_status_display(self):
        """Verify TrayApp displays '● Extension: Connected (Firefox — Active)' and 'Inactive'."""
        self.assertEqual(
            self.tray_app.get_extension_status_text(),
            "○ Extension: Not Connected",
        )

        self.server.start()

        # 1. Send Firefox active status heartbeat
        firefox_active_payload = {
            "browser": "firefox",
            "version": "1.0.0",
            "blocking_active": True,
            "rules_count": 4,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        req1 = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/status",
            data=json.dumps(firefox_active_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req1, timeout=5) as res1:
            self.assertEqual(res1.status, 200)

        self.assertEqual(
            self.tray_app.get_extension_status_text(),
            "● Extension: Connected (Firefox — Active)",
        )

        # 2. Send Firefox inactive status heartbeat (e.g. toggle OFF)
        firefox_inactive_payload = {
            "browser": "firefox",
            "version": "1.0.0",
            "blocking_active": False,
            "rules_count": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/status",
            data=json.dumps(firefox_inactive_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5) as res2:
            self.assertEqual(res2.status, 200)

        self.assertEqual(
            self.tray_app.get_extension_status_text(),
            "● Extension: Connected (Firefox — Inactive)",
        )


if __name__ == "__main__":
    pytest.main([__file__])
