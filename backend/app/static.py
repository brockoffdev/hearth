"""SPA static file mount helper."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)


def mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    """Mount the compiled frontend SPA at '/'.

    If dist_dir does not exist, logs a warning and returns without mounting.
    StaticFiles with html=True handles the SPA fallback to index.html for
    any path that doesn't match a real file.

    This must be called AFTER the API router is registered so /api routes
    take precedence over the catch-all static mount.
    """
    if not dist_dir.exists():
        logger.warning("Frontend dist directory %s not found — skipping static mount", dist_dir)
        return

    app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
    logger.info("Mounted frontend SPA from %s", dist_dir)
