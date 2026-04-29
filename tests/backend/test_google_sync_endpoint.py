"""Tests for POST /api/google/sync — manual GCal sync trigger."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import User
from backend.app.main import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(db_engine: AsyncEngine) -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def bootstrapped_client(
    db_engine: AsyncEngine,
    client: AsyncClient,
) -> AsyncClient:
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)
    return client


async def _login_admin(ac: AsyncClient) -> None:
    resp = await ac.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200


async def _create_and_login_user(ac: AsyncClient, db_engine: AsyncEngine) -> None:
    """Create (idempotent) and log in as a plain user."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        existing = await session.execute(select(User).where(User.username == "regular"))
        if existing.scalar_one_or_none() is None:
            user = User(
                username="regular",
                password_hash=hash_password("password123"),
                role="user",
                must_change_password=False,
                must_complete_google_setup=False,
            )
            session.add(user)
            await session.commit()

    resp = await ac.post(
        "/api/auth/login",
        json={"username": "regular", "password": "password123"},
    )
    assert resp.status_code == 200


_MOCK_STATS: dict[str, int] = {
    "imported": 2,
    "updated": 1,
    "deleted": 0,
    "skipped": 0,
    "errors": 0,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_admin_can_trigger_sync(
    db_engine: AsyncEngine,
    bootstrapped_client: AsyncClient,
) -> None:
    """Admin POST /api/google/sync returns the stats dict."""
    await _login_admin(bootstrapped_client)

    with patch(
        "backend.app.api.google.sync_from_gcal",
        new=AsyncMock(return_value=_MOCK_STATS),
    ):
        resp = await bootstrapped_client.post("/api/google/sync")

    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 2
    assert data["updated"] == 1
    assert set(data.keys()) == {"imported", "updated", "deleted", "skipped", "errors"}


async def test_non_admin_gets_403(
    db_engine: AsyncEngine,
    bootstrapped_client: AsyncClient,
) -> None:
    """Non-admin authenticated user receives 403."""
    await _create_and_login_user(bootstrapped_client, db_engine)

    resp = await bootstrapped_client.post("/api/google/sync")

    assert resp.status_code == 403


async def test_unauthenticated_gets_401(
    db_engine: AsyncEngine,
    client: AsyncClient,
) -> None:
    """Unauthenticated request receives 401."""
    resp = await client.post("/api/google/sync")

    assert resp.status_code == 401
