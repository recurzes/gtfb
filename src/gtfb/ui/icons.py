"""Icon generator and asset loading utilities for GTFB system tray."""

from enum import Enum
import logging
from pathlib import Path
from typing import Optional, Union

from PIL import Image, ImageDraw

logger = logging.getLogger("gtfb.ui.icons")

STATE_COLORS = {
    "STOPPED": "#808080",       # Neutral / Gray
    "COUNTING_DOWN": "#22C55E", # Green (Armed)
    "ENFORCING": "#EF4444",     # Red (Enforcing bedtime)
}


def create_state_icon(
    state: Union[str, Enum] = "STOPPED",
    width: int = 64,
    height: int = 64,
) -> Image.Image:
    """Generate a dynamic RGBA tray icon image corresponding to a scheduler state.

    Args:
        state: The current state string or Enum ('STOPPED', 'COUNTING_DOWN', 'ENFORCING').
        width: Pixel width of the generated icon.
        height: Pixel height of the generated icon.

    Returns:
        PIL.Image.Image: Formatted RGBA icon.
    """
    state_key = state.value if isinstance(state, Enum) else str(state).upper()
    fill_color = STATE_COLORS.get(state_key, "#3B82F6")

    img = Image.new("RGBA", (width, height), color=(0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer badge circle
    margin = max(4, int(width * 0.08))
    draw.ellipse([(margin, margin), (width - margin, height - margin)], fill=fill_color)

    # Inner contrast shape (crescent moon / emblem in white)
    # Center coordinates
    cx, cy = width / 2, height / 2
    r = (width - 2 * margin) / 2

    # Draw crisp inner emblem
    if state_key == "STOPPED":
        # Neutral pause / bed bar
        bar_w = max(4, int(r * 0.35))
        bar_h = max(12, int(r * 1.1))
        gap = max(4, int(r * 0.25))
        x1 = int(cx - gap / 2 - bar_w)
        x2 = int(cx + gap / 2)
        y1 = int(cy - bar_h / 2)
        y2 = int(cy + bar_h / 2)
        draw.rectangle([(x1, y1), (x1 + bar_w, y2)], fill="#FFFFFF")
        draw.rectangle([(x2, y1), (x2 + bar_w, y2)], fill="#FFFFFF")
    elif state_key == "ENFORCING":
        # Alert exclamation / enforcement badge
        bar_w = max(4, int(r * 0.3))
        bar_h = max(10, int(r * 0.8))
        dot_r = max(2, int(r * 0.18))
        draw.rectangle(
            [(int(cx - bar_w / 2), int(cy - r * 0.6)), (int(cx + bar_w / 2), int(cy + r * 0.2))],
            fill="#FFFFFF",
        )
        draw.ellipse(
            [(int(cx - dot_r), int(cy + r * 0.45)), (int(cx + dot_r), int(cy + r * 0.45 + 2 * dot_r))],
            fill="#FFFFFF",
        )
    else:
        # Crescent moon for active / counting down
        moon_r = int(r * 0.65)
        draw.ellipse(
            [(int(cx - moon_r), int(cy - moon_r)), (int(cx + moon_r), int(cy + moon_r))],
            fill="#FFFFFF",
        )
        cut_r = int(r * 0.55)
        offset_x = int(r * 0.35)
        offset_y = int(r * 0.2)
        draw.ellipse(
            [(int(cx - cut_r + offset_x), int(cy - cut_r - offset_y)), (int(cx + cut_r + offset_x), int(cy + cut_r - offset_y))],
            fill=fill_color,
        )

    return img


def get_icon(
    state: Union[str, Enum] = "STOPPED",
    icon_path: Optional[Union[Path, str]] = None,
    width: int = 64,
    height: int = 64,
) -> Image.Image:
    """Retrieve an icon asset for the given state, falling back to dynamic rendering.

    Args:
        state: State name or Enum ('STOPPED', 'COUNTING_DOWN', 'ENFORCING').
        icon_path: Optional explicit file path to an icon.
        width: Fallback width.
        height: Fallback height.

    Returns:
        PIL.Image.Image: Loaded or generated RGBA icon.
    """
    state_key = state.value if isinstance(state, Enum) else str(state).lower()
    candidates = []

    if icon_path:
        candidates.append(Path(icon_path))

    # State-specific icon assets
    candidates.append(Path(__file__).resolve().parent.parent / "assets" / "icons" / f"{state_key}.png")
    candidates.append(Path("assets/icons") / f"{state_key}.png")

    for path in candidates:
        try:
            if path.is_file():
                return Image.open(path).convert("RGBA")
        except Exception as err:
            logger.warning("Failed loading icon from %s: %s", path, err)

    return create_state_icon(state, width=width, height=height)


def generate_fallback_icon(width: int = 64, height: int = 64) -> Image.Image:
    """Legacy helper: generate dynamic fallback RGBA tray icon image."""
    return create_state_icon("COUNTING_DOWN", width=width, height=height)


def load_tray_icon(icon_path: Optional[Union[Path, str]] = None) -> Image.Image:
    """Legacy helper: load icon asset or generate dynamic fallback."""
    candidates = []
    if icon_path:
        candidates.append(Path(icon_path))

    candidates.append(Path(__file__).resolve().parent.parent / "assets" / "icon.png")
    candidates.append(Path("assets/icons/icon.png"))
    candidates.append(Path("assets/icon.png"))

    for path in candidates:
        try:
            if path.is_file():
                return Image.open(path).convert("RGBA")
        except Exception as err:
            logger.warning("Failed loading icon from %s: %s", path, err)

    return generate_fallback_icon()
