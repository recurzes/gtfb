"""Tests for Extension Manual Toggle & Focus Lock Timer (feat/ext-manual-toggle)."""

import json
from pathlib import Path
import subprocess
import pytest

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"
SRC_DIR = EXTENSION_DIR / "src"


def test_popup_files_exist():
    """Verify popup.html, popup.css, popup.js, background.js, and rules.js exist."""
    assert (SRC_DIR / "popup.html").is_file(), "popup.html must exist"
    assert (SRC_DIR / "popup.css").is_file(), "popup.css must exist"
    assert (SRC_DIR / "popup.js").is_file(), "popup.js must exist"
    assert (SRC_DIR / "background.js").is_file(), "background.js must exist"
    assert (SRC_DIR / "rules.js").is_file(), "rules.js must exist"


def test_popup_html_structure():
    """Verify popup.html contains essential elements, IDs, and links."""
    content = (SRC_DIR / "popup.html").read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in content
    assert 'href="popup.css"' in content
    assert 'src="popup.js"' in content

    # Check key element IDs required by spec and focus lock
    assert 'id="blockingToggle"' in content
    assert 'id="statusLabel"' in content
    assert 'id="statusDetail"' in content
    assert 'id="syncStatus"' in content
    assert 'id="domainCount"' in content
    assert 'id="lockCountdown"' in content
    assert 'id="startLockBtn"' in content

    # Check text content
    assert "GTFB Suite" in content
    assert "Focus Lock" in content
    assert "Standalone" in content


def test_popup_css_design_system():
    """Verify popup.css contains design system tokens and component classes."""
    content = (SRC_DIR / "popup.css").read_text(encoding="utf-8")

    # Tokens
    assert "--bg-primary" in content
    assert "--bg-card" in content
    assert "--accent-emerald" in content
    assert "--accent-violet" in content

    # UI Classes
    assert ".main-control" in content
    assert ".switch" in content
    assert ".slider" in content
    assert ".lock-banner" in content
    assert ".chip" in content
    assert ".btn-start-lock" in content


def test_node_background_toggle_and_lock():
    """Execute background.js logic in Node.js to verify TOGGLE_BLOCKING, badge updates, and Focus Lock enforcement."""
    bg_path = SRC_DIR / "background.js"

    js_test_script = f"""
    // Mock chrome environment before dynamic module import
    let storageState = {{}};
    let badgeState = {{ text: "", color: "" }};
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
            }}
            return result;
          }},
          set: async (items) => {{
            Object.assign(storageState, items);
          }}
        }}
      }},
      action: {{
        setBadgeText: async (details) => {{
          badgeState.text = details.text;
        }},
        setBadgeBackgroundColor: async (details) => {{
          badgeState.color = details.color;
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
      }},
      runtime: {{
        onMessage: {{ addListener: () => {{}} }},
        onInstalled: {{ addListener: () => {{}} }},
        onStartup: {{ addListener: () => {{}} }}
      }}
    }};

    const {{ handleToggle, getBlockingStatus, startLockTimer }} = await import('{bg_path.as_uri()}');

    // 1. Test standard Toggle ON
    const onResult = await handleToggle(true);
    if (!onResult.success || !onResult.isBlockingActive) {{
      throw new Error("handleToggle(true) failed");
    }}
    if (badgeState.text !== "ON") {{
      throw new Error(`Expected badge text 'ON', got: ${{badgeState.text}}`);
    }}
    if (storageState.isBlockingActive !== true) {{
      throw new Error("storage isBlockingActive not true after toggle on");
    }}
    if (dynamicRules.length === 0) {{
      throw new Error("Dynamic rules not applied on toggle on");
    }}

    // 2. Test standard Toggle OFF
    const offResult = await handleToggle(false);
    if (!offResult.success || offResult.isBlockingActive) {{
      throw new Error("handleToggle(false) failed");
    }}
    if (badgeState.text !== "") {{
      throw new Error(`Expected badge text '', got: ${{badgeState.text}}`);
    }}
    if (storageState.isBlockingActive !== false) {{
      throw new Error("storage isBlockingActive not false after toggle off");
    }}
    if (dynamicRules.length !== 0) {{
      throw new Error("Dynamic rules not cleared on toggle off");
    }}

    // 3. Test Focus Lock Timer Activation
    const lockResult = await startLockTimer(25);
    if (!lockResult.success || !lockResult.isLocked || !lockResult.lockedUntil) {{
      throw new Error("startLockTimer(25) failed to start lock session");
    }}
    if (badgeState.text !== "LOCK") {{
      throw new Error(`Expected badge text 'LOCK', got: ${{badgeState.text}}`);
    }}
    if (dynamicRules.length === 0) {{
      throw new Error("Dynamic rules not active during lock");
    }}

    // 4. Test Lockout Enforcement: Attempting to toggle OFF while locked MUST fail
    const blockedToggleOff = await handleToggle(false);
    if (blockedToggleOff.success !== false) {{
      throw new Error("handleToggle(false) should have been rejected while focus lock is active!");
    }}
    if (badgeState.text !== "LOCK") {{
      throw new Error("Badge should remain 'LOCK' after rejected toggle off");
    }}
    if (dynamicRules.length === 0) {{
      throw new Error("Dynamic rules must remain active after rejected toggle off");
    }}

    // 5. Test Lock Expiration
    // Simulate expired lock
    storageState.lockedUntil = Date.now() - 1000;
    const statusAfterExpiry = await getBlockingStatus();
    if (statusAfterExpiry.isLocked) {{
      throw new Error("Expired lock should report isLocked: false");
    }}

    // Now toggle OFF should succeed
    const offAfterExpiry = await handleToggle(false);
    if (!offAfterExpiry.success || offAfterExpiry.isBlockingActive) {{
      throw new Error("Toggle OFF should succeed after lock expiration");
    }}
    if (badgeState.text !== "") {{
      throw new Error("Badge should be cleared after toggle off post-expiration");
    }}

    // 6. Test manual toggle OFF persistence during bedtime schedule
    const {{ evaluateCurrentSchedule }} = await import('{bg_path.as_uri()}');
    const bedtime = new Date(2026, 7, 29, 23, 0, 0); // 23:00
    await evaluateCurrentSchedule(bedtime);
    if (storageState.isBlockingActive !== false) {{
      throw new Error("evaluateCurrentSchedule re-enabled blocking after manual toggle OFF!");
    }}
    if (badgeState.text !== "") {{
      throw new Error("Badge should remain empty after manual toggle OFF during schedule check");
    }}
    if (dynamicRules.length !== 0) {{
      throw new Error("Dynamic rules should remain empty after manual toggle OFF");
    }}

    console.log("BACKGROUND_JS_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node background tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "BACKGROUND_JS_TESTS_PASSED" in res.stdout


def test_node_popup_ui_behavior():
    """Execute popup.js helper and UI state updater in Node.js."""
    popup_path = SRC_DIR / "popup.js"

    js_test_script = f"""
    import {{ formatTime, updateUI }} from '{popup_path.as_uri()}';

    // Test formatTime
    if (formatTime(1500) !== "25:00") {{
      throw new Error(`Expected '25:00', got: ${{formatTime(1500)}}`);
    }}
    if (formatTime(65) !== "01:05") {{
      throw new Error(`Expected '01:05', got: ${{formatTime(65)}}`);
    }}
    if (formatTime(0) !== "00:00") {{
      throw new Error(`Expected '00:00', got: ${{formatTime(0)}}`);
    }}

    // Setup mock DOM for updateUI tests
    function createMockPopupDOM() {{
      const classLists = {{}};
      function makeElem(id) {{
        classLists[id] = new Set();
        return {{
          id,
          textContent: '',
          checked: false,
          disabled: false,
          className: '',
          parentElement: {{
            classList: {{
              add: (cls) => classLists[id + '_p'] = classLists[id + '_p'] || new Set(),
              remove: (cls) => {{ if (classLists[id + '_p']) classLists[id + '_p'].delete(cls); }},
              contains: (cls) => Boolean(classLists[id + '_p'] && classLists[id + '_p'].has(cls))
            }}
          }},
          classList: {{
            add: (cls) => classLists[id].add(cls),
            remove: (cls) => classLists[id].delete(cls),
            contains: (cls) => classLists[id].has(cls)
          }}
        }};
      }}

      const elements = {{
        blockingToggle: makeElem('blockingToggle'),
        statusLabel: makeElem('statusLabel'),
        statusDetail: makeElem('statusDetail'),
        mainControlCard: makeElem('mainControlCard'),
        lockBanner: makeElem('lockBanner'),
        lockCountdown: makeElem('lockCountdown'),
        focusSection: makeElem('focusSection')
      }};

      globalThis.document = {{
        getElementById: (id) => elements[id] || null
      }};

      return elements;
    }}

    // Case 1: Active state
    const dom1 = createMockPopupDOM();
    updateUI({{ isBlockingActive: true, isLocked: false }});
    if (!dom1.blockingToggle.checked) throw new Error("Toggle should be checked when active");
    if (dom1.blockingToggle.disabled) throw new Error("Toggle should NOT be disabled when not locked");
    if (dom1.statusLabel.textContent !== "Blocking Active") throw new Error("Status label mismatch for active");
    if (!dom1.lockBanner.classList.contains("hidden")) throw new Error("Lock banner should be hidden when not locked");

    // Case 2: Inactive state
    const dom2 = createMockPopupDOM();
    updateUI({{ isBlockingActive: false, isLocked: false }});
    if (dom2.blockingToggle.checked) throw new Error("Toggle should be unchecked when inactive");
    if (dom2.statusLabel.textContent !== "Blocking Inactive") throw new Error("Status label mismatch for inactive");

    // Case 3: Locked state
    const dom3 = createMockPopupDOM();
    updateUI({{ isBlockingActive: true, isLocked: true, lockedUntil: Date.now() + 60000 }});
    if (!dom3.blockingToggle.checked) throw new Error("Toggle should be checked when locked");
    if (!dom3.blockingToggle.disabled) throw new Error("Toggle MUST be disabled when locked");
    if (dom3.statusLabel.textContent !== "Focus Locked") throw new Error("Status label should indicate Focus Locked");
    if (dom3.lockBanner.classList.contains("hidden")) throw new Error("Lock banner should NOT be hidden when locked");
    // Clean up active interval before finishing
    updateUI({{ isBlockingActive: false, isLocked: false }});

    console.log("POPUP_JS_TESTS_PASSED");
    process.exit(0);
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node popup tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "POPUP_JS_TESTS_PASSED" in res.stdout
