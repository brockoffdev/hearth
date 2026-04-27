"""Tests for SPA catch-all behaviour in mount_frontend.

Convention used here:
- Any non-/api path (including asset-shaped paths like /assets/missing.js) falls back
  to index.html with status 200.  This is the simplest rule and avoids needing to
  distinguish "asset-shaped" from "route-shaped" paths at the server level.
- Only /api/* paths bypass the fallback and hit the real API router.
"""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

SPA_CONTENT = "<html><body>SPA index</body></html>"


@pytest.fixture()
def spa_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[FastAPI, None, None]:
    """Create a minimal frontend dist with index.html and return a fresh app instance."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(SPA_CONTENT)

    # Patch get_settings to return a Settings object pointing at our temp dist.
    # Save the original lru_cache-wrapped function so we can restore it after the test.
    import backend.app.config as cfg_module
    import backend.app.main as main_module
    from backend.app.config import Settings

    original_get_settings = cfg_module.get_settings
    original_get_settings.cache_clear()

    patched = lambda: Settings(frontend_dist_dir=str(dist))  # noqa: E731

    # Patch in both the config module and main module (which imported it directly).
    monkeypatch.setattr(cfg_module, "get_settings", patched)
    monkeypatch.setattr(main_module, "get_settings", patched)

    app = main_module.create_app()

    yield app

    # Restore the original cached function and clear any stale entries.
    monkeypatch.setattr(cfg_module, "get_settings", original_get_settings)
    monkeypatch.setattr(main_module, "get_settings", original_get_settings)
    original_get_settings.cache_clear()


@pytest.mark.asyncio
async def test_spa_client_route_returns_index(spa_app: FastAPI) -> None:
    """GET /dashboard must return 200 and the contents of index.html."""
    async with AsyncClient(transport=ASGITransport(app=spa_app), base_url="http://test") as client:
        response = await client.get("/dashboard")
    assert response.status_code == 200
    assert SPA_CONTENT in response.text


@pytest.mark.asyncio
async def test_api_health_not_shadowed_by_spa(spa_app: FastAPI) -> None:
    """GET /api/health must still return the real API response, not index.html."""
    async with AsyncClient(transport=ASGITransport(app=spa_app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "version": "0.1.0", "name": "hearth"}


@pytest.mark.asyncio
async def test_missing_asset_returns_index(spa_app: FastAPI) -> None:
    """GET /assets/missing.js falls back to index.html.

    Simplest rule: anything non-/api falls back to the SPA entry point.
    """
    async with AsyncClient(transport=ASGITransport(app=spa_app), base_url="http://test") as client:
        response = await client.get("/assets/missing.js")
    assert response.status_code == 200
    assert SPA_CONTENT in response.text
