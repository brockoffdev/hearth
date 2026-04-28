"""Tests for extract_photographed_date (Phase 5 Task B).

Verifies EXIF DateTimeOriginal extraction from real Pillow-synthesized images.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO

from PIL import Image

from backend.app.uploads.preprocessing import extract_photographed_date

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_image_with_exif(date_str: str) -> bytes:
    """Create a JPEG with the given DateTimeOriginal (tag 36867) in EXIF."""
    image = Image.new("RGB", (200, 200), color="white")
    exif = image.getexif()
    exif[36867] = date_str  # DateTimeOriginal
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=92, exif=exif.tobytes())
    return buf.getvalue()


def _make_image_with_datetime_tag_only(date_str: str) -> bytes:
    """Create a JPEG with only DateTime (tag 306) in EXIF — no DateTimeOriginal."""
    image = Image.new("RGB", (200, 200), color="white")
    exif = image.getexif()
    exif[306] = date_str  # DateTime (last-modified)
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=92, exif=exif.tobytes())
    return buf.getvalue()


def _make_image_without_exif() -> bytes:
    """Create a JPEG with no EXIF data at all."""
    image = Image.new("RGB", (200, 200), color="white")
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _make_image_with_bad_exif(date_str: str) -> bytes:
    """Create a JPEG with DateTimeOriginal containing an invalid date string."""
    image = Image.new("RGB", (200, 200), color="white")
    exif = image.getexif()
    exif[36867] = date_str  # Bad format
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=92, exif=exif.tobytes())
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_extract_photographed_date_returns_date_when_present() -> None:
    """EXIF DateTimeOriginal '2026:04:27 14:35:12' → date(2026, 4, 27)."""
    image_bytes = _make_image_with_exif("2026:04:27 14:35:12")
    result = extract_photographed_date(image_bytes)
    assert result == date(2026, 4, 27), f"Expected date(2026, 4, 27), got {result}"


def test_extract_photographed_date_returns_none_when_missing() -> None:
    """Image with no EXIF data at all returns None."""
    image_bytes = _make_image_without_exif()
    result = extract_photographed_date(image_bytes)
    assert result is None, f"Expected None for image with no EXIF, got {result}"


def test_extract_photographed_date_falls_back_to_datetime_tag() -> None:
    """When only DateTime (tag 306) is present, falls back and returns its date."""
    image_bytes = _make_image_with_datetime_tag_only("2025:12:15 08:00:00")
    result = extract_photographed_date(image_bytes)
    assert result == date(2025, 12, 15), f"Expected date(2025, 12, 15), got {result}"


def test_extract_photographed_date_returns_none_on_invalid_format() -> None:
    """EXIF DateTimeOriginal with invalid format 'garbage' returns None."""
    image_bytes = _make_image_with_bad_exif("garbage-not-a-date")
    result = extract_photographed_date(image_bytes)
    assert result is None, f"Expected None for invalid format, got {result}"


def test_extract_photographed_date_returns_none_on_corrupt_image() -> None:
    """Completely non-image bytes returns None (defensive error handling)."""
    result = extract_photographed_date(b"not an image at all")
    assert result is None, f"Expected None for corrupt image, got {result}"
