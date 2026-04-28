"""Upload API endpoints — Phase 3 Task A + B + Phase 3.5.

Routes:
  POST   /api/uploads                    — accept a multipart photo upload
  GET    /api/uploads                    — list current user's uploads (most recent first)
  GET    /api/uploads/{id}              — single upload metadata
  GET    /api/uploads/{id}/photo        — raw photo bytes
  GET    /api/uploads/{id}/events       — SSE stream of pipeline stage events
  DELETE /api/uploads/{id}              — cancel a queued upload (removes row + file)
  POST   /api/uploads/{id}/retry        — retry a failed upload (creates new row)
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
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
from backend.app.db.base import get_db, get_session_factory
from backend.app.db.models import Upload, User
from backend.app.uploads.friendly_time import (
    format_relative_finished_at,
    format_relative_started_at,
    format_thumb_label,
)
from backend.app.uploads.pipeline import (
    estimate_remaining_seconds,
    queue_wait_seconds_simple,
)
from backend.app.uploads.queue import dequeue, enqueue, queue_position
from backend.app.uploads.runner import run_pipeline_for_upload
from backend.app.uploads.storage import read_photo, store_photo

router = APIRouter()

# Strong references to running pipeline tasks.  Without this, the GC could
# collect a Task before it finishes (Python only keeps weak refs to Tasks).
_background_tasks: set[asyncio.Task[None]] = set()

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
# Queue-wait ETA helper
# ---------------------------------------------------------------------------


def _queue_wait_seconds(upload_id: int) -> int:
    """Upper-bound queue-wait ETA for *upload_id*.

    Delegates to queue_wait_seconds_simple from pipeline.py (position x
    full-pipeline median).  Returns 0 if the upload is not in the queue or
    is at the head.
    """
    pos = queue_position(upload_id)
    if pos is None or pos == 0:
        return 0
    return queue_wait_seconds_simple(pos)


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
            When None, the queue position is looked up live.
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

    # Compute queue wait for ETA when processing.
    if is_processing and queued_behind is None:
        queued_behind = queue_position(upload.id)

    pipeline_eta = estimate_remaining_seconds(completed_stages) if is_processing else None
    if is_processing and pipeline_eta is not None:
        queue_wait = _queue_wait_seconds(upload.id) if upload.id is not None else 0
        remaining = pipeline_eta + queue_wait
    else:
        remaining = None

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
            "remaining_seconds": remaining,
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
    """Accept a multipart photo upload; store it; create a queued Upload row;
    dispatch the pipeline runner as a background asyncio.Task."""
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
        current_stage="queued",
        completed_stages="[]",
    )
    db.add(upload)
    await db.commit()
    await db.refresh(upload)

    # Enqueue THEN dispatch.  enqueue must happen before create_task so that
    # queue_position() returns the correct value inside _to_response().
    await enqueue(upload.id)

    if settings.dispatch_runner_on_create_upload:
        factory = get_session_factory()
        _task = asyncio.create_task(
            run_pipeline_for_upload(
                upload.id,
                factory,
                stage_delay_seconds=settings.pipeline_stage_delay_seconds,
                cell_delay_seconds=settings.pipeline_cell_delay_seconds,
            )
        )
        _background_tasks.add(_task)
        _task.add_done_callback(_background_tasks.discard)

    pos = queue_position(upload.id)
    return _to_response(upload, queued_behind=pos).model_dump(by_alias=True)


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
# SSE endpoint — polling reader (Phase 3.5 lightweight implementation)
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

    **Phase 3.5 implementation:** the pipeline runner is dispatched as an
    asyncio.Task at POST time (decoupled from this endpoint).  This handler
    polls the Upload row every 0.5 s and emits a ``stage_update`` event
    whenever the row's state key changes.

    The polling model trades ~0.5 s latency for simplicity.  Given the fake
    pipeline's per-stage delay of 1.5 s the latency is imperceptible.  Phase 5
    may replace polling with a pub/sub channel if sub-second latency matters.

    Emits ``stage_update`` named events.  Each event's data is a JSON object
    with keys: ``stage``, ``message``, ``progress``, ``completed_stages``,
    ``remaining_seconds``.

    If the upload is already completed or failed, a single ``done`` event is
    emitted immediately and the connection closes.
    """
    upload = await _fetch_upload_or_404(upload_id, db)
    _check_access(upload, current_user)

    # Short-circuit if already terminal — don't wait for anything.
    # The payload shape must match the polling-loop branch below so SSE
    # consumers can rely on completed_stages / remaining_seconds always
    # being present (otherwise a race between POST and SSE-subscribe in
    # CI exposes the schema gap).
    if upload.status in ("completed", "failed"):
        terminal_completed = (
            json.loads(upload.completed_stages) if upload.completed_stages else []
        )

        async def _already_done() -> AsyncGenerator[dict[str, str], None]:
            payload = {
                "stage": "done",
                "message": "already-complete",
                "progress": None,
                "completed_stages": terminal_completed,
                "remaining_seconds": 0,
            }
            yield {"event": "stage_update", "data": json.dumps(payload)}

        return EventSourceResponse(_already_done())

    # Polling SSE generator — reads DB state every 0.5 s.
    async def _poll_generator() -> AsyncGenerator[dict[str, str], None]:
        # (status, current_stage, cell_progress, total_cells, completed_stages_len)
        last_state_key: tuple[object, ...] | None = None

        # Use a fresh session for each poll to avoid stale reads.
        factory = get_session_factory()

        while True:
            if await request.is_disconnected():
                break

            async with factory() as session:
                row = await session.get(Upload, upload_id)

            if row is None:
                break

            completed = json.loads(row.completed_stages) if row.completed_stages else []
            state_key = (
                row.status,
                row.current_stage,
                row.cell_progress,
                row.total_cells,
                len(completed),
            )

            if state_key != last_state_key:
                last_state_key = state_key

                # Build the event payload.
                stage = row.current_stage or "queued"
                remaining = (
                    estimate_remaining_seconds(completed)
                    + _queue_wait_seconds(upload_id)
                )
                progress_payload = (
                    {"cell": row.cell_progress, "total": row.total_cells}
                    if row.cell_progress is not None
                    else None
                )
                payload = {
                    "stage": stage,
                    "message": None,
                    "progress": progress_payload,
                    "completed_stages": completed,
                    "remaining_seconds": remaining,
                }
                yield {"event": "stage_update", "data": json.dumps(payload)}

                # Terminal states: emit a final 'done' event then close.
                if row.status in ("completed", "failed"):
                    done_message = "completed" if row.status == "completed" else "failed"
                    yield {
                        "event": "stage_update",
                        "data": json.dumps({
                            "stage": "done",
                            "message": done_message,
                            "progress": None,
                            "completed_stages": completed,
                            "remaining_seconds": 0,
                        }),
                    }
                    break

            await asyncio.sleep(0.5)

    return EventSourceResponse(_poll_generator())


# ---------------------------------------------------------------------------
# Cancel endpoint
# ---------------------------------------------------------------------------


@router.delete("/{upload_id}", status_code=204)
async def cancel_upload(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> None:
    """Cancel a queued upload.

    Removes the upload from the process-wide queue, deletes the stored photo
    file, and deletes the DB row.  Only queued uploads can be cancelled;
    in-progress uploads are not user-cancellable in Phase 3.5.

    Returns 204 No Content on success.
    """
    upload = await _fetch_upload_or_404(upload_id, db)
    _check_access(upload, current_user)

    if upload.status != "queued":
        raise HTTPException(
            status_code=400,
            detail=(
                "Only queued uploads can be cancelled. "
                "Running uploads are not user-cancellable."
            ),
        )

    # Remove from the process-wide queue first so the runner (if it wakes up)
    # sees no queue entry and aborts.
    await dequeue(upload.id)

    # Delete the stored photo file.
    file_path = settings.data_dir / upload.image_path
    try:
        await asyncio.to_thread(file_path.unlink, missing_ok=True)
    except OSError:
        pass  # log-worthy but never fail the cancel request

    # Delete the DB row (cancel means "this never happened").
    await db.delete(upload)
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# Retry endpoint
# ---------------------------------------------------------------------------


@router.post("/{upload_id}/retry", status_code=201)
async def retry_upload(
    upload_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Retry a failed upload by creating a new Upload row.

    The original failed row is preserved as evidence (different id).  The new
    row shares the same photo file (content-addressed storage means the bytes
    are already on disk under the same path).

    Returns 201 with the new Upload row's UploadResponse.
    """
    failed = await _fetch_upload_or_404(upload_id, db)
    _check_access(failed, current_user)

    if failed.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed uploads can be retried")

    new_upload = Upload(
        user_id=failed.user_id,
        image_path=failed.image_path,  # share the content-addressed photo file
        status="queued",
        current_stage="queued",
        completed_stages="[]",
    )
    db.add(new_upload)
    await db.commit()
    await db.refresh(new_upload)

    await enqueue(new_upload.id)

    if settings.dispatch_runner_on_create_upload:
        factory = get_session_factory()
        _task = asyncio.create_task(
            run_pipeline_for_upload(
                new_upload.id,
                factory,
                stage_delay_seconds=settings.pipeline_stage_delay_seconds,
                cell_delay_seconds=settings.pipeline_cell_delay_seconds,
            )
        )
        _background_tasks.add(_task)
        _task.add_done_callback(_background_tasks.discard)

    pos = queue_position(new_upload.id)
    return _to_response(new_upload, queued_behind=pos).model_dump(by_alias=True)


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
