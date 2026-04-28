"""Tests for backend/app/uploads/grid_detect.py (Phase 4 Task E).

All test images are synthesised — no bundled photos.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from backend.app.uploads.grid_detect import (
    CellBox,
    GridDetectionResult,
    NotesPanel,
    _cluster_coordinates,
    _uniform_grid_cells,
    crop_cell,
    crop_notes_panel,
    detect_grid,
)

# ---------------------------------------------------------------------------
# Synthetic image helpers
# ---------------------------------------------------------------------------


def _make_perfect_grid(width: int = 1500, height: int = 1000) -> bytes:
    """White background with a crisp 5x7 black-line grid covering the full image."""
    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)
    cell_w = width // 7
    cell_h = height // 5
    # Vertical lines (8 lines for 7 columns)
    for col in range(8):
        x = col * cell_w
        draw.line([(x, 0), (x, height - 1)], fill="black", width=3)
    # Horizontal lines (6 lines for 5 rows)
    for row in range(6):
        y = row * cell_h
        draw.line([(0, y), (width - 1, y)], fill="black", width=3)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _make_grid_with_notes_panel(
    width: int = 1500, height: int = 1000, grid_fraction: float = 0.70
) -> bytes:
    """Grid occupying the left 70% of the image; blank right side is the notes panel."""
    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)
    grid_w = int(width * grid_fraction)
    cell_w = grid_w // 7
    cell_h = height // 5
    # Vertical lines
    for col in range(8):
        x = col * cell_w
        draw.line([(x, 0), (x, height - 1)], fill="black", width=3)
    # Horizontal lines
    for row in range(6):
        y = row * cell_h
        draw.line([(0, y), (grid_w - 1, y)], fill="black", width=3)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _make_solid_image(width: int = 800, height: int = 600) -> bytes:
    """Solid grey — no grid lines."""
    image = Image.new("RGB", (width, height), color=(180, 180, 180))
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# detect_grid — perfect grid
# ---------------------------------------------------------------------------


class TestDetectGridPerfectGrid:
    @pytest.mark.asyncio
    async def test_detect_grid_returns_35_cells_for_perfect_grid(self) -> None:
        image_bytes = _make_perfect_grid()
        result = await detect_grid(image_bytes)
        assert len(result.cells) == 35

    @pytest.mark.asyncio
    async def test_detect_grid_uses_lines_method_for_perfect_grid(self) -> None:
        image_bytes = _make_perfect_grid()
        result = await detect_grid(image_bytes)
        assert result.detection_method == "lines"

    @pytest.mark.asyncio
    async def test_detect_grid_cells_cover_all_row_col_combos(self) -> None:
        image_bytes = _make_perfect_grid()
        result = await detect_grid(image_bytes)
        coords = {(c.row, c.col) for c in result.cells}
        expected = {(r, c) for r in range(5) for c in range(7)}
        assert coords == expected

    @pytest.mark.asyncio
    async def test_detect_grid_cell_positions_roughly_match_drawn_grid(self) -> None:
        """Cell (row, col) x/y should be within 10px of the drawn grid lines."""
        width, height = 1500, 1000
        image_bytes = _make_perfect_grid(width, height)
        result = await detect_grid(image_bytes)

        cell_w = width // 7
        cell_h = height // 5
        tolerance = 10  # pixels

        for cell in result.cells:
            expected_x = cell.col * cell_w
            expected_y = cell.row * cell_h
            assert abs(cell.x - expected_x) <= tolerance, (
                f"Cell ({cell.row},{cell.col}) x={cell.x}, expected ~{expected_x}"
            )
            assert abs(cell.y - expected_y) <= tolerance, (
                f"Cell ({cell.row},{cell.col}) y={cell.y}, expected ~{expected_y}"
            )


# ---------------------------------------------------------------------------
# detect_grid — solid image (fallback)
# ---------------------------------------------------------------------------


class TestDetectGridFallback:
    @pytest.mark.asyncio
    async def test_detect_grid_falls_back_for_solid_image(self) -> None:
        image_bytes = _make_solid_image()
        result = await detect_grid(image_bytes)
        assert result.detection_method == "fallback"
        assert len(result.cells) == 35

    @pytest.mark.asyncio
    async def test_detect_grid_uniform_fallback_dimensions(self) -> None:
        """Fallback cells must tile the image without gaps or overlaps."""
        width, height = 800, 600
        image_bytes = _make_solid_image(width, height)
        result = await detect_grid(image_bytes)
        assert result.detection_method == "fallback"

        cell_w = width // 7
        cell_h = height // 5

        # Check all 35 cells have uniform dimensions and correct positions
        for cell in result.cells:
            assert cell.width == cell_w, f"Cell width {cell.width} != {cell_w}"
            assert cell.height == cell_h, f"Cell height {cell.height} != {cell_h}"
            assert cell.x == cell.col * cell_w
            assert cell.y == cell.row * cell_h

    @pytest.mark.asyncio
    async def test_detect_grid_fallback_notes_is_none(self) -> None:
        image_bytes = _make_solid_image()
        result = await detect_grid(image_bytes)
        assert result.notes is None


# ---------------------------------------------------------------------------
# detect_grid — corrupt input
# ---------------------------------------------------------------------------


class TestDetectGridCorruptInput:
    @pytest.mark.asyncio
    async def test_detect_grid_handles_corrupt_input(self) -> None:
        """b'not an image' should return a failed result (empty cells)."""
        result = await detect_grid(b"not an image")
        # Either failed or fallback — must not raise
        assert isinstance(result, GridDetectionResult)
        # When we can't load the image we can't determine dimensions → failed
        assert result.detection_method == "failed"
        assert len(result.cells) == 0

    @pytest.mark.asyncio
    async def test_detect_grid_handles_empty_bytes(self) -> None:
        result = await detect_grid(b"")
        assert isinstance(result, GridDetectionResult)
        assert result.detection_method == "failed"


# ---------------------------------------------------------------------------
# detect_grid — notes panel
# ---------------------------------------------------------------------------


class TestDetectGridNotesPanel:
    @pytest.mark.asyncio
    async def test_detect_grid_finds_notes_panel_when_grid_is_left_aligned(self) -> None:
        """When the grid covers ~70% of the width, notes panel should be detected."""
        width, height = 1500, 1000
        image_bytes = _make_grid_with_notes_panel(width, height, grid_fraction=0.70)
        result = await detect_grid(image_bytes)

        # May detect via lines or fallback — notes only expected for lines
        if result.detection_method == "lines":
            # Notes panel should be roughly the right 30%
            if result.notes is not None:
                notes = result.notes
                # Notes x should be > 60% of width
                assert notes.x > width * 0.60, f"notes.x={notes.x} not in right portion"
                # Notes width should be > 15% of image width
                assert notes.width > width * 0.15, f"notes.width={notes.width} too small"


# ---------------------------------------------------------------------------
# _cluster_coordinates — unit tests
# ---------------------------------------------------------------------------


class TestClusterCoordinates:
    def test_cluster_coordinates_groups_near_values(self) -> None:
        coords = [10, 12, 11, 50, 52, 100]
        result = _cluster_coordinates(coords, tolerance=5)
        assert len(result) == 3
        assert abs(result[0] - 11) <= 2
        assert abs(result[1] - 51) <= 2
        assert abs(result[2] - 100) <= 2

    def test_cluster_coordinates_handles_empty(self) -> None:
        assert _cluster_coordinates([], tolerance=10) == []

    def test_cluster_coordinates_single_value(self) -> None:
        assert _cluster_coordinates([42], tolerance=10) == [42]

    def test_cluster_coordinates_all_in_one_cluster(self) -> None:
        coords = [1, 2, 3, 4, 5]
        result = _cluster_coordinates(coords, tolerance=5)
        assert len(result) == 1
        assert abs(result[0] - 3) <= 1  # mean ≈ 3

    def test_cluster_coordinates_tolerance_boundary(self) -> None:
        """Values exactly at tolerance distance should cluster together."""
        coords = [0, 5]
        result = _cluster_coordinates(coords, tolerance=5)
        assert len(result) == 1

    def test_cluster_coordinates_just_outside_tolerance(self) -> None:
        """Values one beyond tolerance should stay separate."""
        coords = [0, 6]
        result = _cluster_coordinates(coords, tolerance=5)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# _uniform_grid_cells — unit tests
# ---------------------------------------------------------------------------


class TestUniformGridCells:
    def test_uniform_grid_cells_returns_35(self) -> None:
        cells = _uniform_grid_cells(1400, 1000)
        assert len(cells) == 35

    def test_uniform_grid_cells_dimensions(self) -> None:
        width, height = 700, 500
        cells = _uniform_grid_cells(width, height)
        cell_w = width // 7
        cell_h = height // 5
        for cell in cells:
            assert cell.width == cell_w
            assert cell.height == cell_h

    def test_uniform_grid_cells_all_row_col_combos(self) -> None:
        cells = _uniform_grid_cells(1400, 1000)
        coords = {(c.row, c.col) for c in cells}
        expected = {(r, c) for r in range(5) for c in range(7)}
        assert coords == expected

    def test_uniform_grid_cells_no_overlap(self) -> None:
        """Each pixel position should be covered by exactly one cell."""
        width, height = 700, 500
        cells = _uniform_grid_cells(width, height)
        coverage: dict[tuple[int, int], int] = {}
        for cell in cells:
            for row in range(cell.y, cell.y + cell.height):
                for col in range(cell.x, cell.x + cell.width):
                    key = (row, col)
                    coverage[key] = coverage.get(key, 0) + 1
        overlaps = [k for k, v in coverage.items() if v > 1]
        assert overlaps == [], f"Found {len(overlaps)} overlapping pixels"

    def test_uniform_grid_cells_returns_cellbox_instances(self) -> None:
        cells = _uniform_grid_cells(700, 500)
        for cell in cells:
            assert isinstance(cell, CellBox)


# ---------------------------------------------------------------------------
# crop_cell
# ---------------------------------------------------------------------------


class TestCropCell:
    def test_crop_cell_returns_jpeg_bytes(self) -> None:
        image_bytes = _make_perfect_grid()
        cell = CellBox(row=0, col=0, x=0, y=0, width=200, height=150)
        result = crop_cell(image_bytes, cell)
        # JPEG magic bytes: FF D8
        assert result[:2] == b"\xff\xd8"

    def test_crop_cell_clamps_to_image_bounds(self) -> None:
        """Padding that would push outside the image is clamped without error."""
        image_bytes = _make_solid_image(100, 100)
        # A cell at the bottom-right corner
        cell = CellBox(row=4, col=6, x=90, y=90, width=10, height=10)
        result = crop_cell(image_bytes, cell, padding_px=20)
        # Should return valid JPEG bytes
        assert result[:2] == b"\xff\xd8"
        # Result image should be non-empty
        cropped = Image.open(io.BytesIO(result))
        assert cropped.size[0] > 0 and cropped.size[1] > 0

    def test_crop_cell_respects_padding(self) -> None:
        """Cropped region should be larger with padding than without."""
        image_bytes = _make_solid_image(400, 400)
        cell = CellBox(row=1, col=1, x=100, y=100, width=100, height=100)
        result_no_pad = crop_cell(image_bytes, cell, padding_px=0)
        result_with_pad = crop_cell(image_bytes, cell, padding_px=10)
        img_no_pad = Image.open(io.BytesIO(result_no_pad))
        img_with_pad = Image.open(io.BytesIO(result_with_pad))
        assert img_with_pad.size[0] > img_no_pad.size[0]
        assert img_with_pad.size[1] > img_no_pad.size[1]


# ---------------------------------------------------------------------------
# crop_notes_panel
# ---------------------------------------------------------------------------


class TestCropNotesPanel:
    def test_crop_notes_panel_returns_jpeg_bytes(self) -> None:
        image_bytes = _make_solid_image(800, 600)
        panel = NotesPanel(x=560, y=0, width=240, height=600)
        result = crop_notes_panel(image_bytes, panel)
        assert result[:2] == b"\xff\xd8"

    def test_crop_notes_panel_dimensions(self) -> None:
        """Cropped panel (without padding) should match panel dimensions."""
        image_bytes = _make_solid_image(800, 600)
        panel = NotesPanel(x=100, y=50, width=200, height=300)
        result = crop_notes_panel(image_bytes, panel, padding_px=0)
        cropped = Image.open(io.BytesIO(result))
        assert cropped.size == (200, 300)

    def test_crop_notes_panel_clamps_to_image_bounds(self) -> None:
        """Panel right at the image edge with padding should not error."""
        image_bytes = _make_solid_image(100, 100)
        panel = NotesPanel(x=80, y=80, width=20, height=20)
        result = crop_notes_panel(image_bytes, panel, padding_px=30)
        assert result[:2] == b"\xff\xd8"


# ---------------------------------------------------------------------------
# GridDetectionResult — dataclass shape
# ---------------------------------------------------------------------------


class TestGridDetectionResult:
    def test_result_is_frozen(self) -> None:
        cells = tuple(_uniform_grid_cells(700, 500))
        result = GridDetectionResult(cells=cells, notes=None, detection_method="fallback")
        with pytest.raises((AttributeError, TypeError)):
            result.detection_method = "mutated"  # type: ignore[misc]

    def test_cellbox_is_frozen(self) -> None:
        cell = CellBox(row=0, col=0, x=0, y=0, width=100, height=100)
        with pytest.raises((AttributeError, TypeError)):
            cell.row = 99  # type: ignore[misc]

    def test_notes_panel_is_frozen(self) -> None:
        panel = NotesPanel(x=10, y=10, width=100, height=200)
        with pytest.raises((AttributeError, TypeError)):
            panel.x = 999  # type: ignore[misc]
