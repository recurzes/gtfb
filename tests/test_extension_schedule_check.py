"""Tests for Extension Background Schedule Evaluator (feat/ext-schedule-check)."""

import json
from pathlib import Path
import subprocess
import pytest

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"
SRC_DIR = EXTENSION_DIR / "src"


def test_scheduler_files_exist():
    """Verify scheduler_utils.js, background.js, rules.js, and manifest.json exist."""
    assert (SRC_DIR / "scheduler_utils.js").is_file(), "scheduler_utils.js must exist"
    assert (SRC_DIR / "background.js").is_file(), "background.js must exist"
    assert (SRC_DIR / "rules.js").is_file(), "rules.js must exist"
    assert (EXTENSION_DIR / "manifest.json").is_file(), "manifest.json must exist"


def test_manifest_alarms_permission():
    """Verify manifest.json declares the 'alarms' permission."""
    manifest_path = EXTENSION_DIR / "manifest.json"
    content = json.loads(manifest_path.read_text(encoding="utf-8"))
    permissions = content.get("permissions", [])
    assert "alarms" in permissions, "manifest.json must include 'alarms' in permissions"


def test_node_is_time_in_window_algorithm():
    """Execute isTimeInWindow in Node.js across same-day, overnight, and boundary edge cases."""
    scheduler_utils_path = SRC_DIR / "scheduler_utils.js"

    js_test_script = f"""
    import {{ isTimeInWindow }} from '{scheduler_utils_path.as_uri()}';

    function makeDate(hour, minute) {{
      const d = new Date(2026, 7, 29, hour, minute, 0, 0);
      return d;
    }}

    // 1. Same-day window (09:00 -> 17:00)
    // Before start
    if (isTimeInWindow(makeDate(8, 59), 9, 0, 17, 0) !== false) {{
      throw new Error("08:59 should NOT be in 09:00-17:00 window");
    }}
    // Exact start
    if (isTimeInWindow(makeDate(9, 0), 9, 0, 17, 0) !== true) {{
      throw new Error("09:00 MUST be in 09:00-17:00 window");
    }}
    // Middle
    if (isTimeInWindow(makeDate(12, 30), 9, 0, 17, 0) !== true) {{
      throw new Error("12:30 MUST be in 09:00-17:00 window");
    }}
    // Last minute
    if (isTimeInWindow(makeDate(16, 59), 9, 0, 17, 0) !== true) {{
      throw new Error("16:59 MUST be in 09:00-17:00 window");
    }}
    // Exact end (exclusive)
    if (isTimeInWindow(makeDate(17, 0), 9, 0, 17, 0) !== false) {{
      throw new Error("17:00 should NOT be in 09:00-17:00 window");
    }}
    // After end
    if (isTimeInWindow(makeDate(17, 1), 9, 0, 17, 0) !== false) {{
      throw new Error("17:01 should NOT be in 09:00-17:00 window");
    }}
    // Night
    if (isTimeInWindow(makeDate(23, 0), 9, 0, 17, 0) !== false) {{
      throw new Error("23:00 should NOT be in 09:00-17:00 window");
    }}

    // 2. Overnight window crossing midnight (22:00 -> 06:00)
    // Before window in evening
    if (isTimeInWindow(makeDate(21, 59), 22, 0, 6, 0) !== false) {{
      throw new Error("21:59 should NOT be in 22:00-06:00 window");
    }}
    // Exact start
    if (isTimeInWindow(makeDate(22, 0), 22, 0, 6, 0) !== true) {{
      throw new Error("22:00 MUST be in 22:00-06:00 window");
    }}
    // Late night before midnight
    if (isTimeInWindow(makeDate(23, 30), 22, 0, 6, 0) !== true) {{
      throw new Error("23:30 MUST be in 22:00-06:00 window");
    }}
    // Midnight sharp
    if (isTimeInWindow(makeDate(0, 0), 22, 0, 6, 0) !== true) {{
      throw new Error("00:00 MUST be in 22:00-06:00 window");
    }}
    // Early morning
    if (isTimeInWindow(makeDate(1, 15), 22, 0, 6, 0) !== true) {{
      throw new Error("01:15 MUST be in 22:00-06:00 window");
    }}
    // Last minute before morning end
    if (isTimeInWindow(makeDate(5, 59), 22, 0, 6, 0) !== true) {{
      throw new Error("05:59 MUST be in 22:00-06:00 window");
    }}
    // Exact morning end (exclusive)
    if (isTimeInWindow(makeDate(6, 0), 22, 0, 6, 0) !== false) {{
      throw new Error("06:00 should NOT be in 22:00-06:00 window");
    }}
    // Afternoon
    if (isTimeInWindow(makeDate(12, 0), 22, 0, 6, 0) !== false) {{
      throw new Error("12:00 should NOT be in 22:00-06:00 window");
    }}
    // Evening before start
    if (isTimeInWindow(makeDate(18, 0), 22, 0, 6, 0) !== false) {{
      throw new Error("18:00 should NOT be in 22:00-06:00 window");
    }}

    // 3. Zero-length / equal window (10:00 -> 10:00)
    if (isTimeInWindow(makeDate(10, 0), 10, 0, 10, 0) !== false) {{
      throw new Error("Equal start and end times must return false");
    }}

    console.log("IS_TIME_IN_WINDOW_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node isTimeInWindow tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "IS_TIME_IN_WINDOW_TESTS_PASSED" in res.stdout


def test_node_background_schedule_alarm_and_evaluation():
    """Execute background.js in Node.js to verify setupScheduleAlarm, alarm listener, and automated schedule transitions."""
    bg_path = SRC_DIR / "background.js"

    js_test_script = f"""
    // Mock chrome environment
    let storageState = {{}};
    let badgeState = {{ text: "", color: "" }};
    let dynamicRules = [];
    let registeredAlarms = {{}};
    let alarmListeners = [];

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
      alarms: {{
        create: (name, options) => {{
          registeredAlarms[name] = options;
        }},
        get: async (name) => registeredAlarms[name] || null,
        onAlarm: {{
          addListener: (fn) => {{
            alarmListeners.push(fn);
          }}
        }}
      }},
      runtime: {{
        onMessage: {{ addListener: () => {{}} }},
        onInstalled: {{ addListener: () => {{}} }},
        onStartup: {{ addListener: () => {{}} }}
      }}
    }};

    const {{ setupScheduleAlarm, evaluateCurrentSchedule, DEFAULT_SCHEDULE }} = await import('{bg_path.as_uri()}');

    // 1. Verify setupScheduleAlarm creates the recurring 1-minute alarm
    setupScheduleAlarm();
    if (!registeredAlarms["gtfb-schedule-check"]) {{
      throw new Error("setupScheduleAlarm did not create 'gtfb-schedule-check' alarm");
    }}
    if (registeredAlarms["gtfb-schedule-check"].periodInMinutes !== 1) {{
      throw new Error(`Expected periodInMinutes: 1, got ${{registeredAlarms["gtfb-schedule-check"].periodInMinutes}}`);
    }}

    // 2. Verify evaluateCurrentSchedule when time enters window (23:00)
    storageState.isBlockingActive = false;
    dynamicRules = [];
    badgeState = {{ text: "", color: "" }};

    const bedtime = new Date(2026, 7, 29, 23, 0, 0); // 23:00
    await evaluateCurrentSchedule(bedtime);

    if (storageState.isBlockingActive !== true) {{
      throw new Error("isBlockingActive should be true when entering bedtime schedule window");
    }}
    if (badgeState.text !== "ON") {{
      throw new Error(`Expected badge text 'ON', got '${{badgeState.text}}'`);
    }}
    if (dynamicRules.length === 0) {{
      throw new Error("Dynamic rules should be applied when entering schedule window");
    }}

    // 3. Verify evaluateCurrentSchedule when time leaves window (08:00 next morning)
    const morning = new Date(2026, 7, 30, 8, 0, 0); // 08:00
    await evaluateCurrentSchedule(morning);

    if (storageState.isBlockingActive !== false) {{
      throw new Error("isBlockingActive should be false when leaving bedtime schedule window");
    }}
    if (badgeState.text !== "") {{
      throw new Error(`Expected badge text '', got '${{badgeState.text}}'`);
    }}
    if (dynamicRules.length !== 0) {{
      throw new Error("Dynamic rules should be cleared when leaving schedule window");
    }}

    // 4. Verify Focus Lock safety: When locked, schedule check outside window does NOT disengage blocking
    storageState.isBlockingActive = true;
    storageState.lockedUntil = Date.now() + 15 * 60 * 1000; // 15 min lock
    badgeState.text = "LOCK";

    await evaluateCurrentSchedule(morning); // 08:00 (outside window)
    if (storageState.isBlockingActive !== true) {{
      throw new Error("Schedule check MUST NOT disable blocking while focus lock is active!");
    }}
    if (badgeState.text !== "LOCK") {{
      throw new Error("Badge text should remain 'LOCK' while focus lock is active!");
    }}

    // 5. Test Alarm Listener dispatch
    let alarmDispatched = false;
    for (const listener of alarmListeners) {{
      await listener({{ name: "gtfb-schedule-check" }});
      alarmDispatched = true;
    }}
    if (!alarmDispatched) {{
      throw new Error("Alarm listener was not registered or invoked");
    }}

    console.log("BACKGROUND_SCHEDULE_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node background schedule tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "BACKGROUND_SCHEDULE_TESTS_PASSED" in res.stdout
