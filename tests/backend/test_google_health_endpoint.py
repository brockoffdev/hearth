"""Tests for GET /api/google/health endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import OauthToken, User
from backend.app.google.health_state import mark_oauth_broken
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
async def bootstrapped_client(db_engine: AsyncEngine, client: AsyncClient) -> AsyncClient:
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)
    return client


async def _login_admin(ac: AsyncClient) -> None:
    resp = await ac.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200


async def _add_non_admin_user(db_engine: AsyncEngine) -> None:
    factory = get_session_factory(db_engine)
    async with factory() as session:
        session.add(
            User(
                username="regular",
                password_hash=hash_password("pass"),
                role="user",
            )
        )
        await session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_google_health_requires_auth(client: AsyncClient) -> None:
    """Unauthenticated request returns 401."""
    async with client as ac:
        resp = await ac.get("/api/google/health")
    assert resp.status_code == 401


async def test_google_health_returns_disconnected_when_no_token_row(
    bootstrapped_client: AsyncClient,
) -> None:
    """Returns connected=false when no oauth_tokens row exists."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/google/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["broken_reason"] is None
    assert data["broken_at"] is None


async def test_google_health_returns_connected_when_token_present_and_not_broken(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Returns connected=true when oauth_tokens row exists with no broken flag."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        session.add(
            OauthToken(
                id=1,
                refresh_token="rt",
                scopes="https://www.googleapis.com/auth/calendar",
            )
        )
        await session.commit()

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/google/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["broken_reason"] is None


async def test_google_health_returns_broken_when_flag_set(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Returns connected=false and broken_reason when the broken flag is set."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        session.add(
            OauthToken(
                id=1,
                refresh_token="rt",
                scopes="https://www.googleapis.com/auth/calendar",
            )
        )
        await session.commit()
        await mark_oauth_broken(session, "invalid_grant: token revoked")

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/google/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert "invalid_grant" in data["broken_reason"]
    assert data["broken_at"] is not None
