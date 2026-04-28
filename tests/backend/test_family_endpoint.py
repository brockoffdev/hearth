"""Tests for GET /api/family — public (non-admin) family endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
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


async def _login_regular(ac: AsyncClient, db_engine: AsyncEngine) -> None:
    """Create and log in as a non-admin user."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_get_family_returns_all_members(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/family returns all 5 seeded family members in sort_order."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/family")

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 5

    names = [m["name"] for m in body]
    assert "Bryant" in names
    assert "Danielle" in names
    assert "Izzy" in names
    assert "Ellie" in names
    assert "Family" in names

    for member in body:
        assert "id" in member
        assert "name" in member
        assert "color_hex_center" in member
        assert member["color_hex_center"].startswith("#")


async def test_get_family_requires_auth(
    bootstrapped_client: AsyncClient,
) -> None:
    """GET /api/family returns 401 for unauthenticated requests."""
    async with bootstrapped_client as ac:
        resp = await ac.get("/api/family")

    assert resp.status_code == 401


async def test_get_family_works_for_non_admin_user(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin users can successfully call GET /api/family."""
    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.get("/api/family")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5
