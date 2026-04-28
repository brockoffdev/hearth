"""Upload API endpoints — Phase 3 Task A + B + Phase 3.5.

Routes:
  POST   /api/uploads               — accept a multipart photo upload
  GET    /api/uploads               — list current user's uploads (most recent first)
  GET    /api/uploads/{id}          — single upload metadata
  GET    /api/uploads/{id}/photo    — raw photo bytes
  GET    /api/uploads/{id}/events   — SSE stream of pipeline stage events
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from backend.app.auth.dependencies import require_user
from backend.app.config import Settings, get_settings
from backend.app.db.base import get_db
from backend.app.db.models import PipelineStageDuration, Upload, User
from backend.app.uploads.friendly_time import (
    format_relative_finished_at,
    format_relative_started_at,
    format_thumb_label,
)
from backend.app.uploads.pipeline import estimate_remaining_seconds, run_fake_pipeline
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
    id: str  # stringified integer
    status: Literal["processing", "completed", "failed"]
    image_path: str
    thumb_label: str = Field(alias="thumbLabel")
    started_at: str | None = Field(default=None, alias="startedAt")
    finished_at: str | None = Field(default=None, alias="finishedAt")

    # processing-only
    current_stage: str | None = None
    completed_stages: list[str] | None = None
    cell_progress: int | None = Field(default=None, alias="cellProgress")
    total_cells: int | None = Field(default=None, alias="totalCells")
    remaining_seconds: int | None = None
    queued_behind: int | None = Field(default=None, alias="queuedBehind")

    # completed-only (Phase 6+ adds events table; found/review are None for now)
    found: int | None = None
    review: int | None = None
    duration_sec: int | None = Field(default=None, alias="durationSec")

    # failed-only
    error: str | None = None

    # Legacy fields kept for Phase 3 frontend until Tasks F-H land.
    url: str
    uploaded_at: str

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Status mapping helper
# ---------------------------------------------------------------------------


def _row_status_to_api(
    row_status: str, current_stage: str | None
) -> Literal["processing", "completed", "failed"]:
    """Map DB row.status → API status.

    Queued rows show as 'processing' with current_stage='queued' since the
    design treats queued as a sub-state of processing.
    """
    if row_status in ("queued", "processing"):
        return "processing"
    if row_status == "failed":
        return "failed"
    return "completed"


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------


def _to_response(
    upload: Upload,
    *,
    queued_behind: int | None = None,
    now: datetime | None = None,
) -> UploadResponse:
    """Build an UploadResponse from an Upload ORM row.

    Args:
        upload: The Upload row to serialize.
        queued_behind: Number of pipelines ahead in the queue (0 = running now).
            Task B will compute this; Task A passes None for now.
        now: Override the current time (used in tests for deterministic output).
    """
    now = now or datetime.now(UTC)
    api_status = _row_status_to_api(upload.status, upload.current_stage)

    is_processing = api_status == "processing"
    is_completed = api_status == "completed"
    is_failed = api_status == "failed"

    # SQLite returns naive datetimes; strip timezone from `now` if needed.
    if upload.uploaded_at.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    completed_stages = json.loads(upload.completed_stages) if upload.completed_stages else []

    return UploadResponse.model_validate(
        {
            "id": str(upload.id),
            "status": api_status,
            "image_path": upload.image_path,
            "thumbLabel": format_thumb_label(upload.uploaded_at),
            "startedAt": (
                format_relative_started_at(upload.uploaded_at, now)
                if is_processing
                else None
            ),
            "finishedAt": (
                format_relative_finished_at(upload.finished_at, now)
                if upload.finished_at
                else None
            ),
            # processing fields
            "current_stage": upload.current_stage if is_processing else None,
            "completed_stages": completed_stages if is_processing else None,
            "cellProgress": upload.cell_progress if is_processing else None,
            "totalCells": upload.total_cells if is_processing else None,
            "remaining_seconds": (
                estimate_remaining_seconds(completed_stages) if is_processing else None
            ),
            "queuedBehind": queued_behind if is_processing else None,
            # completed fields
            "durationSec": (
                int((upload.finished_at - upload.uploaded_at).total_seconds())
                if is_completed and upload.finished_at
                else None
            ),
            # failed fields
            "error": upload.error if is_failed else None,
            # legacy for Phase 3 frontend
            "url": f"/api/uploads/{upload.id}/photo",
            "uploaded_at": upload.uploaded_at.isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def create_upload(
    photo: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
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
        completed_stages="[]",
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)
    return _to_response(upload).model_dump(by_alias=True)


@router.get("")
async def list_uploads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> list[dict[str, object]]:
    """Return the current user's uploads, most recent first (limit 50)."""
    result = await db.execute(
        select(Upload)
        .where(Upload.user_id == current_user.id)
        .order_by(Upload.uploaded_at.desc(), Upload.id.desc())
        .limit(_LIST_LIMIT)
    )
    uploads = list(result.scalars().all())
    return [_to_response(u).model_dump(by_alias=True) for u in uploads]


@router.get("/{upload_id}")
async def get_upload(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
) -> dict[str, object]:
    """Return metadata for a single upload."""
    upload = await _fetch_upload_or_404(upload_id, db)
    _check_access(upload, current_user)
    return _to_response(upload).model_dump(by_alias=True)


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
    with keys ``stage``, ``message``, ``progress``, ``completed_stages``, and
    ``remaining_seconds``.

    During streaming, the Upload row's ``current_stage``, ``completed_stages``,
    ``cell_progress``, and ``total_cells`` fields are updated on each stage
    transition so concurrent GET requests see live progress.

    Per-stage durations are recorded to ``pipeline_stage_durations`` on each
    stage transition for future ETA calibration (Phase 4+).

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
        stage_start: dict[str, float] = {}
        prev_stage: str | None = None

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

                now_mono = time.monotonic()

                # Track stage transitions: record duration for the previous stage.
                if prev_stage is not None and prev_stage != stage_event.stage:
                    duration = now_mono - stage_start[prev_stage]
                    db.add(
                        PipelineStageDuration(
                            upload_id=upload.id,
                            stage=prev_stage,
                            duration_seconds=duration,
                        )
                    )

                if stage_event.stage not in stage_start:
                    stage_start[stage_event.stage] = now_mono

                # Persist progress to the Upload row.
                upload.current_stage = stage_event.stage
                upload.completed_stages = json.dumps(stage_event.completed_stages or [])
                if stage_event.progress:
                    upload.cell_progress = stage_event.progress["cell"]
                    upload.total_cells = stage_event.progress["total"]

                await db.commit()

                # Emit the event to the client.
                yield {
                    "event": "stage_update",
                    "data": json.dumps(asdict(stage_event)),
                }

                prev_stage = stage_event.stage

                if stage_event.stage == "done":
                    saw_done = True
                    break

        finally:
            if saw_done and not await request.is_disconnected():
                # Record duration for the final stage.
                if prev_stage and prev_stage in stage_start:
                    duration = time.monotonic() - stage_start[prev_stage]
                    db.add(
                        PipelineStageDuration(
                            upload_id=upload.id,
                            stage=prev_stage,
                            duration_seconds=duration,
                        )
                    )

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
