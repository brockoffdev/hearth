"""Tests for POST /api/setup/complete-google."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import FamilyMember, OauthToken, User
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


async def _add_oauth_token(db_engine: AsyncEngine) -> None:
    """Insert a valid OauthToken row (id=1)."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        session.add(
            OauthToken(
                id=1,
                refresh_token="valid-refresh-token",
                access_token="valid-access-token",
                scopes="https://www.googleapis.com/auth/calendar",
            )
        )
        await session.commit()


async def _map_all_family_members(db_engine: AsyncEngine, count: int = 5) -> None:
    """Set google_calendar_id on `count` family members (by sort_order)."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(FamilyMember).order_by(FamilyMember.sort_order)
        )
        members = list(result.scalars().all())
        for i, member in enumerate(members[:count]):
            member.google_calendar_id = f"cal-{i}@group.calendar.google.com"
        await session.commit()


# ---------------------------------------------------------------------------
# POST /api/setup/complete-google
# ---------------------------------------------------------------------------


async def test_complete_google_clears_flag(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Successful POST clears must_complete_google_setup and returns updated user."""
    await _add_oauth_token(db_engine)
    await _map_all_family_members(db_engine, count=5)

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post("/api/setup/complete-google")

    assert resp.status_code == 200
    body = resp.json()
    assert body["must_complete_google_setup"] is False

    # Verify the DB row was actually updated.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        admin = result.scalar_one()
    assert admin.must_complete_google_setup is False


async def test_complete_google_400_when_unmapped_family_members_exist(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """400 when only 4 of 5 family members are mapped."""
    await _add_oauth_token(db_engine)
    await _map_all_family_members(db_engine, count=4)  # only 4

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post("/api/setup/complete-google")

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "family members" in detail.lower()
    assert "calendar" in detail.lower()


async def test_complete_google_400_when_no_oauth_tokens(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """400 when all 5 members are mapped but there is no oauth_tokens row."""
    # Map all family members but do NOT add an OauthToken row.
    await _map_all_family_members(db_engine, count=5)

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post("/api/setup/complete-google")

    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "oauth" in detail.lower()


async def test_complete_google_requires_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin user gets 403 on POST /api/setup/complete-google."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        user = User(
            username="regular4",
            password_hash=hash_password("password123"),
            role="user",
            must_change_password=False,
            must_complete_google_setup=False,
        )
        session.add(user)
        await session.commit()

    async with bootstrapped_client as ac:
        login_resp = await ac.post(
            "/api/auth/login",
            json={"username": "regular4", "password": "password123"},
        )
        assert login_resp.status_code == 200
        resp = await ac.post("/api/setup/complete-google")

    assert resp.status_code == 403
