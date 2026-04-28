"""Image preprocessing pipeline for Hearth upload photos (Phase 4 Task D).

Exports one async entry point:
    preprocess_photo(image_bytes, *, target_long_edge_px=2048) -> bytes

Four pure helpers (testable in isolation):
    _exif_rotate     — EXIF orientation correction via Pillow
    _downscale       — Fit long edge to target_long_edge_px
    _deskew          — Hough-transform dominant-line deskew via OpenCV
    _perspective_correct — Four-point perspective warp via OpenCV
"""

from __future__ import annotations

import asyncio
import io
import logging

import cv2
import numpy as np
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def _exif_rotate(image: Image.Image) -> Image.Image:
    """Apply EXIF orientation correction so the image is physically upright.

    Args:
        image: Source PIL image, possibly carrying an EXIF orientation tag.

    Returns:
        The corrected image (or the original if EXIF is absent / malformed).
    """
    return ImageOps.exif_transpose(image) or image


def _downscale(image: Image.Image, target_long_edge_px: int) -> Image.Image:
    """Resize so the longest edge equals *target_long_edge_px*.

    No-op when the image is already smaller than or equal to the target.

    Args:
        image: Source PIL image.
        target_long_edge_px: Maximum permitted long edge in pixels.

    Returns:
        Downscaled (or original) PIL image.
    """
    w, h = image.size
    long_edge = max(w, h)
    if long_edge <= target_long_edge_px:
        return image
    scale = target_long_edge_px / long_edge
    new_w = round(w * scale)
    new_h = round(h * scale)
    return image.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _deskew(image_array: np.ndarray) -> np.ndarray:
    """Detect dominant near-horizontal lines via Hough and rotate to correct skew.

    Args:
        image_array: OpenCV BGR (or grayscale) numpy array.

    Returns:
        Deskewed array, or the original if no suitable lines were found.
    """
    gray = (
        cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
        if image_array.ndim == 3
        else image_array
    )
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10
    )

    if lines is None or len(lines) == 0:
        return image_array  # no-op: no lines detected

    angles: list[float] = []
    for x1, y1, x2, y2 in lines[:, 0]:
        if x2 == x1:
            continue  # vertical line — skip
        angle_rad = np.arctan2(y2 - y1, x2 - x1)
        angle_deg = float(np.degrees(angle_rad))
        # Normalise to [-90, 90]
        if angle_deg > 90:
            angle_deg -= 180
        if angle_deg < -90:
            angle_deg += 180
        # Only near-horizontal lines (within ±30°)
        if abs(angle_deg) <= 30:
            angles.append(angle_deg)

    if not angles:
        return image_array  # no near-horizontal lines — no-op

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:
        return image_array  # already well-aligned — skip rotation

    h, w = image_array.shape[:2]
    center = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated: np.ndarray = cv2.warpAffine(
        image_array,
        rot_mat,
        (w, h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Order 4 corner points as TL, TR, BR, BL.

    Args:
        pts: Array of shape (4, 2), float32.

    Returns:
        Reordered array of shape (4, 2), float32.
    """
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]   # top-left -- smallest x+y
    rect[2] = pts[np.argmax(s)]   # bottom-right -- largest x+y
    diff = np.diff(pts, axis=1).reshape(-1)
    rect[1] = pts[np.argmin(diff)]  # top-right -- smallest x-y
    rect[3] = pts[np.argmax(diff)]  # bottom-left -- largest x-y
    return rect


def _perspective_correct(image_array: np.ndarray) -> np.ndarray:
    """Find the largest 4-vertex contour (calendar frame) and warp to a rectangle.

    Args:
        image_array: OpenCV BGR (or grayscale) numpy array.

    Returns:
        Perspective-corrected array, or the original if no suitable quad found.
    """
    h, w = image_array.shape[:2]
    image_area = h * w

    gray = (
        cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
        if image_array.ndim == 3
        else image_array
    )
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_contour: np.ndarray | None = None
    best_area = 0.0
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < image_area * 0.3:
            continue  # too small to be the calendar frame
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        if len(approx) == 4 and area > best_area:
            best_contour = approx
            best_area = area

    if best_contour is None:
        return image_array  # no suitable quad found — no-op

    pts = best_contour.reshape(4, 2).astype(np.float32)
    ordered = _order_corners(pts)

    tl, tr, br, bl = ordered
    width_a = float(np.linalg.norm(br - bl))
    width_b = float(np.linalg.norm(tr - tl))
    max_width = int(max(width_a, width_b))
    height_a = float(np.linalg.norm(tr - br))
    height_b = float(np.linalg.norm(tl - bl))
    max_height = int(max(height_a, height_b))

    if max_width < 100 or max_height < 100:
        return image_array  # quad too small to be useful — no-op

    target = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype=np.float32,
    )

    persp_mat = cv2.getPerspectiveTransform(ordered, target)
    warped: np.ndarray = cv2.warpPerspective(image_array, persp_mat, (max_width, max_height))
    return warped


# ---------------------------------------------------------------------------
# Async orchestrator
# ---------------------------------------------------------------------------


async def preprocess_photo(
    image_bytes: bytes,
    *,
    target_long_edge_px: int = 2048,
) -> bytes:
    """Run the standard preprocessing pipeline on a raw uploaded photo.

    Steps (each gracefully falling back to the prior result if it fails):
      1. EXIF rotation — read the EXIF orientation tag and rotate so the image
         is upright.
      2. Downscale — fit the long edge to *target_long_edge_px* (default 2048).
      3. Deskew — detect dominant lines via Hough transform; rotate by the
         median angle to make horizontal lines truly horizontal.
      4. Perspective correction — find the largest 4-corner contour (the
         calendar frame); apply four-point perspective transform to rectify.

    All sync work runs in a thread via :func:`asyncio.to_thread`.

    Args:
        image_bytes: Raw photo bytes (JPEG, PNG, etc.).
        target_long_edge_px: Maximum long-edge pixel count after downscale.

    Returns:
        JPEG-encoded bytes at quality 92.
    """
    return await asyncio.to_thread(_preprocess_photo_sync, image_bytes, target_long_edge_px)


def _preprocess_photo_sync(image_bytes: bytes, target_long_edge_px: int) -> bytes:
    """Synchronous implementation used internally by :func:`preprocess_photo`."""
    # --- Stage 1: Load + EXIF rotation ---
    pil_image: Image.Image
    try:
        pil_image = Image.open(io.BytesIO(image_bytes))
        pil_image.load()
        pil_image = _exif_rotate(pil_image)
    except Exception:
        logger.warning("preprocess: EXIF/load step failed; returning original bytes")
        return image_bytes

    # Normalise colour mode
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    # --- Stage 2: Downscale ---
    try:
        pil_image = _downscale(pil_image, target_long_edge_px)
    except Exception:
        logger.warning("preprocess: downscale failed; continuing with current image")

    # Convert to OpenCV BGR array
    array: np.ndarray = np.array(pil_image)[:, :, ::-1].copy()

    # --- Stage 3: Deskew ---
    try:
        array = _deskew(array)
    except Exception:
        logger.warning("preprocess: deskew failed; continuing with current array")

    # --- Stage 4: Perspective correction ---
    try:
        array = _perspective_correct(array)
    except Exception:
        logger.warning("preprocess: perspective fix failed; continuing with current array")

    # Re-encode as JPEG
    array_rgb: np.ndarray = array[:, :, ::-1].copy()
    final = Image.fromarray(array_rgb)
    buf = io.BytesIO()
    final.save(buf, format="JPEG", quality=92)
    return buf.getvalue()
