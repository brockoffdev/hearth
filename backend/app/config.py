"""Application settings loaded from environment variables."""

import functools
from pathlib import Path
from typing import Literal

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

    # When True, create the bootstrap admin user on startup if no users exist.
    # Set HEARTH_BOOTSTRAP_ADMIN_ON_STARTUP=false in tests (each test controls
    # bootstrap explicitly via the ensure_bootstrap_admin fixture).
    bootstrap_admin_on_startup: bool = True

    # When True, scan for stranded uploads (status 'queued' or 'processing')
    # on startup and re-enqueue them.  Uploads can be stranded if the server
    # crashes mid-pipeline (the in-memory queue is lost but the DB rows remain).
    # Set HEARTH_RECOVER_UPLOADS_ON_STARTUP=false in tests to avoid spurious
    # task dispatch during unit tests.
    recover_uploads_on_startup: bool = True

    # Required: a long random string used to sign session cookies.
    # Generate one with:
    #   python -c "import secrets; print(secrets.token_urlsafe(32))"
    # Set HEARTH_SESSION_SECRET in your environment or .env file.
    # The application will refuse to start if this is not set.
    session_secret: str

    # Public base URL for the Hearth server, used to build OAuth redirect URIs.
    # Override via HEARTH_PUBLIC_BASE_URL in production (e.g. https://hearth.example.com).
    # Must NOT have a trailing slash.
    public_base_url: str = "http://localhost:8080"

    # Maximum size in bytes accepted for a single photo upload.
    # Override via HEARTH_MAX_UPLOAD_BYTES.
    max_upload_bytes: int = 25 * 1024 * 1024  # 25 MB

    # Fake-pipeline timing knobs — Phase 3 only.
    # Phase 4 replaces the fake pipeline with real VLM calls; these settings
    # become irrelevant once real timing is driven by model inference.
    # Seconds to pause between pipeline stages (non-cell-progress stages).
    pipeline_stage_delay_seconds: float = 1.5
    # Seconds to pause between individual cell events during cell_progress.
    pipeline_cell_delay_seconds: float = 0.15

    # When True, dispatch an asyncio.Task to run the pipeline immediately after
    # POST /api/uploads (or POST /api/uploads/{id}/retry) creates a queued row.
    # Set HEARTH_DISPATCH_RUNNER_ON_CREATE_UPLOAD=false in tests so the runner
    # is never auto-fired; tests that need pipeline behaviour call
    # run_pipeline_for_upload() directly for deterministic sequencing.
    dispatch_runner_on_create_upload: bool = True

    # ---------------------------------------------------------------------------
    # Vision provider config
    # ---------------------------------------------------------------------------

    # Which VisionProvider to use. Override via HEARTH_VISION_PROVIDER.
    vision_provider: Literal["ollama", "gemini", "anthropic"] = "ollama"

    # URL of the Ollama daemon. Override via HEARTH_OLLAMA_ENDPOINT.
    ollama_endpoint: str = "http://localhost:11434"

    # Which model the provider uses. Override via HEARTH_VISION_MODEL.
    vision_model: str = "qwen2.5-vl:7b"

    # Above this confidence, events auto-publish; below, they queue for review.
    # Override via HEARTH_CONFIDENCE_THRESHOLD.
    confidence_threshold: float = 0.85

    # Gemini API key (BYO). Required when vision_provider='gemini'.
    # Get one at https://aistudio.google.com/.
    # Override via HEARTH_GEMINI_API_KEY.
    # Note: when switching providers, set BOTH vision_provider AND vision_model;
    # the factory does not auto-swap to provider-specific defaults.
    gemini_api_key: str = ""

    # Anthropic API key (BYO). Required when vision_provider='anthropic'.
    # Get one at https://console.anthropic.com/.
    # Override via HEARTH_ANTHROPIC_API_KEY.
    # Note: when switching providers, set BOTH vision_provider AND vision_model;
    # the factory does not auto-swap to provider-specific defaults.
    anthropic_api_key: str = ""

    # When True, POST /api/uploads dispatches the real VLM pipeline
    # (preprocessing + grid detect + per-cell VLM + color match).
    # When False (default), uses the fake-stages-on-a-timer pipeline — useful
    # for UI testing without a running VLM model.
    # Override via HEARTH_USE_REAL_PIPELINE.
    use_real_pipeline: bool = False

    # How many of the most recent event_corrections to include as few-shot
    # examples in the VLM prompt. Override via HEARTH_FEW_SHOT_CORRECTION_WINDOW.
    # Set to 0 to disable few-shot retrieval entirely.
    few_shot_correction_window: int = 10

    # When True, probe the configured VisionProvider during startup lifespan.
    # Non-fatal: failures log a warning but never block startup.
    # Set HEARTH_VISION_HEALTH_CHECK_ON_STARTUP=false in tests or dev to skip.
    vision_health_check_on_startup: bool = True

    # Session cookie configuration.
    session_cookie_name: str = "hearth_session"
    # Set HEARTH_SESSION_COOKIE_SECURE=true in production (HTTPS).
    # False by default to allow plain HTTP in local dev.
    session_cookie_secure: bool = False
    # 30 days — forces a periodic re-login without annoying daily users.
    session_cookie_max_age_seconds: int = 60 * 60 * 24 * 30

    model_config = SettingsConfigDict(env_prefix="HEARTH_")


@functools.lru_cache
def get_settings() -> Settings:
    # session_secret has no default; pydantic-settings loads it from
    # HEARTH_SESSION_SECRET at runtime.  mypy cannot model this pattern.
    return Settings()  # type: ignore[call-arg]
