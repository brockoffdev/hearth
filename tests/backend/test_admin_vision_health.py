"""Tests for GET /api/admin/vision/health — Phase 5 Task C."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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


async def test_vision_health_returns_healthy_when_provider_responds(
    bootstrapped_client: AsyncClient,
) -> None:
    """Admin GET /api/admin/vision/health returns 200 with healthy=true when provider responds."""
    with patch(
        "backend.app.api.admin.get_vision_provider"
    ) as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.name = "ollama:qwen2.5-vl:7b"
        mock_provider.health_check = AsyncMock(return_value=True)
        mock_factory.return_value = mock_provider

        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.get("/api/admin/vision/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is True
    assert body["error"] is None
    assert body["provider"] == "ollama"
    assert body["model"] == "qwen2.5-vl:7b"
    assert body["name"] == "ollama:qwen2.5-vl:7b"


async def test_vision_health_returns_unhealthy_when_provider_fails(
    bootstrapped_client: AsyncClient,
) -> None:
    """health_check() returning False yields 200 + healthy=false."""
    with patch(
        "backend.app.api.admin.get_vision_provider"
    ) as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.name = "ollama:qwen2.5-vl:7b"
        mock_provider.health_check = AsyncMock(return_value=False)
        mock_factory.return_value = mock_provider

        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.get("/api/admin/vision/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is False
    assert body["error"] is not None
    assert len(body["error"]) > 0


async def test_vision_health_handles_health_check_raising(
    bootstrapped_client: AsyncClient,
) -> None:
    """A buggy provider whose health_check() raises maps to 200 + healthy=false."""
    with patch(
        "backend.app.api.admin.get_vision_provider"
    ) as mock_factory:
        mock_provider = AsyncMock()
        mock_provider.name = "ollama:qwen2.5-vl:7b"
        mock_provider.health_check = AsyncMock(side_effect=RuntimeError("boom"))
        mock_factory.return_value = mock_provider

        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.get("/api/admin/vision/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is False
    assert body["error"] is not None
    assert "boom" in body["error"]


async def test_vision_health_handles_factory_error(
    bootstrapped_client: AsyncClient,
) -> None:
    """GET /api/admin/vision/health returns 200 with healthy=false when factory raises."""
    error_message = "HEARTH_GEMINI_API_KEY is required when vision_provider='gemini'"

    with patch(
        "backend.app.api.admin.get_vision_provider",
        side_effect=ValueError(error_message),
    ):
        async with bootstrapped_client as ac:
            await _login_admin(ac)
            resp = await ac.get("/api/admin/vision/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["healthy"] is False
    assert body["error"] is not None
    assert "HEARTH_GEMINI_API_KEY" in body["error"]


async def test_vision_health_requires_admin(
    bootstrapped_client: AsyncClient,
    db_engine: AsyncEngine,
) -> None:
    """Non-admin user gets 403 on GET /api/admin/vision/health."""
    async with bootstrapped_client as ac:
        await _login_regular(ac, db_engine)
        resp = await ac.get("/api/admin/vision/health")

    assert resp.status_code == 403
