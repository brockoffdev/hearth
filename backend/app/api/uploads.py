"""Upload API endpoints — Phase 3 Task A + B.

Routes:
  POST   /api/uploads               — accept a multipart photo upload
  GET    /api/uploads               — list current user's uploads (most recent first)
  GET    /api/uploads/{id}          — single upload metadata
  GET    /api/uploads/{id}/photo    — raw photo bytes
  GET    /api/uploads/{id}/events   — SSE stream of pipeline stage events
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.app.auth.dependencies import require_user
from backend.app.config import Settings, get_settings
from backend.app.db.base import get_db
from backend.app.db.models import Upload, User
from backend.app.uploads.pipeline import run_fake_pipeline
from backend.app.uploads.storage import read_photo, store_photo

router = APIRouter()

# Map stored file extension → media type returned in photo responses.
_EXT_TO_MEDIA_TYPE: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".bin": "application/octet-stream",
}

_LIST_LIMIT = 50


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class UploadResponse(BaseModel):
    id: int
    status: str
    image_path: str
    uploaded_at: datetime
    url: str

    model_config = {"from_attributes": True}


def _to_response(upload: Upload) -> UploadResponse:
    return UploadResponse(
        id=upload.id,
        status=upload.status,
        image_path=upload.image_path,
        uploaded_at=upload.uploaded_at,
        url=f"/api/uploads/{upload.id}/photo",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=UploadResponse)
async def create_upload(
    photo: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> UploadResponse:
    """Accept a multipart photo upload; store it; create an Upload row."""
    content_type = photo.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    image_bytes = await photo.read()

    if len(image_bytes) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds maximum allowed size of {settings.max_upload_bytes} bytes",
        )

    _sha256, rel_path = await store_photo(image_bytes, content_type, settings.data_dir)

    upload = Upload(
        user_id=current_user.id,
        image_path=rel_path,
        status="queued",
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return _to_response(upload)


@router.get("", response_model=list[UploadResponse])
async def list_uploads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> list[UploadResponse]:
    """Return the current user's uploads, most recent first (limit 50)."""
    result = await db.execute(
        select(Upload)
        .where(Upload.user_id == current_user.id)
        .order_by(Upload.uploaded_at.desc(), Upload.id.desc())
        .limit(_LIST_LIMIT)
    )
    uploads = list(result.scalars().all())
    return [_to_response(u) for u in uploads]


@router.get("/{upload_id}", response_model=UploadResponse)
async def get_upload(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> UploadResponse:
    """Return metadata for a single upload."""
    upload = await _fetch_upload_or_404(upload_id, db)
    _check_access(upload, current_user)
    return _to_response(upload)


@router.get("/{upload_id}/photo")
async def get_upload_photo(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Return the raw photo bytes for an upload."""
    upload = await _fetch_upload_or_404(upload_id, db)
    _check_access(upload, current_user)

    try:
        image_bytes = await read_photo(upload.image_path, settings.data_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Photo file not found on disk") from exc

    ext = Path(upload.image_path).suffix.lower()
    media_type = _EXT_TO_MEDIA_TYPE.get(ext, "application/octet-stream")
    return Response(content=image_bytes, media_type=media_type)


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------


@router.get("/{upload_id}/events")
async def stream_upload_events(
    upload_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(require_user),
) -> EventSourceResponse:
    """Stream SSE events for the upload's processing pipeline.

    Emits ``stage_update`` named events.  Each event's data is a JSON object
    with keys ``stage``, ``message``, and ``progress``.

    If the upload is already completed or failed, a single ``done`` event is
    emitted immediately and the connection closes.
    """
    upload = await _fetch_upload_or_404(upload_id, db)
    _check_access(upload, current_user)

    # Short-circuit if already terminal — don't re-run the pipeline.
    if upload.status in ("completed", "failed"):
        async def _already_done() -> AsyncGenerator[dict[str, str], None]:
            payload = {"stage": "done", "message": "already-complete", "progress": None}
            yield {"event": "stage_update", "data": json.dumps(payload)}

        return EventSourceResponse(_already_done())

    # Transition status to processing before emitting the first event so that
    # GET /api/uploads/{id} reflects the in-flight state immediately.
    upload.status = "processing"
    await db.commit()
    await db.refresh(upload)

    async def _event_generator() -> AsyncGenerator[dict[str, str], None]:
        saw_done = False
        try:
            pipeline = run_fake_pipeline(
                upload_id,
                stage_delay_seconds=settings.pipeline_stage_delay_seconds,
                cell_delay_seconds=settings.pipeline_cell_delay_seconds,
            )
            async for stage_event in pipeline:
                if await request.is_disconnected():
                    # Client disconnected mid-stream — abort without updating DB.
                    return

                yield {
                    "event": "stage_update",
                    "data": json.dumps(asdict(stage_event)),
                }

                if stage_event.stage == "done":
                    saw_done = True
                    break

        finally:
            if saw_done and not await request.is_disconnected():
                # Mark the upload as completed only if the pipeline ran to done.
                upload.status = "completed"
                upload.finished_at = datetime.now(tz=UTC)
                upload.provider = "fake-pipeline-phase-3"
                await db.commit()

    return EventSourceResponse(_event_generator())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch_upload_or_404(upload_id: int, db: AsyncSession) -> Upload:
    result = await db.execute(select(Upload).where(Upload.id == upload_id))
    upload = result.scalar_one_or_none()
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload


def _check_access(upload: Upload, current_user: User) -> None:
    """Raise 403 if current_user may not access this upload."""
    if upload.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
