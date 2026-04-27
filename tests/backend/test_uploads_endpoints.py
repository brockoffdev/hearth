"""End-to-end tests for the /api/uploads/* endpoints.

Uses httpx.AsyncClient with ASGITransport against a real FastAPI app backed
by an isolated per-test SQLite database (via db_engine from conftest.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.config import get_settings
from backend.app.db.base import get_session_factory
from backend.app.db.models import Upload, User
from backend.app.main import create_app

# ---------------------------------------------------------------------------
# Minimal fake JPEG — just the JFIF magic bytes; backend doesn't decode it.
# ---------------------------------------------------------------------------
_FAKE_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xd9"  # EOI marker — technically valid tiny JPEG
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(
    db_engine: AsyncEngine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncClient:
    """AsyncClient backed by a fresh app with isolated DB + temp data_dir."""
    monkeypatch.setenv("HEARTH_DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def bootstrapped_client(
    db_engine: AsyncEngine,
    client: AsyncClient,
) -> AsyncClient:
    """client with bootstrap admin already inserted."""
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)
    return client


async def _login_admin(ac: AsyncClient) -> None:
    resp = await ac.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200


async def _create_and_login_second_user(
    ac: AsyncClient,
    db_engine: AsyncEngine,
    username: str = "other",
) -> User:
    """Insert a second non-admin user and log in as them; return the User row."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        user = User(
            username=username,
            password_hash=hash_password("password123"),
            role="user",
            must_change_password=False,
            must_complete_google_setup=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    resp = await ac.post(
        "/api/auth/login",
        json={"username": username, "password": "password123"},
    )
    assert resp.status_code == 200
    return user


def _photo_payload(
    content_type: str = "image/jpeg",
    data: bytes = _FAKE_JPEG_BYTES,
    field: str = "photo",
) -> dict[str, tuple[str, bytes, str]]:
    return {field: ("test.jpg", data, content_type)}


# ---------------------------------------------------------------------------
# POST /api/uploads
# ---------------------------------------------------------------------------


async def test_post_upload_creates_row_and_stores_file(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """A valid multipart POST creates a DB row and stores the file on disk."""
    settings = get_settings()
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post("/api/uploads", files=_photo_payload())

    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert body["status"] == "queued"
    assert body["image_path"].startswith("uploads/")
    assert body["uploaded_at"]  # ISO string, non-empty
    assert body["url"] == f"/api/uploads/{body['id']}/photo"

    # File must exist on disk.
    disk_path = settings.data_dir / body["image_path"]
    assert disk_path.exists()
    assert disk_path.read_bytes() == _FAKE_JPEG_BYTES

    # DB row must exist.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(Upload).where(Upload.id == body["id"]))
        row = result.scalar_one_or_none()
    assert row is not None
    assert row.status == "queued"


async def test_post_upload_requires_auth(
    bootstrapped_client: AsyncClient,
) -> None:
    """Unauthenticated POST returns 401."""
    async with bootstrapped_client as ac:
        resp = await ac.post("/api/uploads", files=_photo_payload())
    assert resp.status_code == 401


async def test_post_upload_rejects_non_image(
    bootstrapped_client: AsyncClient,
) -> None:
    """Uploading a non-image content-type returns 400."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/uploads",
            files={"photo": ("file.txt", b"hello world", "text/plain")},
        )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Only image uploads are supported"


async def test_post_upload_rejects_oversized(
    bootstrapped_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Body larger than max_upload_bytes returns 413."""
    # Reduce the limit to 10 bytes so the test doesn't need to allocate 25 MB.
    monkeypatch.setenv("HEARTH_MAX_UPLOAD_BYTES", "10")
    get_settings.cache_clear()

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/uploads",
            files={"photo": ("big.jpg", b"\xff\xd8" * 20, "image/jpeg")},
        )
    assert resp.status_code == 413


async def test_post_upload_assigns_user_id_to_current_user(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """The Upload row's user_id matches the logged-in user's id."""
    factory = get_session_factory(db_engine)
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post("/api/uploads", files=_photo_payload())

    assert resp.status_code == 201
    upload_id = resp.json()["id"]

    async with factory() as session:
        result = await session.execute(select(Upload).where(Upload.id == upload_id))
        row = result.scalar_one()
        user_result = await session.execute(
            select(User).where(User.username == "admin")
        )
        admin_user = user_result.scalar_one()

    assert row.user_id == admin_user.id


# ---------------------------------------------------------------------------
# GET /api/uploads
# ---------------------------------------------------------------------------


async def test_get_uploads_lists_users_uploads_desc(
    bootstrapped_client: AsyncClient,
) -> None:
    """POST 3 uploads; list endpoint returns 3 items in reverse-chron order."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)

        ids: list[int] = []
        for _ in range(3):
            r = await ac.post("/api/uploads", files=_photo_payload())
            assert r.status_code == 201
            ids.append(r.json()["id"])

        resp = await ac.get("/api/uploads")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    returned_ids = [item["id"] for item in body]
    # Most recently created should come first.
    assert returned_ids == list(reversed(ids))


# ---------------------------------------------------------------------------
# GET /api/uploads/{id}
# ---------------------------------------------------------------------------


async def test_get_upload_returns_metadata(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        post_resp = await ac.post("/api/uploads", files=_photo_payload())
        assert post_resp.status_code == 201
        upload_id = post_resp.json()["id"]

        get_resp = await ac.get(f"/api/uploads/{upload_id}")

    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["id"] == upload_id
    assert body["status"] == "queued"


async def test_get_upload_404_for_unknown_id(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/uploads/999999")
    assert resp.status_code == 404


async def test_get_upload_403_when_other_users_upload(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """User B cannot see User A's upload."""
    async with bootstrapped_client as ac:
        # User A (admin) uploads a photo.
        await _login_admin(ac)
        post_resp = await ac.post("/api/uploads", files=_photo_payload())
        assert post_resp.status_code == 201
        upload_id = post_resp.json()["id"]

        # Switch to User B.
        await ac.post("/api/auth/logout")
        await _create_and_login_second_user(ac, db_engine)

        resp = await ac.get(f"/api/uploads/{upload_id}")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/uploads/{id}/photo
# ---------------------------------------------------------------------------


async def test_get_photo_returns_bytes_with_correct_content_type(
    bootstrapped_client: AsyncClient,
) -> None:
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        post_resp = await ac.post("/api/uploads", files=_photo_payload())
        assert post_resp.status_code == 201
        upload_id = post_resp.json()["id"]

        photo_resp = await ac.get(f"/api/uploads/{upload_id}/photo")

    assert photo_resp.status_code == 200
    assert photo_resp.headers["content-type"].startswith("image/jpeg")
    assert photo_resp.content == _FAKE_JPEG_BYTES


async def test_get_photo_404_when_file_missing(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """DB row exists but file was deleted from disk → 404."""
    settings = get_settings()

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        post_resp = await ac.post("/api/uploads", files=_photo_payload())
        assert post_resp.status_code == 201
        body = post_resp.json()
        upload_id = body["id"]

        # Delete the file from disk.
        disk_path = settings.data_dir / body["image_path"]
        disk_path.unlink()

        photo_resp = await ac.get(f"/api/uploads/{upload_id}/photo")

    assert photo_resp.status_code == 404
