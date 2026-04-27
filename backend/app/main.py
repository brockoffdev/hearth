"""FastAPI application factory."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import router as api_router
from backend.app.config import get_settings
from backend.app.static import mount_frontend

logger = logging.getLogger(__name__)


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


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
        logger.info("Hearth starting up — version %s", settings.version)
        if settings.run_migrations_on_startup:
            logger.info("Running database migrations…")
            await asyncio.to_thread(_run_migrations)
            logger.info("Migrations complete.")
        yield

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

    mount_frontend(application, settings.frontend_dist_dir)

    return application


app = create_app()
