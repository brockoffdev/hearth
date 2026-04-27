"""Application settings loaded from environment variables."""

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "hearth"
    version: str = "0.1.0"
    debug: bool = False
    data_dir: str = "/data"
    frontend_dist_dir: str = "frontend/dist"

    model_config = SettingsConfigDict(env_prefix="HEARTH_")


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()
