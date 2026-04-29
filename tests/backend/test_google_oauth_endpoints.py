"""Tests for the /api/google/oauth/* endpoints.

All Google network calls are mocked — no real HTTP requests to Google in
these tests.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import FamilyMember, OauthToken, Setting, User
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
    """Log in as admin and store the session cookie on *ac*."""
    resp = await ac.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/google/oauth/credentials
# ---------------------------------------------------------------------------


async def test_oauth_credentials_persists_to_settings(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Posting credentials as admin persists them to the settings table."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post(
            "/api/google/oauth/credentials",
            json={"client_id": "test-client-id", "client_secret": "test-client-secret"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    # Verify settings were persisted.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        cred_keys = ["google_oauth_client_id", "google_oauth_client_secret"]
        result = await session.execute(
            select(Setting).where(Setting.key.in_(cred_keys))
        )
        rows = {row.key: row.value for row in result.scalars()}
    assert rows.get("google_oauth_client_id") == "test-client-id"
    assert rows.get("google_oauth_client_secret") == "test-client-secret"


async def test_oauth_credentials_non_admin_returns_403(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin user gets 403 when trying to post credentials."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        regular_user = User(
            username="regular",
            password_hash=hash_password("password123"),
            role="user",
            must_change_password=False,
            must_complete_google_setup=False,
        )
        session.add(regular_user)
        await session.commit()

    async with bootstrapped_client as ac:
        # Log in as regular user.
        login_resp = await ac.post(
            "/api/auth/login",
            json={"username": "regular", "password": "password123"},
        )
        assert login_resp.status_code == 200

        resp = await ac.post(
            "/api/google/oauth/credentials",
            json={"client_id": "id", "client_secret": "secret"},
        )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/google/oauth/init
# ---------------------------------------------------------------------------


async def _pre_populate_creds(db_engine: AsyncEngine) -> None:
    """Write client_id + client_secret into settings so init can proceed."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        for key, value in [
            ("google_oauth_client_id", "fake-client-id"),
            ("google_oauth_client_secret", "fake-client-secret"),
        ]:
            result = await session.execute(select(Setting).where(Setting.key == key))
            row = result.scalar_one_or_none()
            if row is None:
                session.add(Setting(key=key, value=value))
            else:
                row.value = value
        await session.commit()


_FAKE_AUTH_URL = "https://accounts.google.com/o/oauth2/auth?fake=1"


def _make_mock_flow(auth_url: str = _FAKE_AUTH_URL) -> MagicMock:
    """Return a mock Flow whose get_authorization_url path returns *auth_url*.

    `code_verifier` is set to a real string so the init handler can persist
    it to the settings table (the production path stores it for the matching
    callback's PKCE exchange).
    """
    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = (auth_url, "state123")
    mock_flow.code_verifier = "test-code-verifier-not-real"
    return mock_flow


async def test_oauth_init_returns_authorization_url(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """init returns an authorization_url and stores the pending state."""
    await _pre_populate_creds(db_engine)

    mock_flow = _make_mock_flow()
    with (
        patch("backend.app.api.google.build_flow", return_value=mock_flow),
        patch(
            "backend.app.api.google.get_authorization_url",
            return_value=_FAKE_AUTH_URL,
        ),
    ):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.post("/api/google/oauth/init")

    assert resp.status_code == 200
    body = resp.json()
    assert "authorization_url" in body
    assert body["authorization_url"] == _FAKE_AUTH_URL

    # Verify pending state was stored.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == "google_oauth_pending_state")
        )
        row = result.scalar_one_or_none()
    assert row is not None
    assert len(row.value) > 0


async def test_oauth_init_400_when_credentials_missing(
    bootstrapped_client: AsyncClient,
) -> None:
    """init returns 400 when no credentials have been saved."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.post("/api/google/oauth/init")

    assert resp.status_code == 400
    assert "credentials not configured" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /api/google/oauth/callback
# ---------------------------------------------------------------------------


async def _run_init(
    ac: AsyncClient,
    db_engine: AsyncEngine,
) -> str:
    """Run the init flow and return the stored pending state value."""
    await _pre_populate_creds(db_engine)

    mock_flow = _make_mock_flow()
    with (
        patch("backend.app.api.google.build_flow", return_value=mock_flow),
        patch(
            "backend.app.api.google.get_authorization_url",
            return_value=_FAKE_AUTH_URL,
        ),
    ):
        resp = await ac.post("/api/google/oauth/init")
    assert resp.status_code == 200

    # Retrieve the stored state.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(
            select(Setting).where(Setting.key == "google_oauth_pending_state")
        )
        row = result.scalar_one_or_none()
    assert row is not None
    return row.value


async def test_oauth_callback_state_mismatch_redirects_with_error(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Callback with wrong state returns a 302 redirect with status=error."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        await _run_init(ac, db_engine)

        resp = await ac.get(
            "/api/google/oauth/callback",
            params={"code": "auth-code-123", "state": "WRONG_STATE"},
            follow_redirects=False,
        )

    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "status=error" in location


async def test_oauth_callback_success_persists_tokens_and_redirects(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Successful callback persists tokens and redirects to /setup/google?status=ok."""
    fake_tokens: dict[str, Any] = {
        "access_token": "ya29.fake-access-token",
        "refresh_token": "1//fake-refresh-token",
        "expires_at": 9999999999.0,
        "scopes": ["https://www.googleapis.com/auth/calendar"],
    }

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        state = await _run_init(ac, db_engine)

        mock_flow = _make_mock_flow()
        with (
            patch("backend.app.api.google.build_flow", return_value=mock_flow),
            patch("backend.app.api.google.fetch_token", return_value=fake_tokens),
        ):
            resp = await ac.get(
                "/api/google/oauth/callback",
                params={"code": "auth-code-123", "state": state},
                follow_redirects=False,
            )

    # Verify redirect destination.
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "status=ok" in location
    assert "status=error" not in location

    # Verify tokens were persisted.
    factory = get_session_factory(db_engine)
    async with factory() as session:
        result = await session.execute(select(OauthToken).where(OauthToken.id == 1))
        token_row = result.scalar_one_or_none()

    assert token_row is not None
    assert token_row.access_token == "ya29.fake-access-token"
    assert token_row.refresh_token == "1//fake-refresh-token"
    assert token_row.scopes == "https://www.googleapis.com/auth/calendar"

    # Verify pending state was cleared.
    async with factory() as session:
        state_result = await session.execute(
            select(Setting).where(Setting.key == "google_oauth_pending_state")
        )
        state_row = state_result.scalar_one_or_none()
    # Should be either None or an empty string (we upsert with "").
    assert state_row is None or state_row.value == ""


# ---------------------------------------------------------------------------
# GET /api/google/oauth/state
# ---------------------------------------------------------------------------


async def test_oauth_state_no_tokens_no_mappings(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """No tokens and no calendar mappings → connected=false, calendars_mapped=false."""
    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/google/oauth/state")

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is False
    assert body["calendars_mapped"] is False
    assert body["refresh_token_present"] is False


async def test_oauth_state_tokens_stored_no_mappings(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Tokens stored, no calendar mappings → connected=true, calendars_mapped=false."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        session.add(
            OauthToken(
                id=1,
                refresh_token="fake-refresh",
                access_token="fake-access",
                scopes="https://www.googleapis.com/auth/calendar",
            )
        )
        await session.commit()

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/google/oauth/state")

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["refresh_token_present"] is True
    assert body["calendars_mapped"] is False
    assert body["scopes"] == ["https://www.googleapis.com/auth/calendar"]


async def test_oauth_state_tokens_and_all_members_mapped(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Tokens + all family members mapped → connected=true, calendars_mapped=true."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        session.add(
            OauthToken(
                id=1,
                refresh_token="fake-refresh",
                access_token="fake-access",
                scopes="https://www.googleapis.com/auth/calendar",
            )
        )
        # The migration seeds 5 family members — update all of them.
        result = await session.execute(select(FamilyMember))
        members = list(result.scalars().all())
        assert len(members) > 0, "Expected seeded family members from migration"
        for member in members:
            member.google_calendar_id = f"cal-{member.id}@group.calendar.google.com"
        await session.commit()

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/google/oauth/state")

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["calendars_mapped"] is True


async def test_oauth_state_calendars_mapped_vacuously_true_when_no_members(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Tokens stored, zero family members → connected=true, calendars_mapped=true.

    ``all(... for m in [])`` is vacuously True — no member can be unmapped if
    there are no members.  This guards against a regression to ``bool(members)
    and all(...)`` which would return False on empty.
    """
    factory = get_session_factory(db_engine)
    async with factory() as session:
        session.add(
            OauthToken(
                id=1,
                refresh_token="fake-refresh",
                access_token="fake-access",
                scopes="https://www.googleapis.com/auth/calendar",
            )
        )
        # Delete all seeded family members so the list is empty.
        result = await session.execute(select(FamilyMember))
        for member in result.scalars().all():
            await session.delete(member)
        await session.commit()

    async with bootstrapped_client as ac:
        await _login_admin(ac)
        resp = await ac.get("/api/google/oauth/state")

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["calendars_mapped"] is True


# ---------------------------------------------------------------------------
# get_active_credentials — token refresh persistence
# ---------------------------------------------------------------------------


async def test_get_active_credentials_persists_refresh(
    db_engine: AsyncEngine,
) -> None:
    """get_active_credentials updates the OauthToken row when the access token is refreshed.

    Scenario: the stored access_token is expired.  ``credentials_for`` is
    mocked to return a new token and set ``was_refreshed=True``.  After the
    call the OauthToken row must contain the refreshed access_token and
    expires_at.
    """
    from backend.app.api.google import get_active_credentials

    refreshed_token = "ya29.refreshed-access-token"
    new_expiry = datetime(2099, 1, 1, 0, 0, 0)  # naive UTC, far future

    factory = get_session_factory(db_engine)
    async with factory() as session:
        # Pre-populate with an expired access token and a valid refresh token.
        session.add(
            OauthToken(
                id=1,
                refresh_token="valid-refresh-token",
                access_token="expired-access-token",
                expires_at=datetime(2000, 1, 1),  # clearly in the past
                scopes="https://www.googleapis.com/auth/calendar",
            )
        )
        # Ensure credentials settings are present.
        for key, value in [
            ("google_oauth_client_id", "test-client-id"),
            ("google_oauth_client_secret", "test-client-secret"),
        ]:
            from backend.app.db.models import Setting as SettingModel

            session.add(SettingModel(key=key, value=value))
        await session.commit()

    # Build a Credentials-like mock that represents the post-refresh state.
    mock_creds = MagicMock(spec=Credentials)
    mock_creds.token = refreshed_token
    mock_creds.expiry = new_expiry

    with patch(
        "backend.app.api.google.credentials_for",
        return_value=(mock_creds, True),
    ):
        async with factory() as session:
            await get_active_credentials(session)

    # Verify the DB row was updated with the refreshed values.
    async with factory() as session:
        result = await session.execute(select(OauthToken).where(OauthToken.id == 1))
        token_row = result.scalar_one_or_none()

    assert token_row is not None
    assert token_row.access_token == refreshed_token
    assert token_row.expires_at == new_expiry
