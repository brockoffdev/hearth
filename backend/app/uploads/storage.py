"""Content-addressed photo storage.

Photos are stored under:
  <data_dir>/uploads/<sha256[:2]>/<sha256[2:]>/original.<ext>

The two-level fan-out prevents single-directory crowding at high upload volume.
The path stored in the DB is *relative to data_dir*, e.g.:
  uploads/ab/cdef1234.../original.jpg

This decouples DB content from the host filesystem layout.
"""

import asyncio
import hashlib
from pathlib import Path

# Map MIME type → file extension.
_CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heic",
}


def extension_for_content_type(content_type: str) -> str:
    """Map content-type to file extension.  Unknown types map to '.bin'."""
    # Normalise: strip parameters such as '; charset=utf-8'.
    mime = content_type.split(";")[0].strip().lower()
    return _CONTENT_TYPE_TO_EXT.get(mime, ".bin")


async def store_photo(
    image_bytes: bytes,
    content_type: str,
    data_dir: Path,
) -> tuple[str, str]:
    """Store photo bytes using content-addressed paths.

    Returns:
        (sha256_hex, image_path) where image_path is relative to data_dir,
        e.g. 'uploads/ab/cdef1234.../original.jpg'.

    If the same file has already been stored (identical SHA-256), the write is
    a no-op (the new bytes are identical so overwriting is harmless).
    """
    sha256_hex = hashlib.sha256(image_bytes).hexdigest()
    ext = extension_for_content_type(content_type)
    rel_path = f"uploads/{sha256_hex[:2]}/{sha256_hex[2:]}/original{ext}"
    abs_path = data_dir / rel_path

    def _write() -> None:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(image_bytes)

    await asyncio.to_thread(_write)
    return sha256_hex, rel_path


async def read_photo(image_path: str, data_dir: Path) -> bytes:
    """Read photo bytes given a relative path stored on an Upload row.

    Raises:
        FileNotFoundError: if the file does not exist on disk.
    """
    abs_path = data_dir / image_path

    def _read() -> bytes:
        return abs_path.read_bytes()

    return await asyncio.to_thread(_read)
