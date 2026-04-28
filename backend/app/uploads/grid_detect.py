"""Grid detection for Hearth calendar photos (Phase 4 Task E).

Detects the 5x7 calendar grid in a preprocessed photo and returns
cell bounding boxes plus the right-side notes panel coordinates.

Public API
----------
detect_grid(image_bytes) -> GridDetectionResult   (async)
crop_cell(image_bytes, cell, *, padding_px=8) -> bytes
crop_notes_panel(image_bytes, panel, *, padding_px=8) -> bytes
"""

from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CellBox:
    """One cell of the calendar grid, in image-pixel coordinates."""

    row: int  # 0..4 (5 weeks)
    col: int  # 0..6 (7 days)
    x: int  # left edge in pixels
    y: int  # top edge in pixels
    width: int
    height: int


@dataclass(frozen=True)
class NotesPanel:
    """The right-side notes/long-future-events panel, if present."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class GridDetectionResult:
    """Result of grid detection.

    *cells* is always 35 long (or 0 if image could not be loaded).
    *notes* is None when the panel was not detected or detection fell back.
    *detection_method* is one of "lines", "fallback", or "failed".
    """

    cells: tuple[CellBox, ...]
    notes: NotesPanel | None
    detection_method: str


# ---------------------------------------------------------------------------
# Public async entry point
# ---------------------------------------------------------------------------


async def detect_grid(image_bytes: bytes) -> GridDetectionResult:
    """Detect the 5x7 calendar grid in *image_bytes*.

    Runs synchronous OpenCV work in a thread via :func:`asyncio.to_thread`.

    Returns a :class:`GridDetectionResult` with 35 cells.  On any failure the
    result falls back to a uniform grid or, if the image cannot be loaded, an
    empty-cell "failed" result.
    """
    return await asyncio.to_thread(_detect_grid_sync, image_bytes)


# ---------------------------------------------------------------------------
# Sync crop helpers (public)
# ---------------------------------------------------------------------------


def crop_cell(image_bytes: bytes, cell: CellBox, *, padding_px: int = 8) -> bytes:
    """Crop a single cell out of the image (with small padding).

    Returns JPEG bytes ready for VLM consumption.
    """
    return _crop_box(image_bytes, cell.x, cell.y, cell.width, cell.height, padding_px)


def crop_notes_panel(image_bytes: bytes, panel: NotesPanel, *, padding_px: int = 8) -> bytes:
    """Crop the notes panel out of the photo.

    Returns JPEG bytes.
    """
    return _crop_box(image_bytes, panel.x, panel.y, panel.width, panel.height, padding_px)


# ---------------------------------------------------------------------------
# Internal sync implementation
# ---------------------------------------------------------------------------


def _detect_grid_sync(image_bytes: bytes) -> GridDetectionResult:
    """Synchronous implementation used by :func:`detect_grid`."""
    # --- Load image ---
    try:
        pil_image: Image.Image = Image.open(io.BytesIO(image_bytes))
        pil_image.load()
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        array = np.array(pil_image)[:, :, ::-1]  # RGB → BGR for OpenCV
    except Exception:
        logger.warning("grid_detect: failed to load image; cannot detect grid")
        return GridDetectionResult(cells=(), notes=None, detection_method="failed")

    h, w = array.shape[:2]

    # --- Try Hough-line-based detection ---
    try:
        cells, notes = _detect_grid_via_lines(array)
        if cells is not None and len(cells) == 35:
            return GridDetectionResult(
                cells=tuple(cells), notes=notes, detection_method="lines"
            )
    except Exception:
        logger.warning(
            "grid_detect: line-based detection raised an exception; falling back to uniform grid"
        )

    # --- Fallback: uniform 5x7 grid ---
    cells = _uniform_grid_cells(w, h)
    return GridDetectionResult(cells=tuple(cells), notes=None, detection_method="fallback")


def _detect_grid_via_lines(
    array: np.ndarray,
) -> tuple[list[CellBox] | None, NotesPanel | None]:
    """Attempt to detect the 5x7 grid using Hough line detection.

    Returns *(cells, notes)* on success; *(None, None)* if detection failed
    (not enough lines or ambiguous clusters).
    """
    h, w = array.shape[:2]

    gray = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # Probabilistic Hough: thresholds scaled to image size
    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=int(min(h, w) * 0.3),
        minLineLength=int(min(h, w) * 0.4),
        maxLineGap=20,
    )

    if lines is None or len(lines) < 8:
        return None, None

    horizontals: list[int] = []  # y-coordinates of horizontal lines
    verticals: list[int] = []  # x-coordinates of vertical lines

    for x1, y1, x2, y2 in lines[:, 0]:
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) < 1:  # near-vertical (dx ≈ 0)
            verticals.append((x1 + x2) // 2)
            continue
        if abs(dy) < 1:  # near-horizontal (dy ≈ 0)
            horizontals.append((y1 + y2) // 2)
            continue
        angle_deg = abs(float(np.degrees(np.arctan2(dy, dx))))
        if angle_deg < 15 or angle_deg > 165:
            horizontals.append((y1 + y2) // 2)
        elif 75 < angle_deg < 105:
            verticals.append((x1 + x2) // 2)

    # Cluster nearby lines (tolerance ~ 2% of image dimension)
    h_lines = _cluster_coordinates(horizontals, tolerance=int(h * 0.02))
    v_lines = _cluster_coordinates(verticals, tolerance=int(w * 0.02))

    # Need ≥6 horizontal and ≥8 vertical lines
    if len(h_lines) < 6 or len(v_lines) < 8:
        return None, None

    # Use the first 8 vertical and first 6 horizontal lines (left-anchored calendar)
    v_lines = sorted(v_lines)[:8]
    h_lines = sorted(h_lines)[:6]

    if len(h_lines) != 6 or len(v_lines) != 8:
        return None, None

    # Build the 35 cell boxes
    cells: list[CellBox] = []
    for row in range(5):
        for col in range(7):
            y0 = h_lines[row]
            y1 = h_lines[row + 1]
            x0 = v_lines[col]
            x1 = v_lines[col + 1]
            cells.append(
                CellBox(
                    row=row,
                    col=col,
                    x=int(x0),
                    y=int(y0),
                    width=int(x1 - x0),
                    height=int(y1 - y0),
                )
            )

    # Notes panel: right of v_lines[7] up to the image right edge
    notes_x = v_lines[7]
    notes_y = h_lines[0]
    notes_w = w - notes_x
    notes_h = h_lines[-1] - h_lines[0]

    notes: NotesPanel | None = None
    if notes_w > w * 0.05 and notes_w < w * 0.4:
        notes = NotesPanel(
            x=int(notes_x),
            y=int(notes_y),
            width=int(notes_w),
            height=int(notes_h),
        )

    return cells, notes


def _cluster_coordinates(coords: list[int], *, tolerance: int) -> list[int]:
    """Cluster nearby integer coordinates and return the cluster centres.

    Coordinates within *tolerance* pixels of the previous cluster's last member
    are merged.  Returns a sorted list of cluster mean values.
    """
    if not coords:
        return []
    sorted_coords = sorted(coords)
    clusters: list[list[int]] = [[sorted_coords[0]]]
    for c in sorted_coords[1:]:
        if c - clusters[-1][-1] <= tolerance:
            clusters[-1].append(c)
        else:
            clusters.append([c])
    return [int(np.mean(cluster)) for cluster in clusters]


def _uniform_grid_cells(width: int, height: int) -> list[CellBox]:
    """Fallback: divide the image into a uniform 5x7 grid of cells."""
    cell_w = width // 7
    cell_h = height // 5
    cells: list[CellBox] = []
    for row in range(5):
        for col in range(7):
            cells.append(
                CellBox(
                    row=row,
                    col=col,
                    x=col * cell_w,
                    y=row * cell_h,
                    width=cell_w,
                    height=cell_h,
                )
            )
    return cells


# ---------------------------------------------------------------------------
# Internal crop helper
# ---------------------------------------------------------------------------


def _crop_box(image_bytes: bytes, x: int, y: int, w: int, h: int, padding: int) -> bytes:
    """Load *image_bytes*, crop the region *(x, y, w, h)* with *padding*, return JPEG."""
    pil_image: Image.Image = Image.open(io.BytesIO(image_bytes))
    pil_image.load()
    if pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")
    img_w, img_h = pil_image.size
    left = max(0, x - padding)
    top = max(0, y - padding)
    right = min(img_w, x + w + padding)
    bottom = min(img_h, y + h + padding)
    cropped = pil_image.crop((left, top, right, bottom))
    buf = io.BytesIO()
    cropped.save(buf, format="JPEG", quality=92)
    return buf.getvalue()
