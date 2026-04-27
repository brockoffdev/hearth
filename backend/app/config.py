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

    model_config = SettingsConfigDict(env_prefix="HEARTH_")


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
