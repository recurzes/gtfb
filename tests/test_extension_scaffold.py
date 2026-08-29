"""Tests for Manifest V3 Browser Extension Scaffold."""

import json
from pathlib import Path
import pytest
from PIL import Image

EXTENSION_DIR = Path(__file__).resolve().parent.parent / "extension"


def test_manifest_file_exists():
    """Verify that manifest.json exists in the extension directory."""
    manifest_path = EXTENSION_DIR / "manifest.json"
    assert manifest_path.is_file(), "manifest.json must exist in extension directory"


def test_manifest_structure_and_mv3():
    """Verify that manifest.json conforms to Manifest V3 schema and required permissions."""
    manifest_path = EXTENSION_DIR / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest.get("manifest_version") == 3
    assert manifest.get("name") == "GTFB — Anti-Distraction Suite"
    assert manifest.get("version") == "1.0.0"
    assert "description" in manifest

    # Permissions
    expected_permissions = {"declarativeNetRequest", "storage", "alarms"}
    assert expected_permissions.issubset(set(manifest.get("permissions", [])))

    # Host permissions
    assert "*://*/*" in manifest.get("host_permissions", [])

    # Background service worker
    background = manifest.get("background", {})
    assert "service_worker" in background
    sw_path = EXTENSION_DIR / background["service_worker"]
    assert sw_path.is_file(), f"Service worker not found at {sw_path}"

    # Action popup and icons
    action = manifest.get("action", {})
    assert "default_popup" in action
    popup_path = EXTENSION_DIR / action["default_popup"]
    assert popup_path.is_file(), f"Popup HTML not found at {popup_path}"

    # Action and extension icons
    for icon_dict_key in ["action", "icons"]:
        icon_dict = manifest.get(icon_dict_key, {})
        if icon_dict_key == "action":
            icon_dict = icon_dict.get("default_icon", {})

        for size_str in ["16", "48", "128"]:
            assert size_str in icon_dict, f"Missing icon size {size_str} in {icon_dict_key}"
            icon_file = EXTENSION_DIR / icon_dict[size_str]
            assert icon_file.is_file(), f"Icon file missing at {icon_file}"


@pytest.mark.parametrize("size", [16, 48, 128])
def test_extension_icons(size):
    """Verify that icon PNG assets exist and have expected dimensions."""
    icon_path = EXTENSION_DIR / "icons" / f"icon{size}.png"
    assert icon_path.is_file(), f"Icon {icon_path.name} does not exist"

    with Image.open(icon_path) as img:
        assert img.format == "PNG"
        assert img.size == (size, size)
        assert img.mode == "RGBA"


def test_background_service_worker_content():
    """Verify background.js contains lifecycle event listener."""
    bg_path = EXTENSION_DIR / "src" / "background.js"
    assert bg_path.is_file()
    content = bg_path.read_text(encoding="utf-8")
    assert "chrome.runtime.onInstalled.addListener" in content
    assert "GTFB Background" in content


def test_popup_ui_files():
    """Verify popup.html, popup.css, and popup.js exist and are properly linked."""
    popup_html = EXTENSION_DIR / "src" / "popup.html"
    popup_css = EXTENSION_DIR / "src" / "popup.css"
    popup_js = EXTENSION_DIR / "src" / "popup.js"

    assert popup_html.is_file()
    assert popup_css.is_file()
    assert popup_js.is_file()

    html_content = popup_html.read_text(encoding="utf-8")
    assert "popup.css" in html_content
    assert "popup.js" in html_content
    assert "GTFB" in html_content
