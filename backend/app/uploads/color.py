"""HSV histogram-based ink-color → family member matcher (Phase 4 Task F).

Strategy
--------
1. Decode the cell-crop image.
2. Convert RGB → HSV (OpenCV H ∈ [0, 179]).
3. Mask out "paper" pixels — bright (V > value_threshold) AND low-saturation
   (S < saturation_threshold) pixels are discarded.
4. Compute a 180-bin hue histogram on the remaining ink pixels.
5. Apply circular Gaussian smoothing so hues near bin 0 and 179 (both "red"
   in OpenCV's scale) are handled correctly.
6. Find the dominant hue (histogram peak) and convert back to CSS degrees
   (multiply by 2 to go from 0-179 to 0-358).
7. Match the dominant hue against each FamilyMemberLike's [hue_range_low,
   hue_range_high] — including Danielle's wrap-around range [350, 20].
8. Return the best ColorMatch (highest confidence), or None if the cell
   contains no detectable ink.

Known limitation: if two family members have written in the same cell (e.g.,
Bryant in blue AND Danielle in red), the histogram-peak approach picks only
the *dominant* color. The pipeline (Task G) documents this.

This module uses no new dependencies — only opencv-python-headless, numpy,
and Pillow (already required by Tasks D and E).
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol — allows unit tests to pass SimpleNamespace without importing
# SQLAlchemy models, while the real pipeline passes FamilyMember rows.
# ---------------------------------------------------------------------------


class _FamilyMemberLike(Protocol):
    id: int
    name: str
    color_hex_center: str
    hue_range_low: int
    hue_range_high: int


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColorMatch:
    """Result of a single color-matching operation."""

    family_member_id: int
    """The FamilyMember.id of the best match."""
    family_member_name: str
    """Human-readable name — for diagnostics and logging."""
    color_hex: str
    """The family member's canonical color_hex_center."""
    confidence: float
    """Confidence in [0, 1]; distance-to-center based."""
    detected_hue_deg: float
    """Dominant hue actually detected, in CSS/standard degrees [0, 358]."""


# ---------------------------------------------------------------------------
# Public synchronous entry point
# ---------------------------------------------------------------------------


def match_ink_color(
    image_bytes: bytes,
    family_members: Sequence[_FamilyMemberLike],
    *,
    value_threshold: int = 200,
    saturation_threshold: int = 30,
) -> ColorMatch | None:
    """Identify which family member wrote in this cell by ink-color analysis.

    Args:
        image_bytes: JPEG/PNG bytes of a cell crop.
        family_members: FamilyMember-like rows to match against.  Duck-typed
            via ``_FamilyMemberLike`` — both SQLAlchemy models and plain
            ``SimpleNamespace`` objects work.
        value_threshold: HSV V threshold (0-255).  Pixels *above* this are
            considered white paper and excluded from analysis.
        saturation_threshold: HSV S threshold (0-255).  Pixels *below* this
            are considered grey/black/achromatic and excluded.

    Returns:
        The best ``ColorMatch``, or ``None`` if the cell has no detectable
        saturated ink (empty, all-white, or all-grey).

    Note:
        Mixed-ink cells (two family members' writing in the same crop) will
        be attributed to the *dominant* color.  This is a known limitation;
        Phase 5+ may address it with additional heuristics.
    """
    if not family_members:
        return None

    # --- 1. Load image -------------------------------------------------------
    try:
        pil_image: Image.Image = Image.open(io.BytesIO(image_bytes))
        pil_image.load()
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        array = np.array(pil_image, dtype=np.uint8)
    except Exception:
        logger.warning("color_match: failed to decode image — returning None")
        return None

    # --- 2. Convert RGB → HSV ------------------------------------------------
    # cv2 expects BGR; we pass the RGB array directly and use the RGB→HSV
    # conversion code instead.
    try:
        hsv = cv2.cvtColor(array, cv2.COLOR_RGB2HSV)
    except Exception:
        logger.warning("color_match: cvtColor failed — returning None")
        return None

    h_channel, s_channel, _v_channel = cv2.split(hsv)

    # --- 3. Build ink mask ---------------------------------------------------
    # Identify "ink-like" pixels: those with enough saturation to carry a
    # meaningful hue.  White paper (S ≈ 0) and grey pencil marks (S < threshold)
    # are filtered out.  Pale ink colours like pink (#E17AA1, S≈117) and
    # orange (#D97A2C, S≈203) have sufficient saturation to pass this filter
    # even though their brightness (V) is high — so we intentionally do NOT
    # apply a V upper-bound here.
    #
    # The value_threshold parameter is still accepted for API compatibility and
    # future use (e.g., filtering dark smudges on coloured paper), but the
    # primary gate is saturation.
    ink_mask: np.ndarray = s_channel >= saturation_threshold

    if int(ink_mask.sum()) < 20:
        # Fewer than 20 qualifying pixels — treat as empty cell.
        return None

    # --- 4. Hue histogram ----------------------------------------------------
    hue_pixels = h_channel[ink_mask]
    hist = np.bincount(hue_pixels.astype(np.int64), minlength=180)

    if int(hist.sum()) == 0:
        return None

    # --- 5. Circular smoothing + peak detection ------------------------------
    smoothed = _smooth_circular(hist, sigma=2)
    peak_h_opencv = int(np.argmax(smoothed))

    # OpenCV H ∈ [0, 179] → CSS degrees ∈ [0, 358]
    detected_hue_deg = float(peak_h_opencv * 2)

    # --- 6. Match against each family member ---------------------------------
    best_match: ColorMatch | None = None
    best_confidence = -1.0

    for fm in family_members:
        confidence = _confidence_for_hue(
            detected_hue_deg, fm.hue_range_low, fm.hue_range_high
        )
        if confidence > best_confidence:
            best_confidence = confidence
            best_match = ColorMatch(
                family_member_id=fm.id,
                family_member_name=fm.name,
                color_hex=fm.color_hex_center,
                confidence=confidence,
                detected_hue_deg=detected_hue_deg,
            )

    if best_match is None or best_match.confidence <= 0.0:
        return None

    return best_match


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _smooth_circular(hist: np.ndarray, sigma: int = 2) -> np.ndarray:
    """Apply wrap-around Gaussian smoothing to a 1D histogram.

    Hue histograms are circular: bin 0 and bin 179 are both "red" in
    OpenCV's H scale.  Tripling the array, smoothing, then taking the middle
    third handles the wrap correctly.
    """
    n = len(hist)
    tripled = np.concatenate([hist, hist, hist]).astype(float)
    kernel_size = max(3, (sigma * 6) | 1)  # ensure odd
    kernel = cv2.getGaussianKernel(kernel_size, sigma)
    smoothed_3x: np.ndarray = cv2.filter2D(
        tripled.reshape(-1, 1), -1, kernel
    ).reshape(-1)
    return smoothed_3x[n : 2 * n]


def _confidence_for_hue(
    hue_deg: float,
    range_low_deg: int,
    range_high_deg: int,
) -> float:
    """Compute confidence that *hue_deg* belongs to the given hue range.

    Returns 1.0 at the range center, decreasing linearly to 0.0 at 90°
    distance.  Hues actually *inside* the range get a floor of 0.7.

    Handles wrap-around: if ``range_low > range_high`` (e.g., Danielle's
    ``[350, 20]``), the range covers ``[350, 359] U [0, 20]``.

    Args:
        hue_deg: Detected dominant hue in CSS/standard degrees [0, 358].
        range_low_deg: Lower bound of the family member's hue band (0-359).
        range_high_deg: Upper bound of the family member's hue band (0-359).

    Returns:
        Confidence in [0.0, 1.0].
    """
    if range_low_deg <= range_high_deg:
        # Normal (non-wrapping) range.
        center = (range_low_deg + range_high_deg) / 2.0
        in_range = range_low_deg <= hue_deg <= range_high_deg
    else:
        # Wrap-around case, e.g., [350, 20].
        # Center: midpoint of the arc [350, 360+20] = (350 + 380) / 2 = 365 → 5°
        center = ((range_low_deg + range_high_deg + 360) / 2.0) % 360.0
        in_range = hue_deg >= range_low_deg or hue_deg <= range_high_deg

    # Circular distance to center (max 180).
    diff = abs(hue_deg - center)
    distance = min(diff, 360.0 - diff)

    confidence = 1.0 - (distance / 90.0)

    # Floor: if the hue is geometrically inside the range, bump up to 0.7.
    if in_range:
        confidence = max(confidence, 0.7)

    return float(max(0.0, min(1.0, confidence)))


# ---------------------------------------------------------------------------
# Public async wrapper
# ---------------------------------------------------------------------------


async def match_ink_color_async(
    image_bytes: bytes,
    family_members: Sequence[_FamilyMemberLike],
    **kwargs: int,
) -> ColorMatch | None:
    """Async wrapper around :func:`match_ink_color`.

    Phase 4 Task G calls this from the pipeline.  Runs the synchronous
    OpenCV work in a thread pool via ``asyncio.to_thread``.
    """
    return await asyncio.to_thread(
        match_ink_color, image_bytes, family_members, **kwargs
    )
