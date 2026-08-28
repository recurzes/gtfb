"""Tests for GTFB icon generation and state-based asset loading."""

from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image

from gtfb.core.scheduler import SchedulerState
from gtfb.ui.icons import (
    STATE_COLORS,
    create_state_icon,
    generate_fallback_icon,
    get_icon,
    load_tray_icon,
)


class TestIconGeneration(unittest.TestCase):
    """Test dynamic icon rendering and color mappings."""

    def test_state_colors_defined(self):
        self.assertIn("STOPPED", STATE_COLORS)
        self.assertIn("COUNTING_DOWN", STATE_COLORS)
        self.assertIn("ENFORCING", STATE_COLORS)

    def test_create_state_icon_stopped(self):
        img = create_state_icon("STOPPED", 64, 64)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, "RGBA")

    def test_create_state_icon_counting_down(self):
        img = create_state_icon("COUNTING_DOWN", 32, 32)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (32, 32))
        self.assertEqual(img.mode, "RGBA")

    def test_create_state_icon_enforcing(self):
        img = create_state_icon(SchedulerState.ENFORCING, 64, 64)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, "RGBA")

    def test_get_icon_with_enum_and_str(self):
        img_enum = get_icon(SchedulerState.COUNTING_DOWN)
        img_str = get_icon("COUNTING_DOWN")
        self.assertIsInstance(img_enum, Image.Image)
        self.assertIsInstance(img_str, Image.Image)

    def test_get_icon_with_existing_asset(self):
        asset_path = Path(__file__).resolve().parent.parent / "src" / "gtfb" / "assets" / "icon.png"
        img = get_icon("STOPPED", icon_path=asset_path)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.mode, "RGBA")

    def test_get_icon_with_nonexistent_custom_path_falls_back(self):
        img = get_icon("STOPPED", icon_path="nonexistent_folder/fake_icon.png")
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.mode, "RGBA")

    def test_legacy_generate_fallback_icon(self):
        img = generate_fallback_icon(64, 64)
        self.assertIsInstance(img, Image.Image)
        self.assertEqual(img.size, (64, 64))

    def test_legacy_load_tray_icon(self):
        img = load_tray_icon()
        self.assertIsInstance(img, Image.Image)


if __name__ == "__main__":
    unittest.main()
