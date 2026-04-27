"""End-to-end tests for the /api/auth/* endpoints.

Uses httpx.AsyncClient with ASGITransport so tests run entirely in-process
against the real FastAPI app backed by an isolated per-test SQLite database.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.config import get_settings
from backend.app.db.base import get_session_factory
from backend.app.main import create_app


@pytest.fixture
async def client(db_engine: AsyncEngine) -> AsyncClient:
    """Return an AsyncClient backed by a test app with an isolated DB.

    Migrations + bootstrap are both disabled on startup (see conftest env
    vars).  This fixture creates the app AFTER the db_engine fixture has
    patched HEARTH_DATABASE_URL via monkeypatch, so the app sees the test DB.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def bootstrapped_client(
    db_engine: AsyncEngine,
    client: AsyncClient,
) -> AsyncClient:
    """Like *client*, but with the bootstrap admin user already created."""
    factory = get_session_factory(db_engine)
    await ensure_bootstrap_admin(factory)
    return client


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


async def test_login_success_returns_user_and_sets_cookie(
    bootstrapped_client: AsyncClient,
) -> None:
    """Successful login returns UserResponse body and a hearth_session cookie."""
    settings = get_settings()
    async with bootstrapped_client as ac:
        response = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"
    assert body["must_change_password"] is True
    assert body["must_complete_google_setup"] is True
    assert "password_hash" not in body
    # Cookie must be present.
    assert settings.session_cookie_name in response.cookies


async def test_login_unknown_user_returns_401(
    bootstrapped_client: AsyncClient,
) -> None:
    """Login with an unknown username returns 401 without leaking info."""
    async with bootstrapped_client as ac:
        response = await ac.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "whatever"},
        )
    assert response.status_code == 401
    detail = response.json()["detail"]
    # Must not reveal whether the username exists.
    assert "not found" not in detail.lower()
    assert "user" not in detail.lower()
    assert detail == "Invalid credentials"


async def test_login_wrong_password_returns_401(
    bootstrapped_client: AsyncClient,
) -> None:
    """Login with correct username but wrong password returns 401."""
    async with bootstrapped_client as ac:
        response = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


async def test_me_with_valid_session_returns_user(
    bootstrapped_client: AsyncClient,
) -> None:
    """After login, GET /api/auth/me returns the same user data."""
    async with bootstrapped_client as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        me = await ac.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


async def test_me_without_session_returns_401(
    client: AsyncClient,
) -> None:
    """GET /api/auth/me without a session cookie returns 401."""
    async with client as ac:
        response = await ac.get("/api/auth/me")
    assert response.status_code == 401


async def test_me_with_invalid_cookie_returns_401(
    client: AsyncClient,
) -> None:
    """GET /api/auth/me with a bogus cookie value returns 401."""
    settings = get_settings()
    async with client as ac:
        ac.cookies.set(settings.session_cookie_name, "INVALID.GARBAGE.VALUE")
        response = await ac.get("/api/auth/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


async def test_logout_clears_cookie(
    bootstrapped_client: AsyncClient,
) -> None:
    """After logout, GET /api/auth/me should return 401."""
    async with bootstrapped_client as ac:
        await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        # Verify we're logged in.
        me_before = await ac.get("/api/auth/me")
        assert me_before.status_code == 200

        # Logout.
        logout = await ac.post("/api/auth/logout")
        assert logout.status_code == 200

        # /me should now 401.
        me_after = await ac.get("/api/auth/me")
    assert me_after.status_code == 401


async def test_logout_without_session_is_ok(
    client: AsyncClient,
) -> None:
    """Logout when not logged in should still return 2xx (idempotent)."""
    async with client as ac:
        response = await ac.post("/api/auth/logout")
    assert response.status_code in (200, 204)


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


async def test_change_password_success(
    bootstrapped_client: AsyncClient,
) -> None:
    """Full password-change flow: change works, session persists, old password rejected."""
    async with bootstrapped_client as ac:
        # 1. Login with default password.
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        # 2. Change password.
        change = await ac.post(
            "/api/auth/change-password",
            json={"current_password": "admin", "new_password": "newpassword123"},
        )
        assert change.status_code == 200
        body = change.json()
        assert body["must_change_password"] is False

        # 3. /me should still work (session rolls on).
        me = await ac.get("/api/auth/me")
        assert me.status_code == 200

        # 4. Old password no longer works.
        old_login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert old_login.status_code == 401

        # 5. New password works.
        new_login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "newpassword123"},
        )
    assert new_login.status_code == 200


async def test_change_password_wrong_current_returns_400(
    bootstrapped_client: AsyncClient,
) -> None:
    """Providing an incorrect current_password returns 400."""
    async with bootstrapped_client as ac:
        await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        response = await ac.post(
            "/api/auth/change-password",
            json={"current_password": "wrong", "new_password": "newpassword123"},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "Current password is incorrect"


async def test_change_password_too_short_returns_400(
    bootstrapped_client: AsyncClient,
) -> None:
    """new_password shorter than 8 characters returns 400."""
    async with bootstrapped_client as ac:
        await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        response = await ac.post(
            "/api/auth/change-password",
            json={"current_password": "admin", "new_password": "short"},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "New password must be at least 8 characters"


async def test_change_password_same_as_current_returns_400(
    bootstrapped_client: AsyncClient,
) -> None:
    """Setting new_password equal to current_password returns 400."""
    async with bootstrapped_client as ac:
        await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        response = await ac.post(
            "/api/auth/change-password",
            json={"current_password": "admin", "new_password": "admin"},
        )
    assert response.status_code == 400
    assert response.json()["detail"] == "New password must differ from current"
