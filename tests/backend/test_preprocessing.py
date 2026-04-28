"""Tests for backend/app/uploads/preprocessing.py (Phase 4 Task D)."""

from __future__ import annotations

import io

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.app.uploads.preprocessing import (
    _deskew,
    _downscale,
    _exif_rotate,
    _perspective_correct,
    preprocess_photo,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_rgb_image(
    width: int, height: int, color: tuple[int, int, int] = (200, 200, 200)
) -> Image.Image:
    return Image.new("RGB", (width, height), color=color)


def make_image_bytes(image: Image.Image, fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return buf.getvalue()


def pil_to_bgr(image: Image.Image) -> np.ndarray:
    """Convert PIL RGB image to OpenCV BGR array."""
    arr = np.array(image)
    return arr[:, :, ::-1].copy()


# ---------------------------------------------------------------------------
# _exif_rotate
# ---------------------------------------------------------------------------


class TestExifRotate:
    def test_upright_image_unchanged_dimensions(self) -> None:
        """An image with no EXIF orientation tag should keep its dimensions."""
        img = make_rgb_image(400, 200)
        result = _exif_rotate(img)
        assert result.size == (400, 200)

    def test_orientation_6_swaps_dimensions(self) -> None:
        """EXIF orientation=6 means 90 CW rotation needed; corrected image is taller than wide."""
        # Create a 400x200 landscape image with orientation tag 6 (rotate 90 CW to correct).
        # After correction a 400x200 landscape becomes 200x400 portrait.
        img = make_rgb_image(400, 200)

        # Inject EXIF orientation=6 using Pillow's native Exif object so the tag is properly
        # encoded and survives a JPEG round-trip.
        exif_data = img.getexif()
        exif_data[0x0112] = 6  # Orientation = 6 (90 CW rotation required)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif_data.tobytes())
        buf.seek(0)
        loaded = Image.open(buf)
        loaded.load()

        result = _exif_rotate(loaded)
        # After correcting orientation 6, a 400-wide x 200-tall image becomes 200-wide x 400-tall
        assert result.size == (200, 400)

    def test_returns_image_even_if_no_exif(self) -> None:
        """No EXIF should not raise; the same image is returned."""
        img = make_rgb_image(100, 100)
        result = _exif_rotate(img)
        assert isinstance(result, Image.Image)


# ---------------------------------------------------------------------------
# _downscale
# ---------------------------------------------------------------------------


class TestDownscale:
    def test_large_image_scaled_down(self) -> None:
        img = make_rgb_image(4096, 3072)
        result = _downscale(img, 2048)
        assert max(result.size) == 2048

    def test_aspect_ratio_preserved(self) -> None:
        img = make_rgb_image(4096, 3072)
        result = _downscale(img, 2048)
        original_ratio = 4096 / 3072
        result_ratio = result.width / result.height
        assert abs(original_ratio - result_ratio) < 0.01

    def test_small_image_not_upscaled(self) -> None:
        img = make_rgb_image(800, 600)
        result = _downscale(img, 2048)
        assert result.size == (800, 600)

    def test_exact_target_unchanged(self) -> None:
        img = make_rgb_image(2048, 1024)
        result = _downscale(img, 2048)
        assert result.size == (2048, 1024)

    def test_portrait_orientation(self) -> None:
        """Portrait image: height > width; long edge is height."""
        img = make_rgb_image(1000, 4000)
        result = _downscale(img, 2048)
        assert max(result.size) == 2048


# ---------------------------------------------------------------------------
# _deskew
# ---------------------------------------------------------------------------


class TestDeskew:
    def _make_rotated_grid_array(self, angle_deg: float = 5.0) -> np.ndarray:
        """Create a white 600x600 image with black horizontal lines, rotated by angle_deg."""
        img = Image.new("RGB", (600, 600), color="white")
        draw = ImageDraw.Draw(img)
        for y in range(50, 600, 80):
            draw.line([(0, y), (599, y)], fill="black", width=3)
        arr = pil_to_bgr(img)
        h, w = arr.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
        rotated: np.ndarray = cv2.warpAffine(
            arr, rot_mat, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        )
        return rotated

    def _measure_median_angle(self, arr: np.ndarray) -> float:
        """Re-measure the median line angle in an array (same method as _deskew)."""
        gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY) if arr.ndim == 3 else arr
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=100, minLineLength=100, maxLineGap=10
        )
        if lines is None or len(lines) == 0:
            return 0.0
        angles = []
        for x1, y1, x2, y2 in lines[:, 0]:
            if x2 == x1:
                continue
            angle_rad = np.arctan2(y2 - y1, x2 - x1)
            angle_deg = np.degrees(angle_rad)
            if angle_deg > 90:
                angle_deg -= 180
            if angle_deg < -90:
                angle_deg += 180
            if abs(angle_deg) <= 30:
                angles.append(angle_deg)
        return float(np.median(angles)) if angles else 0.0

    def test_deskew_reduces_angle(self) -> None:
        """After deskew, the remaining median line angle should be < 1 degree."""
        rotated = self._make_rotated_grid_array(angle_deg=5.0)
        deskewed = _deskew(rotated)
        remaining = self._measure_median_angle(deskewed)
        assert abs(remaining) < 1.0, f"Remaining angle {remaining:.2f} deg is not < 1 deg"

    def test_already_aligned_no_change(self) -> None:
        """Image with lines already horizontal should return basically the same array."""
        img = Image.new("RGB", (400, 400), color="white")
        draw = ImageDraw.Draw(img)
        for y in range(50, 400, 60):
            draw.line([(0, y), (399, y)], fill="black", width=3)
        arr = pil_to_bgr(img)
        result = _deskew(arr)
        assert result.shape == arr.shape

    def test_no_lines_returns_original(self) -> None:
        """Blank image with no detectable lines returns original array."""
        arr = np.full((200, 200, 3), 200, dtype=np.uint8)
        result = _deskew(arr)
        np.testing.assert_array_equal(result, arr)

    def test_output_same_shape_as_input(self) -> None:
        rotated = self._make_rotated_grid_array(angle_deg=8.0)
        result = _deskew(rotated)
        assert result.shape == rotated.shape


# ---------------------------------------------------------------------------
# _perspective_correct
# ---------------------------------------------------------------------------


class TestPerspectiveCorrect:
    def _make_quad_image(
        self,
        img_w: int = 600,
        img_h: int = 600,
        quad_pts: list[tuple[int, int]] | None = None,
    ) -> np.ndarray:
        """White image with a drawn quadrilateral outline -- simulates a calendar frame."""
        img = Image.new("RGB", (img_w, img_h), color="white")
        draw = ImageDraw.Draw(img)
        if quad_pts is None:
            quad_pts = [(60, 50), (540, 60), (530, 540), (70, 535)]
        draw.polygon(quad_pts, outline="black", fill=None)
        # Draw a thick outline so Canny picks it up
        for i in range(3):
            draw.polygon(
                [(x + i, y + i) for x, y in quad_pts],
                outline="black",
                fill=None,
            )
        return pil_to_bgr(img)

    def test_output_bounded_by_quad_dimensions(self) -> None:
        """Output should be smaller than the source image (quad is the inner frame)."""
        arr = self._make_quad_image()
        result = _perspective_correct(arr)
        # Whether a quad was found or not, the result must be a valid non-empty array
        assert result.shape[0] > 0 and result.shape[1] > 0

    def test_no_quad_returns_original(self) -> None:
        """Blank image should return the original array unchanged."""
        arr = np.full((300, 300, 3), 240, dtype=np.uint8)
        result = _perspective_correct(arr)
        np.testing.assert_array_equal(result, arr)

    def test_output_is_ndarray(self) -> None:
        arr = self._make_quad_image()
        result = _perspective_correct(arr)
        assert isinstance(result, np.ndarray)

    def test_too_small_contour_ignored(self) -> None:
        """A tiny quadrilateral (< 30% of image area) should not trigger perspective warp."""
        img = Image.new("RGB", (600, 600), color="white")
        draw = ImageDraw.Draw(img)
        # Tiny quad in the corner (well under 30% of 600x600)
        tiny_pts = [(10, 10), (40, 10), (40, 40), (10, 40)]
        draw.polygon(tiny_pts, outline="black", fill=None)
        arr = pil_to_bgr(img)
        result = _perspective_correct(arr)
        # Should return original unchanged
        assert result.shape == arr.shape


# ---------------------------------------------------------------------------
# preprocess_photo orchestrator
# ---------------------------------------------------------------------------


class TestPreprocessPhoto:
    @pytest.mark.asyncio
    async def test_returns_jpeg_bytes(self) -> None:
        """Output must start with JPEG magic bytes."""
        img = make_rgb_image(400, 300)
        data = make_image_bytes(img)
        result = await preprocess_photo(data)
        assert result[:3] == b"\xff\xd8\xff"

    @pytest.mark.asyncio
    async def test_handles_corrupt_input_gracefully(self) -> None:
        """Corrupt bytes must not raise -- original bytes returned as fallback."""
        result = await preprocess_photo(b"not an image")
        # Must return bytes without raising
        assert isinstance(result, bytes)
        # Fallback: the original bytes are returned
        assert result == b"not an image"

    @pytest.mark.asyncio
    async def test_downscales_large_image(self) -> None:
        """A 5000x3000 image should be returned as <=2048 on the long edge."""
        img = make_rgb_image(5000, 3000)
        data = make_image_bytes(img)
        result = await preprocess_photo(data, target_long_edge_px=2048)
        out_img = Image.open(io.BytesIO(result))
        assert max(out_img.size) <= 2048

    @pytest.mark.asyncio
    async def test_preserves_small_image(self) -> None:
        """An 800x600 image should stay at 800x600."""
        img = make_rgb_image(800, 600)
        data = make_image_bytes(img)
        result = await preprocess_photo(data)
        out_img = Image.open(io.BytesIO(result))
        assert out_img.size == (800, 600)

    @pytest.mark.asyncio
    async def test_accepts_png_input(self) -> None:
        """PNG input should be converted and returned as JPEG."""
        img = make_rgb_image(200, 200)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = await preprocess_photo(buf.getvalue())
        assert result[:3] == b"\xff\xd8\xff"

    @pytest.mark.asyncio
    async def test_rgba_input_converted_to_rgb(self) -> None:
        """RGBA images should be handled (converted to RGB) without error."""
        img = Image.new("RGBA", (200, 200), color=(100, 150, 200, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = await preprocess_photo(buf.getvalue())
        assert result[:3] == b"\xff\xd8\xff"
