"""Application settings loaded from environment variables."""

import functools
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "hearth"
    version: str = "0.1.0"
    debug: bool = False
    data_dir: Path = Path("/data")
    frontend_dist_dir: Path = Path("frontend/dist")
    # Override via JSON list, e.g. HEARTH_CORS_ORIGINS='["https://hearth.example.com"]'
    cors_origins: list[str] = [
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8080",  # Production / compose
    ]

    # Async SQLAlchemy URL for the application.
    # Format: sqlite+aiosqlite:///./path/to/db  (relative) or
    #         sqlite+aiosqlite:////absolute/path/to/db  (absolute — note 4 slashes)
    # Override with HEARTH_DATABASE_URL.
    # Default is relative (./data/hearth.db) for dev; Docker compose overrides to
    # sqlite+aiosqlite:////data/hearth.db to use the /data volume mount.
    database_url: str = "sqlite+aiosqlite:///./data/hearth.db"

    # When True the application runs pending Alembic migrations at startup.
    # Set HEARTH_RUN_MIGRATIONS_ON_STARTUP=false in tests to keep them isolated.
    run_migrations_on_startup: bool = True

    model_config = SettingsConfigDict(env_prefix="HEARTH_")


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
