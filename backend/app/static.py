"""SPA static file mount helper."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.types import Scope

logger = logging.getLogger(__name__)


class SPAStaticFiles(StaticFiles):
    """StaticFiles subclass that falls back to index.html for any missing path.

    Standard StaticFiles(html=True) only serves index.html at '/' and at
    directory paths — it raises 404 for arbitrary client-side routes like
    /dashboard.  This subclass catches those 404s and returns index.html
    instead, enabling client-side routing to work correctly.

    Paths that begin with /api/ are never routed to this mount (FastAPI
    matches the /api prefix first), so the API is unaffected.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                # Fall back to the SPA entry point for unknown paths.
                return await super().get_response("index.html", scope)
            raise


def mount_frontend(app: FastAPI, dist_dir: Path) -> None:
    """Mount the compiled frontend SPA at '/'.

    If dist_dir does not exist, logs a warning and returns without mounting.

    Uses SPAStaticFiles so that any path not matching a real file AND not
    starting with /api/ will receive index.html (status 200), allowing
    client-side routes (e.g. /dashboard) to work correctly.

    This must be called AFTER the API router is registered so /api routes
    take precedence over the catch-all static mount.
    """
    if not dist_dir.exists():
        logger.warning("Frontend dist directory %s not found — skipping static mount", dist_dir)
        return

    app.mount("/", SPAStaticFiles(directory=str(dist_dir), html=True), name="frontend")
    logger.info("Mounted frontend SPA from %s", dist_dir)
