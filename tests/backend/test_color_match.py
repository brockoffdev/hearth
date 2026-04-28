"""Tests for HSV ink-color → family member matching (Phase 4 Task F).

Synthetic images are built with Pillow so no real photo fixtures are needed.
"""

from __future__ import annotations

import asyncio
import io
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.app.uploads.color import (
    ColorMatch,
    _confidence_for_hue,
    _smooth_circular,
    match_ink_color,
    match_ink_color_async,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_color_swatch(hex_color: str, size: tuple[int, int] = (100, 100)) -> bytes:
    """Make a solid-color image of the given hex color."""
    image = Image.new("RGB", size, color=hex_color)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _make_white_image(size: tuple[int, int] = (100, 100)) -> bytes:
    return _make_color_swatch("#FFFFFF", size)


def _make_ink_on_paper(
    ink_hex: str,
    paper_hex: str = "#FFFFFF",
    ink_pixels: int = 200,
    size: tuple[int, int] = (100, 100),
) -> bytes:
    """Paper background + a stroke of N ink-colored pixels."""
    image = Image.new("RGB", size, color=paper_hex)
    draw = ImageDraw.Draw(image)
    width, height = size
    stroke_width = max(2, int(np.sqrt(ink_pixels)))
    draw.line(
        [(10, height // 2), (width - 10, height // 2)],
        fill=ink_hex,
        width=stroke_width,
    )
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _make_family_members() -> list[Any]:
    """Lightweight mocks matching the seed migration data."""
    return [
        SimpleNamespace(
            id=1, name="Bryant", color_hex_center="#2E5BA8",
            hue_range_low=200, hue_range_high=230,
        ),
        SimpleNamespace(
            id=2, name="Danielle", color_hex_center="#C0392B",
            hue_range_low=350, hue_range_high=20,
        ),
        SimpleNamespace(
            id=3, name="Izzy", color_hex_center="#7B4FB8",
            hue_range_low=253, hue_range_high=283,
        ),
        SimpleNamespace(
            id=4, name="Ellie", color_hex_center="#E17AA1",
            hue_range_low=320, hue_range_high=350,
        ),
        SimpleNamespace(
            id=5, name="Family", color_hex_center="#D97A2C",
            hue_range_low=11, hue_range_high=41,
        ),
    ]


# ---------------------------------------------------------------------------
# Full-color swatch tests — one per family member
# ---------------------------------------------------------------------------


def test_match_ink_color_blue_returns_bryant() -> None:
    image_bytes = _make_color_swatch("#2E5BA8")
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is not None
    assert result.family_member_name == "Bryant"
    assert result.confidence > 0.5


def test_match_ink_color_red_returns_danielle() -> None:
    image_bytes = _make_color_swatch("#C0392B")
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is not None
    assert result.family_member_name == "Danielle"
    assert result.confidence > 0.5


def test_match_ink_color_purple_returns_izzy() -> None:
    image_bytes = _make_color_swatch("#7B4FB8")
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is not None
    assert result.family_member_name == "Izzy"
    assert result.confidence > 0.5


def test_match_ink_color_pink_returns_ellie() -> None:
    image_bytes = _make_color_swatch("#E17AA1")
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is not None
    assert result.family_member_name == "Ellie"
    assert result.confidence > 0.5


def test_match_ink_color_orange_returns_family() -> None:
    image_bytes = _make_color_swatch("#D97A2C")
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is not None
    assert result.family_member_name == "Family"
    assert result.confidence > 0.5


# ---------------------------------------------------------------------------
# Ink-on-paper stroke tests
# ---------------------------------------------------------------------------


def test_match_blue_ink_on_paper_returns_bryant() -> None:
    image_bytes = _make_ink_on_paper("#2E5BA8")
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is not None
    assert result.family_member_name == "Bryant"


def test_match_red_ink_on_paper_returns_danielle() -> None:
    image_bytes = _make_ink_on_paper("#C0392B")
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is not None
    assert result.family_member_name == "Danielle"


# ---------------------------------------------------------------------------
# Empty / grey cell edge cases
# ---------------------------------------------------------------------------


def test_match_empty_cell_returns_none() -> None:
    image_bytes = _make_white_image()
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is None


def test_match_grey_only_returns_none() -> None:
    # #888888 has low saturation — should be filtered out
    image_bytes = _make_color_swatch("#888888")
    result = match_ink_color(image_bytes, _make_family_members())
    assert result is None


# ---------------------------------------------------------------------------
# Wrap-around hue tests (Danielle [350, 20])
# ---------------------------------------------------------------------------


def test_match_red_at_hue_5_matches_danielle() -> None:
    """Hue 5° (near 0 from above) should still land on Danielle."""
    # HSS 5°, S=200, V=150 → a saturated dark-red
    # Build image from HSV: H=5/2=2 in OpenCV, S=200, V=150
    import cv2
    hsv_patch = np.full((50, 50, 3), [2, 200, 150], dtype=np.uint8)
    rgb_patch = cv2.cvtColor(hsv_patch, cv2.COLOR_HSV2RGB)
    image = Image.fromarray(rgb_patch, "RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    result = match_ink_color(buf.getvalue(), _make_family_members())
    assert result is not None
    assert result.family_member_name == "Danielle"


def test_match_red_at_hue_355_matches_danielle() -> None:
    """Hue 355° (near 0 from below) should also land on Danielle."""
    import cv2
    # OpenCV H for 355° = 177 (355//2)
    hsv_patch = np.full((50, 50, 3), [177, 200, 150], dtype=np.uint8)
    rgb_patch = cv2.cvtColor(hsv_patch, cv2.COLOR_HSV2RGB)
    image = Image.fromarray(rgb_patch, "RGB")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    result = match_ink_color(buf.getvalue(), _make_family_members())
    assert result is not None
    assert result.family_member_name == "Danielle"


# ---------------------------------------------------------------------------
# Robustness / error handling
# ---------------------------------------------------------------------------


def test_match_handles_corrupt_input_returns_none() -> None:
    result = match_ink_color(b"not an image", _make_family_members())
    assert result is None


def test_match_handles_empty_family_list_returns_none() -> None:
    image_bytes = _make_color_swatch("#2E5BA8")
    result = match_ink_color(image_bytes, [])
    assert result is None


def test_match_handles_empty_bytes_returns_none() -> None:
    result = match_ink_color(b"", _make_family_members())
    assert result is None


# ---------------------------------------------------------------------------
# ColorMatch dataclass
# ---------------------------------------------------------------------------


def test_color_match_is_frozen() -> None:
    cm = ColorMatch(
        family_member_id=1,
        family_member_name="Bryant",
        color_hex="#2E5BA8",
        confidence=0.9,
        detected_hue_deg=215.0,
    )
    with pytest.raises(FrozenInstanceError):
        cm.confidence = 0.5  # type: ignore[misc]


def test_color_match_fields_exposed() -> None:
    cm = ColorMatch(
        family_member_id=2,
        family_member_name="Danielle",
        color_hex="#C0392B",
        confidence=0.8,
        detected_hue_deg=5.0,
    )
    assert cm.family_member_id == 2
    assert cm.family_member_name == "Danielle"
    assert cm.detected_hue_deg == 5.0


# ---------------------------------------------------------------------------
# _confidence_for_hue unit tests
# ---------------------------------------------------------------------------


def test_confidence_for_hue_at_center_is_high() -> None:
    # Bryant range [200, 230], center = 215
    conf = _confidence_for_hue(215.0, 200, 230)
    assert conf >= 0.9


def test_confidence_for_hue_at_edge_is_lower() -> None:
    # Bryant range [200, 230], edge at 200 → distance from center (215) = 15
    conf = _confidence_for_hue(200.0, 200, 230)
    assert conf < 1.0
    assert conf >= 0.7  # still in-range, gets the floor


def test_confidence_for_hue_far_from_range_is_low() -> None:
    # Bryant range [200, 230], hue at 90° distance from center (215) → ~305 or ~125
    conf = _confidence_for_hue(305.0, 200, 230)
    # distance = |305 - 215| = 90 → confidence = 1 - 90/90 = 0.0
    assert conf <= 0.1


def test_confidence_for_hue_in_wrap_range() -> None:
    # Danielle [350, 20], hue 5° → in_range=True → confidence ≥ 0.7
    conf = _confidence_for_hue(5.0, 350, 20)
    assert conf >= 0.7


def test_confidence_for_hue_wrap_center_calculation() -> None:
    # Danielle [350, 20]: center = (350 + 20 + 360) / 2 % 360 = 365 % 360 = 5
    conf_at_center = _confidence_for_hue(5.0, 350, 20)
    conf_at_edge = _confidence_for_hue(350.0, 350, 20)
    assert conf_at_center >= conf_at_edge


def test_confidence_for_hue_outside_wrap_range_is_lower() -> None:
    # Danielle [350, 20]: hue 180° is far away → low confidence
    conf = _confidence_for_hue(180.0, 350, 20)
    assert conf <= 0.1


def test_confidence_clamped_to_zero_not_negative() -> None:
    # 180° away from any center → should be 0.0
    conf = _confidence_for_hue(100.0, 200, 230)
    assert conf >= 0.0


# ---------------------------------------------------------------------------
# _smooth_circular unit tests
# ---------------------------------------------------------------------------


def test_smooth_circular_output_shape() -> None:
    hist = np.zeros(180, dtype=np.int64)
    hist[10] = 100
    smoothed = _smooth_circular(hist, sigma=2)
    assert smoothed.shape == (180,)


def test_smooth_circular_wraps_around() -> None:
    """Histogram with peaks at bins 0 and 179 (both 'red') should be merged by smoothing."""
    hist = np.zeros(180, dtype=np.int64)
    hist[0] = 100
    hist[179] = 100
    smoothed = _smooth_circular(hist, sigma=3)
    # Both ends should have significant values after wrap-around smoothing
    assert smoothed[0] > 0
    assert smoothed[179] > 0
    # Values at both ends should be similar (symmetric peaks)
    assert abs(float(smoothed[0]) - float(smoothed[179])) < float(smoothed[0]) * 0.5


def test_smooth_circular_peak_preserved() -> None:
    hist = np.zeros(180, dtype=np.int64)
    hist[90] = 500  # strong peak in the middle
    smoothed = _smooth_circular(hist, sigma=2)
    # The peak should remain near bin 90
    assert int(np.argmax(smoothed)) == 90


def test_smooth_circular_uniform_stays_uniform() -> None:
    hist = np.ones(180, dtype=np.int64) * 10
    smoothed = _smooth_circular(hist, sigma=2)
    # All values should be approximately equal after smoothing a uniform histogram
    assert np.std(smoothed) < 1.0


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------


def test_match_ink_color_async_blue_returns_bryant() -> None:
    image_bytes = _make_color_swatch("#2E5BA8")
    result = asyncio.run(match_ink_color_async(image_bytes, _make_family_members()))
    assert result is not None
    assert result.family_member_name == "Bryant"
