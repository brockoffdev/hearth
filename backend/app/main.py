"""FastAPI application factory."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import router as api_router
from backend.app.auth.bootstrap import ensure_bootstrap_admin
from backend.app.config import get_settings
from backend.app.db.base import get_session_factory
from backend.app.google.sync import sync_from_gcal
from backend.app.static import mount_frontend
from backend.app.uploads.pipeline import refresh_stage_medians_from_db
from backend.app.uploads.runner import recover_pending_uploads
from backend.app.vision import get_vision_provider

logger = logging.getLogger(__name__)

_sync_task: asyncio.Task[None] | None = None

# Make sure the application's INFO-level logs are visible by default.
# alembic's env.py calls fileConfig(...) on startup which used to wipe
# the existing loggers; we now pass disable_existing_loggers=False there,
# but a default basicConfig here ensures backend.app.* records have a
# stderr handler regardless of how uvicorn is invoked or what other code
# tweaks logging.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

# Resolved once at import time; tests may monkeypatch this to redirect to a
# temporary directory without affecting the real repo tree.
_DOCS_DIR: Path = Path(__file__).resolve().parent.parent.parent / "docs"


def _run_migrations() -> None:
    """Run pending Alembic migrations synchronously.

    Called from lifespan via asyncio.to_thread so the sync Alembic API does
    not block the event loop.  Creates the data directory first so SQLite
    can open the DB file even if the volume mount hasn't pre-created it.
    """
    settings = get_settings()
    # Ensure the directory that will hold the SQLite file exists.
    # This matters on first boot before the volume mount creates /data.
    data_dir = settings.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", "backend/alembic")
    command.upgrade(cfg, "head")


async def _gcal_sync_loop(session_factory: Any) -> None:
    """Background loop: run sync_from_gcal every gcal_sync_interval_seconds."""
    _settings = get_settings()
    while True:
        try:
            async with session_factory() as session:
                stats = await sync_from_gcal(session, settings=_settings)
            logger.info("GCal sync: %s", stats)
        except Exception:
            logger.exception("GCal sync failed")
        await asyncio.sleep(_settings.gcal_sync_interval_seconds)


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("Hearth starting up — version %s", settings.version)
        if settings.run_migrations_on_startup:
            logger.info("Running database migrations…")
            await asyncio.to_thread(_run_migrations)
            logger.info("Migrations complete.")

        # Phase 4 Task H: refresh stage medians from accumulated measurements.
        # Wrapped in wait_for so a stalled DB connection (e.g. an aiosqlite
        # worker that gets stuck) can't wedge startup forever.  The query
        # itself is a single SELECT against an indexed table — 10 s is
        # generous, and on timeout we just keep the baseline values.
        try:
            await asyncio.wait_for(
                refresh_stage_medians_from_db(get_session_factory()),
                timeout=10.0,
            )
        except TimeoutError:
            logger.warning(
                "Refreshing stage medians timed out after 10s — using baseline values"
            )
        except Exception:
            logger.exception(
                "Failed to refresh stage medians — using baseline values"
            )

        if settings.bootstrap_admin_on_startup:
            logger.info("Ensuring bootstrap admin…")
            await ensure_bootstrap_admin(get_session_factory())

        # Phase 4 Task H: re-enqueue uploads stranded by a prior server crash.
        if settings.recover_uploads_on_startup:
            try:
                recovered = await recover_pending_uploads(get_session_factory())
                if recovered > 0:
                    logger.info(
                        "Recovered %d stranded upload(s) from prior session", recovered
                    )
            except Exception:
                logger.exception(
                    "Failed to recover stranded uploads — "
                    "they will need manual cleanup"
                )

        # Phase 5 Task C: non-fatal VisionProvider liveness probe at startup.
        if settings.vision_health_check_on_startup:
            try:
                provider = get_vision_provider(settings)
                provider_name = provider.name
                healthy = await provider.health_check()
                if healthy:
                    logger.info("Vision provider %s healthy", provider_name)
                else:
                    logger.warning(
                        "Vision provider %s health check failed "
                        "(provider may be unavailable)",
                        provider_name,
                    )
            except Exception:
                logger.warning(
                    "Vision provider %s health check failed "
                    "(provider may be unavailable)",
                    settings.vision_provider,
                )

        global _sync_task
        if settings.gcal_sync_enabled:
            _sync_task = asyncio.create_task(
                _gcal_sync_loop(get_session_factory())
            )

        yield

        if _sync_task is not None:
            _sync_task.cancel()
            try:
                await _sync_task
            except asyncio.CancelledError:
                pass
            _sync_task = None

    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router, prefix="/api")

    docs_dir = _DOCS_DIR
    if docs_dir.is_dir():
        application.mount(
            "/docs",
            StaticFiles(directory=str(docs_dir)),
            name="docs",
        )
        logger.info("Mounted docs directory from %s", docs_dir)

    mount_frontend(application, settings.frontend_dist_dir)

    return application


app = create_app()
