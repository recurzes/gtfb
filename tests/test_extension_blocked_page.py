"""Tests for Blocked Landing Page (feat/ext-blocked-page)."""

import json
from pathlib import Path
import subprocess
import pytest

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"
SRC_DIR = EXTENSION_DIR / "src"


def test_blocked_page_files_exist():
    """Verify blocked.html, blocked.css, and blocked.js exist."""
    blocked_html = SRC_DIR / "blocked.html"
    blocked_css = SRC_DIR / "blocked.css"
    blocked_js = SRC_DIR / "blocked.js"

    assert blocked_html.is_file(), "blocked.html must exist in extension/src/"
    assert blocked_css.is_file(), "blocked.css must exist in extension/src/"
    assert blocked_js.is_file(), "blocked.js must exist in extension/src/"


def test_blocked_html_structure_and_elements():
    """Verify blocked.html has correct semantics, asset links, and essential IDs."""
    html_path = SRC_DIR / "blocked.html"
    content = html_path.read_text(encoding="utf-8")

    assert "<!DOCTYPE html>" in content
    assert "<html" in content.lower()
    assert "<title>Blocked — GTFB</title>" in content
    assert 'href="blocked.css"' in content
    assert 'src="blocked.js"' in content

    # Check key UI elements and identifiers
    assert 'id="domainBadge"' in content
    assert 'id="closeTabBtn"' in content
    assert "Distraction Blocked" in content
    assert "This website is currently restricted by GTFB" in content
    assert "Protect your sleep and your focus" in content
    assert "Close This Tab" in content
    assert "<svg" in content
    assert "shield-icon" in content


def test_blocked_page_no_bypass_mechanisms():
    """Verify zero snooze, bypass, unblock, or override controls exist on the blocked page."""
    html_content = (SRC_DIR / "blocked.html").read_text(encoding="utf-8").lower()
    js_content = (SRC_DIR / "blocked.js").read_text(encoding="utf-8").lower()

    prohibited_terms = ["snooze", "bypass", "unblock", "whitelist", "5 more minutes", "disable"]
    for term in prohibited_terms:
        assert term not in html_content, f"Found prohibited bypass term '{term}' in blocked.html"
        assert term not in js_content, f"Found prohibited bypass term '{term}' in blocked.js"


def test_blocked_css_design_system():
    """Verify blocked.css contains dark-mode design tokens and required component classes."""
    css_path = SRC_DIR / "blocked.css"
    content = css_path.read_text(encoding="utf-8")

    # Tokens
    assert "--bg-primary" in content
    assert "--bg-card" in content
    assert "--accent-red" in content

    # Components
    assert ".card" in content
    assert ".icon-container" in content
    assert ".shield-icon" in content
    assert ".domain-badge" in content
    assert ".btn.primary" in content
    assert ":hover" in content


def test_node_blocked_page_script_behavior():
    """Execute blocked.js via Node.js in a mock DOM environment to verify query param handling and close button."""
    js_path = SRC_DIR / "blocked.js"
    js_file_url = js_path.as_uri()

    js_test_script = f"""
    import fs from 'fs';

    const scriptCode = fs.readFileSync('{js_path.as_posix()}', 'utf-8');

    function createMockDOM(queryString) {{
      const listeners = {{}};
      let closed = false;

      const badge = {{
        id: 'domainBadge',
        textContent: 'Domain Protected'
      }};

      const closeBtn = {{
        id: 'closeTabBtn',
        listeners: {{}},
        addEventListener(event, fn) {{
          this.listeners[event] = fn;
        }},
        click() {{
          if (this.listeners['click']) this.listeners['click']();
        }}
      }};

      const elements = {{
        'domainBadge': badge,
        'closeTabBtn': closeBtn
      }};

      const mockDocument = {{
        readyState: 'loading',
        addEventListener(event, fn) {{
          listeners[event] = fn;
        }},
        getElementById(id) {{
          return elements[id] || null;
        }}
      }};

      const mockWindow = {{
        location: {{ search: queryString }},
        close() {{
          closed = true;
        }}
      }};

      // Execute script in mock context
      const fn = new Function('document', 'window', 'URLSearchParams', scriptCode);
      fn(mockDocument, mockWindow, URLSearchParams);

      // Trigger DOMContentLoaded
      if (listeners['DOMContentLoaded']) {{
        listeners['DOMContentLoaded']();
      }}

      return {{ badge, closeBtn, isClosed: () => closed }};
    }}

    // Case 1: Query param provided
    const test1 = createMockDOM('?domain=reddit.com');
    if (test1.badge.textContent !== 'reddit.com') {{
      throw new Error(`Expected badge to be reddit.com, got: ${{test1.badge.textContent}}`);
    }}
    test1.closeBtn.click();
    if (!test1.isClosed()) {{
      throw new Error("Close button did not call window.close()");
    }}

    // Case 2: No query param
    const test2 = createMockDOM('');
    if (test2.badge.textContent !== 'Domain Protected') {{
      throw new Error(`Expected badge to remain 'Domain Protected', got: ${{test2.badge.textContent}}`);
    }}

    // Case 3: Empty domain query param
    const test3 = createMockDOM('?domain=  ');
    if (test3.badge.textContent !== 'Domain Protected') {{
      throw new Error(`Expected badge to remain 'Domain Protected' for whitespace domain, got: ${{test3.badge.textContent}}`);
    }}

    console.log("BLOCKED_PAGE_JS_TESTS_PASSED");
    """

    res = subprocess.run(
        ["node", "--input-type=module", "-e", js_test_script],
        capture_output=True,
        text=True,
        check=False
    )

    assert res.returncode == 0, f"Node tests failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}"
    assert "BLOCKED_PAGE_JS_TESTS_PASSED" in res.stdout
