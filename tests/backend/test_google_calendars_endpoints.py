"""Tests for GET /api/google/calendars and POST /api/google/calendars."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from google.oauth2.credentials import Credentials
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


def _fake_creds() -> MagicMock:
    return MagicMock(spec=Credentials)


_SAMPLE_CALENDARS: list[dict[str, Any]] = [
    {"id": "primary@gmail.com", "summary": "Bryant", "primary": True, "accessRole": "owner"},
    {
        "id": "cal1@group.calendar.google.com",
        "summary": "Family",
        "primary": False,
        "accessRole": "owner",
    },
    {
        "id": "cal2@group.calendar.google.com",
        "summary": "Danielle",
        "primary": False,
        "accessRole": "writer",
    },
]

# ---------------------------------------------------------------------------
# GET /api/google/calendars
# ---------------------------------------------------------------------------


async def test_list_calendars_returns_calendars_when_connected(
    bootstrapped_client: AsyncClient,
) -> None:
    """GET /api/google/calendars returns the 3 calendars from the mock."""
    fake_creds = _fake_creds()
    with (
        patch(
            "backend.app.api.google.get_active_credentials",
            new=AsyncMock(return_value=fake_creds),
        ),
        patch(
            "backend.app.api.google.list_calendars",
            new=AsyncMock(return_value=_SAMPLE_CALENDARS),
        ),
    ):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.get("/api/google/calendars")

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 3
    ids = [c["id"] for c in body]
    assert "primary@gmail.com" in ids
    assert "cal1@group.calendar.google.com" in ids


async def test_list_calendars_400_when_not_connected(
    bootstrapped_client: AsyncClient,
) -> None:
    """GET /api/google/calendars returns 400 when get_active_credentials raises."""
    with patch(
        "backend.app.api.google.get_active_credentials",
        new=AsyncMock(
            side_effect=HTTPException(
                status_code=400,
                detail="Google OAuth not connected — complete the setup wizard first",
            )
        ),
    ):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.get("/api/google/calendars")

    assert resp.status_code == 400
    assert "not connected" in resp.json()["detail"].lower()


async def test_list_calendars_requires_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin user gets 403 on GET /api/google/calendars."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        user = User(
            username="regular2",
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
            json={"username": "regular2", "password": "password123"},
        )
        assert login_resp.status_code == 200
        resp = await ac.get("/api/google/calendars")

    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/google/calendars
# ---------------------------------------------------------------------------


async def test_create_calendar_returns_new_calendar(
    bootstrapped_client: AsyncClient,
) -> None:
    """POST /api/google/calendars creates a calendar and returns it."""
    new_cal = {"id": "newcal@group.calendar.google.com", "summary": "Family"}
    fake_creds = _fake_creds()
    with (
        patch(
            "backend.app.api.google.get_active_credentials",
            new=AsyncMock(return_value=fake_creds),
        ),
        patch(
            "backend.app.api.google.create_calendar",
            new=AsyncMock(return_value=new_cal),
        ),
    ):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post(
                "/api/google/calendars",
                json={"summary": "Family"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "newcal@group.calendar.google.com"
    assert body["summary"] == "Family"


async def test_create_calendar_requires_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin user gets 403 on POST /api/google/calendars."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        user = User(
            username="regular3",
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
            json={"username": "regular3", "password": "password123"},
        )
        assert login_resp.status_code == 200
        resp = await ac.post(
            "/api/google/calendars",
            json={"summary": "Family"},
        )

    assert resp.status_code == 403


async def test_create_calendar_validates_summary(
    bootstrapped_client: AsyncClient,
) -> None:
    """POST /api/google/calendars with empty summary returns 422."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/google/calendars",
            json={"summary": ""},
        )

    assert resp.status_code == 422
