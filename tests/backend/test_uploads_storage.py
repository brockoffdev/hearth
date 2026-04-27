"""Unit tests for backend.app.uploads.storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.uploads.storage import (
    extension_for_content_type,
    read_photo,
    store_photo,
)

_SAMPLE_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"


# ---------------------------------------------------------------------------
# extension_for_content_type
# ---------------------------------------------------------------------------


def test_extension_for_content_type() -> None:
    assert extension_for_content_type("image/jpeg") == ".jpg"
    assert extension_for_content_type("image/jpg") == ".jpg"
    assert extension_for_content_type("image/png") == ".png"
    assert extension_for_content_type("image/webp") == ".webp"
    assert extension_for_content_type("image/heic") == ".heic"
    assert extension_for_content_type("image/heif") == ".heic"
    assert extension_for_content_type("application/octet-stream") == ".bin"
    assert extension_for_content_type("text/plain") == ".bin"
    assert extension_for_content_type("") == ".bin"


def test_extension_for_content_type_strips_parameters() -> None:
    """Content-type with ;charset= parameters are normalised before lookup."""
    assert extension_for_content_type("image/jpeg; quality=high") == ".jpg"


# ---------------------------------------------------------------------------
# store_photo / read_photo round-trip
# ---------------------------------------------------------------------------


async def test_store_then_read_round_trips(tmp_path: Path) -> None:
    _sha, rel_path = await store_photo(_SAMPLE_BYTES, "image/jpeg", tmp_path)
    result = await read_photo(rel_path, tmp_path)
    assert result == _SAMPLE_BYTES


async def test_store_returns_content_addressed_path(tmp_path: Path) -> None:
    import hashlib

    sha = hashlib.sha256(_SAMPLE_BYTES).hexdigest()
    _sha_ret, rel_path = await store_photo(_SAMPLE_BYTES, "image/jpeg", tmp_path)

    assert _sha_ret == sha
    # Path structure: uploads/<2 chars>/<rest>/original.jpg
    assert rel_path == f"uploads/{sha[:2]}/{sha[2:]}/original.jpg"
    assert (tmp_path / rel_path).exists()


async def test_store_idempotent_for_same_bytes(tmp_path: Path) -> None:
    """Storing the same bytes twice returns the same path; file is unchanged."""
    _sha1, path1 = await store_photo(_SAMPLE_BYTES, "image/jpeg", tmp_path)
    _sha2, path2 = await store_photo(_SAMPLE_BYTES, "image/jpeg", tmp_path)

    assert path1 == path2
    assert _sha1 == _sha2
    # File content is still the original bytes.
    result = await read_photo(path1, tmp_path)
    assert result == _SAMPLE_BYTES


async def test_read_photo_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        await read_photo("uploads/ab/nonexistent/original.jpg", tmp_path)
