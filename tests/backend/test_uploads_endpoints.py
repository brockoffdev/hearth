"""End-to-end tests for the /api/uploads/* endpoints.

Uses httpx.AsyncClient with ASGITransport against a real FastAPI app backed
by an isolated per-test SQLite database (via db_engine from conftest.py).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

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
from backend.app.uploads.queue import _reset_for_tests

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


@pytest.fixture(autouse=True)
def reset_queue() -> None:
    """Clear process-wide queue state before each test to avoid leakage."""
    _reset_for_tests()


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
    # id is now a string (API contract: stringified int)
    assert isinstance(body["id"], str)
    # A newly-created upload has status='queued' on the row, but the API maps
    # queued → 'processing' (queued is a sub-state of processing in the API shape).
    assert body["status"] == "processing"
    assert body["image_path"].startswith("uploads/")
    assert body["uploaded_at"]  # ISO string, non-empty
    assert body["url"] == f"/api/uploads/{body['id']}/photo"
    # New Phase 3.5 fields present.
    assert body["thumbLabel"]
    assert "startedAt" in body
    # Phase 3.5: queued row now has current_stage='queued' (set explicitly at POST time).
    assert body["current_stage"] == "queued"
    assert body["completed_stages"] == []

    # File must exist on disk.
    disk_path = settings.data_dir / body["image_path"]
    assert disk_path.exists()
    assert disk_path.read_bytes() == _FAKE_JPEG_BYTES

    # DB row must exist with queued status.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(Upload).where(Upload.id == int(body["id"])))
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
    # id is now a string; convert to int for DB lookup.
    upload_id = int(resp.json()["id"])

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

        ids: list[str] = []
        for _ in range(3):
            r = await ac.post("/api/uploads", files=_photo_payload())
            assert r.status_code == 201
            ids.append(r.json()["id"])  # string ids

        resp = await ac.get("/api/uploads")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    returned_ids = [item["id"] for item in body]
    # Most recently created should come first.
    assert returned_ids == list(reversed(ids))
    # Verify new Phase 3.5 camelCase fields are present on list items.
    for item in body:
        assert "thumbLabel" in item
        assert "status" in item
        assert item["status"] in ("processing", "completed", "failed")


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
        upload_id = post_resp.json()["id"]  # string

        get_resp = await ac.get(f"/api/uploads/{upload_id}")

    assert get_resp.status_code == 200
    body = get_resp.json()
    # id is stringified in the API response.
    assert body["id"] == upload_id
    # queued rows map to 'processing' in the API shape.
    assert body["status"] == "processing"
    # New Phase 3.5 fields.
    assert body["thumbLabel"]
    assert "startedAt" in body
    assert "current_stage" in body
    assert "completed_stages" in body
    # Legacy fields still present for Phase 3 frontend.
    assert body["url"]
    assert body["uploaded_at"]
    assert body["image_path"]


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
        upload_id = post_resp.json()["id"]  # string

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
        upload_id = post_resp.json()["id"]  # string

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
        upload_id = body["id"]  # string

        # Delete the file from disk.
        disk_path = settings.data_dir / body["image_path"]
        disk_path.unlink()

        photo_resp = await ac.get(f"/api/uploads/{upload_id}/photo")

    assert photo_resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 3.5: new shape + legacy field tests
# ---------------------------------------------------------------------------


async def test_get_upload_new_fields_present_on_queued_row(
    bootstrapped_client: AsyncClient,
) -> None:
    """A just-uploaded row returns status='processing', completedStages=[], legacy fields."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        post_resp = await ac.post("/api/uploads", files=_photo_payload())
        assert post_resp.status_code == 201
        upload_id = post_resp.json()["id"]

        get_resp = await ac.get(f"/api/uploads/{upload_id}")

    assert get_resp.status_code == 200
    body = get_resp.json()

    # API maps queued → processing.
    assert body["status"] == "processing"
    # id is stringified.
    assert body["id"] == upload_id
    assert isinstance(body["id"], str)

    # New fields.
    assert "thumbLabel" in body
    assert body["thumbLabel"]  # non-empty string
    assert "startedAt" in body
    assert body["startedAt"] is not None  # processing row has startedAt

    # Processing-only fields present (snake_case — no alias on these).
    assert body["completed_stages"] == []
    # Phase 3.5: queued row now has current_stage='queued' set at POST time.
    assert body["current_stage"] == "queued"

    # Legacy fields for Phase 3 frontend.
    assert body["url"] == f"/api/uploads/{upload_id}/photo"
    assert body["image_path"].startswith("uploads/")
    assert body["uploaded_at"]  # ISO string


async def test_get_upload_camelcase_aliases_serialize_correctly(
    bootstrapped_client: AsyncClient,
) -> None:
    """Response uses camelCase field names per the design TS shape."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        post_resp = await ac.post("/api/uploads", files=_photo_payload())
        assert post_resp.status_code == 201
        upload_id = post_resp.json()["id"]

        get_resp = await ac.get(f"/api/uploads/{upload_id}")

    body = get_resp.json()
    # camelCase aliases from the Pydantic model / TS shape.
    assert "thumbLabel" in body
    assert "startedAt" in body
    assert "finishedAt" in body
    # snake_case fields kept as-is (match the TS shape).
    assert "current_stage" in body
    assert "completed_stages" in body
    assert "remaining_seconds" in body
    # camelCase aliases.
    assert "cellProgress" in body
    assert "totalCells" in body
    assert "queuedBehind" in body
    assert "durationSec" in body


# ---------------------------------------------------------------------------
# Phase 3.5 Task B: queue exposure in POST response
# ---------------------------------------------------------------------------


async def test_post_upload_sets_current_stage_queued(
    bootstrapped_client: AsyncClient,
) -> None:
    """POST /api/uploads creates a queued row with current_stage='queued'."""
    # Patch run_pipeline_for_upload so the background task is a no-op coroutine.
    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post("/api/uploads", files=_photo_payload())

    assert resp.status_code == 201
    body = resp.json()
    # Queued row exposes current_stage='queued' and queuedBehind=0 (head).
    assert body["current_stage"] == "queued"
    assert body["queuedBehind"] == 0


async def test_post_upload_queued_behind_increments_for_second_upload(
    bootstrapped_client: AsyncClient,
) -> None:
    """Second POST while first is queued reports queuedBehind=1."""
    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp1 = await ac.post("/api/uploads", files=_photo_payload())
            resp2 = await ac.post("/api/uploads", files=_photo_payload())

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["queuedBehind"] == 0
    assert resp2.json()["queuedBehind"] == 1


# ---------------------------------------------------------------------------
# Phase 3.5 Task B: DELETE /api/uploads/{id} — cancel queued upload
# ---------------------------------------------------------------------------


async def test_delete_upload_cancels_queued_row(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
    tmp_path: Path,
) -> None:
    """DELETE on a queued upload returns 204, removes the DB row, and deletes the file."""
    factory = get_session_factory(db_engine)
    settings = get_settings()

    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post("/api/uploads", files=_photo_payload())
            assert resp.status_code == 201
            body = resp.json()
            upload_id = body["id"]
            image_path = body["image_path"]

            # File exists on disk before cancel.
            disk_path = settings.data_dir / image_path
            assert disk_path.exists()

            delete_resp = await ac.delete(f"/api/uploads/{upload_id}")

    assert delete_resp.status_code == 204

    # Row should be gone.
    async with factory() as session:
        result = await session.execute(select(Upload).where(Upload.id == int(upload_id)))
        row = result.scalar_one_or_none()
    assert row is None

    # File should be deleted.
    assert not disk_path.exists()


async def test_delete_upload_400_when_processing(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """DELETE on a processing upload returns 400."""
    factory = get_session_factory(db_engine)

    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post("/api/uploads", files=_photo_payload())
            assert resp.status_code == 201
            upload_id = int(resp.json()["id"])

            # Manually set status to processing.
            async with factory() as session:
                row = await session.get(Upload, upload_id)
                row.status = "processing"  # type: ignore[union-attr]
                await session.commit()

            delete_resp = await ac.delete(f"/api/uploads/{upload_id}")

    assert delete_resp.status_code == 400
    assert "queued" in delete_resp.json()["detail"].lower()


async def test_delete_upload_403_when_other_user(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """User B cannot cancel User A's upload."""
    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post("/api/uploads", files=_photo_payload())
            assert resp.status_code == 201
            upload_id = resp.json()["id"]

            # Switch to User B.
            await ac.post("/api/auth/logout")
            await _create_and_login_second_user(ac, db_engine)

            delete_resp = await ac.delete(f"/api/uploads/{upload_id}")

    assert delete_resp.status_code == 403


async def test_delete_upload_404_for_unknown(
    bootstrapped_client: AsyncClient,
) -> None:
    """DELETE on a non-existent upload returns 404."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.delete("/api/uploads/999999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 3.5 Task B: POST /api/uploads/{id}/retry — retry failed upload
# ---------------------------------------------------------------------------


async def test_retry_upload_creates_new_row(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """POST /retry on a failed upload creates a new row; original stays as failed."""
    factory = get_session_factory(db_engine)

    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            # Create an upload and mark it failed.
            resp = await ac.post("/api/uploads", files=_photo_payload())
            assert resp.status_code == 201
            failed_id = int(resp.json()["id"])

            async with factory() as session:
                row = await session.get(Upload, failed_id)
                assert row is not None
                row.status = "failed"
                row.error = "test error"
                await session.commit()

            retry_resp = await ac.post(f"/api/uploads/{failed_id}/retry")

    assert retry_resp.status_code == 201
    new_body = retry_resp.json()
    new_id = int(new_body["id"])

    # New row must have a different id.
    assert new_id != failed_id

    # New row should be queued/processing.
    assert new_body["status"] == "processing"
    assert new_body["current_stage"] == "queued"

    # Original row must still exist with status='failed'.
    async with factory() as session:
        original = await session.get(Upload, failed_id)
        assert original is not None
        assert original.status == "failed"


async def test_retry_upload_shares_photo_file(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Retried upload row shares the same image_path as the failed row."""
    factory = get_session_factory(db_engine)

    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post("/api/uploads", files=_photo_payload())
            assert resp.status_code == 201
            failed_id = int(resp.json()["id"])
            original_image_path = resp.json()["image_path"]

            async with factory() as session:
                row = await session.get(Upload, failed_id)
                row.status = "failed"  # type: ignore[union-attr]
                await session.commit()

            retry_resp = await ac.post(f"/api/uploads/{failed_id}/retry")

    assert retry_resp.status_code == 201
    assert retry_resp.json()["image_path"] == original_image_path


async def test_retry_upload_400_when_not_failed(
    bootstrapped_client: AsyncClient,
) -> None:
    """POST /retry on a non-failed upload returns 400."""
    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post("/api/uploads", files=_photo_payload())
            assert resp.status_code == 201
            upload_id = resp.json()["id"]

            # Upload is queued (not failed) — retry should fail.
            retry_resp = await ac.post(f"/api/uploads/{upload_id}/retry")

    assert retry_resp.status_code == 400
    assert "failed" in retry_resp.json()["detail"].lower()


async def test_retry_upload_403_when_other_user(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """User B cannot retry User A's failed upload."""
    factory = get_session_factory(db_engine)

    async def _noop(*args: object, **kwargs: object) -> None:
        pass

    with patch("backend.app.api.uploads.run_pipeline_for_upload", _noop):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post("/api/uploads", files=_photo_payload())
            assert resp.status_code == 201
            failed_id = int(resp.json()["id"])

            async with factory() as session:
                row = await session.get(Upload, failed_id)
                row.status = "failed"  # type: ignore[union-attr]
                await session.commit()

            await ac.post("/api/auth/logout")
            await _create_and_login_second_user(ac, db_engine)

            retry_resp = await ac.post(f"/api/uploads/{failed_id}/retry")

    assert retry_resp.status_code == 403
