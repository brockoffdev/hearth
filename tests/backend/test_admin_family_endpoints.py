"""Tests for GET /api/admin/family and PATCH /api/admin/family/{member_id}."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import FamilyMember, User
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
# GET /api/admin/family
# ---------------------------------------------------------------------------


async def test_list_family_members_returns_seeded_5(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Admin GET /api/admin/family returns all 5 seeded rows in sort_order."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/admin/family")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 5

        # Verify the response contains the expected fields.
        names = [m["name"] for m in body]
        assert "Bryant" in names
        assert "Danielle" in names
        assert "Isabella" in names
        assert "Eliana" in names
        assert "Family" in names

        # Verify color hex fields are present and non-empty.
        for member in body:
            assert "id" in member
            assert "name" in member
            assert "color_hex_center" in member
            assert member["color_hex_center"].startswith("#")
            assert "google_calendar_id" in member


async def test_list_family_members_sorted_by_sort_order(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """GET /api/admin/family returns members in sort_order."""
    # Verify sort order from the DB matches the response order.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(FamilyMember).order_by(FamilyMember.sort_order)
        )
        db_members = list(result.scalars().all())

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/admin/family")

    body = resp.json()
    assert [m["id"] for m in body] == [m.id for m in db_members]


async def test_list_family_members_requires_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin user gets 403 on GET /api/admin/family."""
    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.get("/api/admin/family")

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/admin/family/{member_id}
# ---------------------------------------------------------------------------


async def test_patch_family_member_updates_calendar_id(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH /api/admin/family/1 sets google_calendar_id; subsequent GET shows updated value."""
    cal_id = "test@group.calendar.google.com"

    # Get the ID of the first member by sort_order.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(FamilyMember).order_by(FamilyMember.sort_order).limit(1)
        )
        first_member = result.scalar_one()
    member_id = first_member.id

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        patch_resp = await ac.patch(
            f"/api/admin/family/{member_id}",
            json={"google_calendar_id": cal_id},
        )

        assert patch_resp.status_code == 200
        body = patch_resp.json()
        assert body["google_calendar_id"] == cal_id
        assert body["id"] == member_id

        # Verify the GET also reflects the update (same session).
        get_resp = await ac.get("/api/admin/family")
        members_by_id = {m["id"]: m for m in get_resp.json()}
        assert members_by_id[member_id]["google_calendar_id"] == cal_id


async def test_patch_family_member_404(
    bootstrapped_client: AsyncClient,
) -> None:
    """PATCH /api/admin/family/9999 returns 404."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            "/api/admin/family/9999",
            json={"google_calendar_id": "cal@google.com"},
        )

    assert resp.status_code == 404


async def test_patch_family_member_can_clear_to_null(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """PATCH with google_calendar_id=null clears the calendar mapping."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(FamilyMember).order_by(FamilyMember.sort_order).limit(1)
        )
        first_member = result.scalar_one()
        # Pre-set a value first.
        first_member.google_calendar_id = "preset@google.com"
        await session.commit()
    member_id = first_member.id

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.patch(
            f"/api/admin/family/{member_id}",
            json={"google_calendar_id": None},
        )

    assert resp.status_code == 200
    assert resp.json()["google_calendar_id"] is None


async def test_patch_family_member_requires_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin user gets 403 on PATCH /api/admin/family/{id}."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(FamilyMember).order_by(FamilyMember.sort_order).limit(1)
        )
        first_member = result.scalar_one()
    member_id = first_member.id

    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.patch(
            f"/api/admin/family/{member_id}",
            json={"google_calendar_id": "cal@google.com"},
        )

    assert resp.status_code == 403
