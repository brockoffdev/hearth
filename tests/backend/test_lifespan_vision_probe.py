"""Tests for the VisionProvider lifespan startup probe — Phase 5 Task C.

These tests exercise the startup probe logic directly via the ASGI lifespan
protocol.  They do NOT use the db_engine fixture; the lifespan catches any DB
error from refresh_stage_medians_from_db via its own try/except, so no real
database is required.

Note on caplog: Alembic (used by the db_engine fixture) calls
``logging.basicConfig`` internally, which replaces pytest's log-capture
handlers on the root logger and breaks ``caplog`` for tests that follow in the
same session.  We therefore spy on the module logger directly instead.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

from backend.app.config import Settings
from backend.app.main import create_app


def _make_settings(**overrides: object) -> Settings:
    """Return a minimal Settings instance with test-safe defaults."""
    defaults: dict[str, object] = {
        "session_secret": "test-secret-do-not-use-in-prod",
        "run_migrations_on_startup": False,
        "bootstrap_admin_on_startup": False,
        "recover_uploads_on_startup": False,
        "vision_health_check_on_startup": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


async def _run_lifespan_startup(settings: Settings) -> None:
    """Drive the ASGI lifespan startup/shutdown sequence.

    Patches get_settings before create_app so the closure captures our settings.
    Sends the full lifespan startup followed by an immediate shutdown so the
    startup probe runs without leaving background tasks alive.
    """
    with patch("backend.app.main.get_settings", return_value=settings):
        app = create_app()

    startup_complete: asyncio.Event = asyncio.Event()
    can_shutdown: asyncio.Event = asyncio.Event()

    async def receive() -> dict[str, Any]:
        if not startup_complete.is_set():
            return {"type": "lifespan.startup"}
        await can_shutdown.wait()
        return {"type": "lifespan.shutdown"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "lifespan.startup.complete":
            startup_complete.set()
            can_shutdown.set()

    scope: dict[str, Any] = {"type": "lifespan", "asgi": {"version": "3.0"}}

    lifespan_task = asyncio.create_task(app(scope, receive, send))
    await startup_complete.wait()
    await lifespan_task


async def test_lifespan_probe_logs_info_when_healthy() -> None:
    """A healthy provider logs at INFO during startup."""
    settings = _make_settings()

    mock_provider = AsyncMock()
    mock_provider.name = "ollama:qwen2.5vl:7b"
    mock_provider.health_check = AsyncMock(return_value=True)

    with patch("backend.app.main.get_vision_provider", return_value=mock_provider), \
         patch("backend.app.main.logger") as mock_logger:
        await _run_lifespan_startup(settings)

    # Verify logger.info was called with the provider name and "healthy".
    info_calls: list[tuple[Any, ...]] = [
        c.args for c in mock_logger.info.call_args_list
    ]
    assert any(
        "ollama:qwen2.5vl:7b" in str(args) and "healthy" in str(args)
        for args in info_calls
    )


async def test_lifespan_probe_logs_warning_when_unhealthy() -> None:
    """A failing provider logs at WARNING during startup, and startup completes."""
    settings = _make_settings()

    mock_provider = AsyncMock()
    mock_provider.name = "ollama:qwen2.5vl:7b"
    mock_provider.health_check = AsyncMock(return_value=False)

    with patch("backend.app.main.get_vision_provider", return_value=mock_provider), \
         patch("backend.app.main.logger") as mock_logger:
        # Must not raise — startup completes even with a failing probe.
        await _run_lifespan_startup(settings)

    warning_calls: list[tuple[Any, ...]] = [
        c.args for c in mock_logger.warning.call_args_list
    ]
    assert any(
        "ollama:qwen2.5vl:7b" in str(args) and "health check failed" in str(args)
        for args in warning_calls
    )


async def test_lifespan_probe_skipped_when_disabled() -> None:
    """vision_health_check_on_startup=False skips the probe entirely."""
    settings = _make_settings(vision_health_check_on_startup=False)

    with patch("backend.app.main.get_vision_provider") as mock_factory:
        await _run_lifespan_startup(settings)

    # Factory must never be called when the probe is disabled.
    mock_factory.assert_not_called()
