"""Tests for declarativeNetRequest Static Blocklist & Rule Management."""

import json
from pathlib import Path
import subprocess
import pytest

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"
SRC_DIR = EXTENSION_DIR / "src"


def test_manifest_declarative_net_request_permissions():
    """Verify manifest.json contains declarativeNetRequest permission and module background."""
    manifest_path = EXTENSION_DIR / "manifest.json"
    assert manifest_path.is_file(), "manifest.json must exist"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("manifest_version") == 3
    permissions = manifest.get("permissions", [])
    assert "declarativeNetRequest" in permissions, "declarativeNetRequest permission required"

    background = manifest.get("background", {})
    assert background.get("service_worker") == "src/background.js"
    assert background.get("type") == "module", "background service worker should be configured as type: module"


def test_blocked_html_placeholder_exists():
    """Verify blocked.html exists as an extension redirect target."""
    blocked_path = SRC_DIR / "blocked.html"
    assert blocked_path.is_file(), "blocked.html must exist in extension/src/"
    content = blocked_path.read_text(encoding="utf-8")
    assert "Blocked" in content
    assert "<html" in content.lower()


def test_rules_file_exists_and_exports():
    """Verify rules.js exists and exports required constants and functions."""
    rules_path = SRC_DIR / "rules.js"
    assert rules_path.is_file(), "rules.js must exist in extension/src/"
    content = rules_path.read_text(encoding="utf-8")

    assert "TEST_DOMAINS" in content
    assert "compileBlockRules" in content
    assert "applyBlockRules" in content
    assert "clearBlockRules" in content
    assert "sanitizeDomain" in content


def test_background_service_worker_lifecycle():
    """Verify background.js imports rules and binds onInstalled and onStartup events."""
    bg_path = SRC_DIR / "background.js"
    assert bg_path.is_file(), "background.js must exist in extension/src/"
    content = bg_path.read_text(encoding="utf-8")

    assert "import" in content
    assert "applyBlockRules" in content
    assert "chrome.runtime.onInstalled.addListener" in content
    assert "chrome.runtime.onStartup.addListener" in content


def test_node_rules_module_execution():
    """Execute rules.js using Node.js to test rule compilation, sanitization, and chrome API interaction."""
    rules_path = SRC_DIR / "rules.js"
    rules_file_url = rules_path.as_uri()

    js_test_script = f"""
    import {{
      TEST_DOMAINS,
      sanitizeDomain,
      compileBlockRules,
      applyBlockRules,
      clearBlockRules
    }} from '{rules_file_url}';

    // 1. Check TEST_DOMAINS
    if (!Array.isArray(TEST_DOMAINS) || TEST_DOMAINS.length === 0) {{
      throw new Error("TEST_DOMAINS should be a non-empty array");
    }}
    const expected = ["reddit.com", "youtube.com", "x.com", "twitter.com", "instagram.com"];
    for (const d of expected) {{
      if (!TEST_DOMAINS.includes(d)) {{
        throw new Error(`TEST_DOMAINS missing ${{d}}`);
      }}
    }}

    // 2. Test sanitizeDomain
    if (sanitizeDomain("https://www.reddit.com/r/all?sort=top") !== "www.reddit.com") {{
      throw new Error("sanitizeDomain failed on URL with path and query");
    }}
    if (sanitizeDomain("  HTTP://YOUTUBE.COM:8080/feed/subscriptions  ") !== "youtube.com") {{
      throw new Error("sanitizeDomain failed on uppercase, port, and spaces");
    }}
    if (sanitizeDomain("") !== "" || sanitizeDomain(null) !== "") {{
      throw new Error("sanitizeDomain failed on empty / null input");
    }}

    // 3. Test compileBlockRules with default domains
    const defaultRules = compileBlockRules();
    if (defaultRules.length !== TEST_DOMAINS.length) {{
      throw new Error("compileBlockRules() did not produce rules matching TEST_DOMAINS length");
    }}

    defaultRules.forEach((rule, idx) => {{
      if (rule.id !== idx + 1) throw new Error(`Invalid rule id at index ${{idx}}`);
      if (rule.priority !== 1) throw new Error(`Invalid priority for rule ${{rule.id}}`);
      if (!rule.action || rule.action.type !== "redirect" || !rule.action.redirect?.extensionPath?.startsWith("/src/blocked.html")) {{
        throw new Error(`Invalid action for rule ${{rule.id}}`);
      }}
      if (!rule.condition || rule.condition.urlFilter !== `||${{TEST_DOMAINS[idx]}}`) {{
        throw new Error(`Invalid condition urlFilter for rule ${{rule.id}}`);
      }}
      if (!Array.isArray(rule.condition.resourceTypes) || !rule.condition.resourceTypes.includes("main_frame")) {{
        throw new Error(`Invalid resourceTypes for rule ${{rule.id}}`);
      }}
    }});

    // 4. Test compileBlockRules with custom and messy domain inputs
    const customRules = compileBlockRules([
      "https://facebook.com/home",
      "TIKTOK.COM",
      "https://facebook.com/messages", // duplicate after sanitization
      "",
      "  ",
      "threads.net"
    ]);

    if (customRules.length !== 3) {{
      throw new Error(`Expected 3 deduplicated custom rules, got ${{customRules.length}}`);
    }}
    if (customRules[0].condition.urlFilter !== "||facebook.com") {{
      throw new Error("Custom rule 0 urlFilter mismatch");
    }}
    if (customRules[1].condition.urlFilter !== "||tiktok.com") {{
      throw new Error("Custom rule 1 urlFilter mismatch");
    }}
    if (customRules[2].condition.urlFilter !== "||threads.net") {{
      throw new Error("Custom rule 2 urlFilter mismatch");
    }}

    // 5. Test applyBlockRules and clearBlockRules with mock chrome API
    let dynamicRulesState = [
      {{ id: 99, priority: 1, action: {{ type: "block" }}, condition: {{ urlFilter: "old.com" }} }}
    ];
    let lastUpdateArgs = null;

    globalThis.chrome = {{
      declarativeNetRequest: {{
        getDynamicRules: async () => dynamicRulesState,
        updateDynamicRules: async (args) => {{
          lastUpdateArgs = args;
          // Apply removals
          dynamicRulesState = dynamicRulesState.filter(r => !args.removeRuleIds.includes(r.id));
          // Apply additions
          if (args.addRules && args.addRules.length > 0) {{
            dynamicRulesState.push(...args.addRules);
          }}
        }}
      }}
    }};

    // Run applyBlockRules
    await applyBlockRules(["reddit.com", "youtube.com"]);
    if (!lastUpdateArgs.removeRuleIds.includes(99)) {{
      throw new Error("applyBlockRules did not remove existing rule id 99");
    }}
    if (lastUpdateArgs.addRules.length !== 2) {{
      throw new Error("applyBlockRules did not add 2 new rules");
    }}
    if (dynamicRulesState.length !== 2) {{
      throw new Error("dynamicRulesState count mismatch after applyBlockRules");
    }}

    // Run clearBlockRules
    await clearBlockRules();
    if (lastUpdateArgs.addRules.length !== 0) {{
      throw new Error("clearBlockRules should pass empty addRules");
    }}
    if (dynamicRulesState.length !== 0) {{
      throw new Error("dynamicRulesState should be empty after clearBlockRules");
    }}

    console.log("ALL_JS_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "ALL_JS_TESTS_PASSED" in res.stdout
