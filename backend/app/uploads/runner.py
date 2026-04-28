"""Background pipeline runner for Hearth uploads.

Decoupled from the SSE endpoint: the runner is dispatched as an asyncio.Task
by POST /api/uploads, and runs to completion regardless of whether any SSE
client is connected.

The SSE endpoint polls the Upload DB row for state changes (0.5s cadence).
This polling model trades ~0.5s latency for simplicity; given the fake
pipeline's per-stage delay of 1.5s the latency is imperceptible.

Phase 5 may replace polling with a pub/sub channel (e.g. Redis Pub/Sub) if
sub-second SSE latency becomes important.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime
from datetime import time as dt_time

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.config import Settings, get_settings
from backend.app.config_overrides import get_effective_settings
from backend.app.db.models import Event, FamilyMember, PipelineStageDuration, Upload
from backend.app.google.publish import (
    GcalError,
    InvalidGrantError,
    NoCalendarError,
    NoOauthError,
    publish_event,
)
from backend.app.uploads.few_shot import fetch_recent_corrections
from backend.app.uploads.pipeline import (
    ExtractedEventRecord,
    StageEvent,
    run_fake_pipeline,
    run_pipeline,
)
from backend.app.uploads.preprocessing import extract_photographed_date
from backend.app.uploads.queue import acquire_pipeline_slot, enqueue, queue_position
from backend.app.uploads.storage import read_photo
from backend.app.vision import get_effective_vision_provider

logger = logging.getLogger(__name__)


def _parse_event_datetime(iso_date: str, time_text: str | None) -> datetime:
    """Combine an ISO date string with an optional time string into a datetime.

    Tries several common time formats (12-hour with AM/PM, 24-hour, etc.).
    Falls back to midnight when time_text is None or cannot be parsed.

    Args:
        iso_date: ISO 8601 date string, e.g. ``"2026-04-27"``.
        time_text: Human-readable time string, e.g. ``"8:30 AM"`` or ``"14:00"``.
            May be ``None`` for all-day events.

    Returns:
        Combined :class:`datetime` with no timezone (naive UTC-local).
    """
    base = date.fromisoformat(iso_date)
    if not time_text:
        return datetime.combine(base, dt_time(0, 0))

    for fmt in ("%I:%M %p", "%I:%M%p", "%I %p", "%I%p", "%H:%M", "%H"):
        try:
            t = datetime.strptime(time_text.strip(), fmt).time()
            return datetime.combine(base, t)
        except ValueError:
            continue

    # Fall back to midnight if no format matched.
    logger.warning("runner: could not parse time_text=%r; using midnight", time_text)
    return datetime.combine(base, dt_time(0, 0))


async def _demote_to_pending_review(
    db: AsyncSession,
    event_id: int,
    reason: str,
) -> None:
    """Update event to pending_review and append a failure note."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        return
    event.status = "pending_review"
    existing = event.notes or ""
    event.notes = existing + f"\n\n[Auto-publish failed: {reason}]"
    await db.commit()


async def persist_and_maybe_publish(
    record: ExtractedEventRecord,
    *,
    upload_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    publish_state: dict[str, bool],
    confidence_threshold: float | None = None,
) -> None:
    """Persist one extracted event and, when eligible, push it to GCal.

    publish_state is a mutable dict with key "oauth_broken" (bool).  When a
    previous call in the same pipeline run hit an InvalidGrantError the flag is
    set to True; subsequent auto-publish attempts are skipped so we don't flood
    the Google API with doomed refresh calls.

    confidence_threshold overrides settings.confidence_threshold when provided,
    letting the runner inject the effective (DB-override-aware) value.
    """
    start_dt = _parse_event_datetime(record.cell_date_iso, record.time_text)
    effective_threshold = (
        confidence_threshold
        if confidence_threshold is not None
        else settings.confidence_threshold
    )
    status = (
        "auto_published"
        if record.composite_confidence >= effective_threshold
        else "pending_review"
    )
    event = Event(
        upload_id=upload_id,
        family_member_id=record.family_member_id,
        title=record.title,
        start_dt=start_dt,
        end_dt=None,
        all_day=record.time_text is None,
        location=None,
        notes=None,
        confidence=record.composite_confidence,
        status=status,
        google_event_id=None,
        cell_crop_path=record.cell_crop_path,
        raw_vlm_json=record.raw_vlm_json,
    )
    async with session_factory() as db:
        db.add(event)
        await db.commit()
        await db.refresh(event)
        event_id = event.id

    if (
        settings.auto_publish_to_gcal
        and status == "auto_published"
        and record.family_member_id is not None
    ):
        if publish_state["oauth_broken"]:
            async with session_factory() as db:
                await _demote_to_pending_review(db, event_id, "OAuth token invalid")
        else:
            async with session_factory() as db:
                try:
                    await publish_event(db, event_id, settings=settings)
                except InvalidGrantError as exc:
                    logger.warning(
                        "auto-publish: invalid grant; remaining events will skip publish: %s",
                        exc,
                    )
                    publish_state["oauth_broken"] = True
                    # publish_event already marks the global broken flag via
                    # health_state.mark_oauth_broken on RefreshError.
                    await _demote_to_pending_review(db, event_id, "OAuth token invalid")
                except (NoOauthError, NoCalendarError, GcalError) as exc:
                    logger.warning("auto-publish: %s for event=%d", exc, event_id)
                    await _demote_to_pending_review(db, event_id, str(exc))
                except Exception:
                    logger.exception("auto-publish: unexpected failure for event=%d", event_id)
                    await _demote_to_pending_review(db, event_id, "unexpected error")


async def _run_chosen_pipeline(
    upload_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stage_delay_seconds: float,
    cell_delay_seconds: float,
) -> AsyncGenerator[StageEvent, None]:
    """Dispatch to the real or fake pipeline based on settings.use_real_pipeline.

    When the real pipeline is active, supply a DB-persisting callback for
    each extracted event.  When the fake pipeline is active, forward the
    timing knobs through unchanged.

    Args:
        upload_id: DB primary key of the Upload row to process.
        session_factory: Async session maker for the real pipeline's callback.
        stage_delay_seconds: Passed through to the chosen pipeline.
        cell_delay_seconds: Passed through to the chosen pipeline.

    Yields:
        StageEvent from whichever pipeline is active.
    """
    settings = get_settings()

    if settings.use_real_pipeline:
        # Load the upload row to get the image path.
        async with session_factory() as session:
            upload = await session.get(Upload, upload_id)
            if upload is None:
                return
            image_path = upload.image_path
            # Capture uploaded_at before the session closes.
            upload_date: date | None = (
                upload.uploaded_at.date() if upload.uploaded_at else None
            )

        # Load family members for color matching and VLM palette context.
        async with session_factory() as session:
            result = await session.execute(select(FamilyMember))
            family_members = list(result.scalars().all())

        # Resolve effective settings (DB overrides + env) and vision provider.
        async with session_factory() as session:
            effective = await get_effective_settings(session)
            provider = await get_effective_vision_provider(session)
        effective_few_shot_window: int = effective["few_shot_correction_window"]
        effective_confidence: float = effective["confidence_threshold"]

        # Fetch recent corrections for the few-shot VLM prompt (once per run).
        if effective_few_shot_window > 0:
            async with session_factory() as session:
                corrections = await fetch_recent_corrections(
                    session, limit=effective_few_shot_window
                )
        else:
            corrections = ()

        # Extract photographed date from EXIF (best effort).
        photographed_date: date | None = None
        try:
            raw_bytes = await read_photo(image_path, settings.data_dir)
            photographed_date = await asyncio.to_thread(extract_photographed_date, raw_bytes)
        except Exception:
            logger.warning("runner: failed to read photo for EXIF extraction")

        # Fall back to upload.uploaded_at.date() if EXIF unavailable.
        if photographed_date is None:
            photographed_date = upload_date if upload_date is not None else date.today()
            logger.info(
                "runner: no EXIF DateTimeOriginal; using upload date %s", photographed_date
            )

        publish_state: dict[str, bool] = {"oauth_broken": False}

        async def on_event_extracted(record: ExtractedEventRecord) -> None:
            await persist_and_maybe_publish(
                record,
                upload_id=upload_id,
                session_factory=session_factory,
                settings=settings,
                publish_state=publish_state,
                confidence_threshold=effective_confidence,
            )

        async for stage_event in run_pipeline(
            upload_id,
            image_path,
            settings,
            family_members,
            stage_delay_seconds=stage_delay_seconds,
            cell_delay_seconds=cell_delay_seconds,
            few_shot_corrections=corrections,
            on_event_extracted=on_event_extracted,
            data_dir=settings.data_dir,
            photographed_month=photographed_date,
            vision_provider_instance=provider,
        ):
            yield stage_event
    else:
        async for stage_event in run_fake_pipeline(
            upload_id,
            stage_delay_seconds=stage_delay_seconds,
            cell_delay_seconds=cell_delay_seconds,
        ):
            yield stage_event


async def run_pipeline_for_upload(
    upload_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stage_delay_seconds: float = 1.5,
    cell_delay_seconds: float = 0.15,
) -> None:
    """Background task: run the full pipeline for *upload_id*, writing progress to DB.

    Waits in the process-wide queue, acquires the pipeline lock, then runs
    the chosen pipeline (real or fake), persisting each stage transition to
    the Upload row and recording per-stage durations to
    ``pipeline_stage_durations``.

    On success: sets upload.status='completed', finished_at, provider.
    On failure: sets upload.status='failed', upload.error, finished_at.
    On cancel (dequeued before reaching head): returns early without touching DB.

    Args:
        upload_id: DB primary key of the Upload row to process.
        session_factory: Async session maker (from ``get_session_factory()``).
        stage_delay_seconds: Passed through to the active pipeline.
        cell_delay_seconds: Passed through to the active pipeline.
    """
    # Spin-wait while queued behind other uploads.  If the upload is dequeued
    # (cancelled) before it reaches the head, abort silently.
    while True:
        pos = queue_position(upload_id)
        if pos is None:
            # Cancelled (dequeued) before we started — abort.
            return
        if pos == 0:
            break
        await asyncio.sleep(1.0)

    # Acquire the pipeline lock and pop ourselves from the queue.
    async with acquire_pipeline_slot(upload_id):
        # Check the row hasn't been cancelled/deleted while we waited.
        async with session_factory() as session:
            upload = await session.get(Upload, upload_id)
            if upload is None or upload.status in ("completed", "failed"):
                return

            upload.status = "processing"
            await session.commit()

        settings = get_settings()

        try:
            stage_start: dict[str, float] = {}
            prev_stage: str | None = None

            pipeline = _run_chosen_pipeline(
                upload_id,
                session_factory,
                stage_delay_seconds=stage_delay_seconds,
                cell_delay_seconds=cell_delay_seconds,
            )
            async for stage_event in pipeline:
                now_mono = time.monotonic()

                # Record duration for the previous stage on transition.
                if prev_stage is not None and prev_stage != stage_event.stage:
                    duration = now_mono - stage_start[prev_stage]
                    async with session_factory() as session:
                        session.add(
                            PipelineStageDuration(
                                upload_id=upload_id,
                                stage=prev_stage,
                                duration_seconds=duration,
                            )
                        )
                        await session.commit()

                if stage_event.stage not in stage_start:
                    stage_start[stage_event.stage] = now_mono

                # Persist current progress to the Upload row.
                async with session_factory() as session:
                    upload = await session.get(Upload, upload_id)
                    if upload is None:
                        return  # row was deleted (shouldn't happen, but be safe)

                    upload.current_stage = stage_event.stage
                    upload.completed_stages = json.dumps(stage_event.completed_stages or [])
                    if stage_event.progress:
                        upload.cell_progress = stage_event.progress["cell"]
                        upload.total_cells = stage_event.progress["total"]

                    if stage_event.stage == "done":
                        upload.status = "completed"
                        upload.finished_at = datetime.now(UTC)
                        if settings.use_real_pipeline:
                            # Resolve overrides at completion time so the
                            # provenance string matches the provider that
                            # actually ran (admin may have changed providers
                            # since this upload started).
                            effective = await get_effective_settings(session)
                            upload.provider = (
                                f"{effective['vision_provider']}:"
                                f"{effective['vision_model']}"
                            )
                        else:
                            upload.provider = "fake-pipeline-phase-3p5"

                    await session.commit()

                prev_stage = stage_event.stage

                if stage_event.stage == "done":
                    break

            # Record final stage duration.
            if prev_stage and prev_stage in stage_start:
                duration = time.monotonic() - stage_start[prev_stage]
                async with session_factory() as session:
                    session.add(
                        PipelineStageDuration(
                            upload_id=upload_id,
                            stage=prev_stage,
                            duration_seconds=duration,
                        )
                    )
                    await session.commit()

        except Exception as exc:
            async with session_factory() as session:
                upload = await session.get(Upload, upload_id)
                if upload is not None:
                    upload.status = "failed"
                    upload.error = str(exc)
                    upload.finished_at = datetime.now(UTC)
                    await session.commit()
            raise


# Module-level set to prevent GC of recovery tasks before they complete.
_recovery_tasks: set[asyncio.Task[None]] = set()


async def recover_pending_uploads(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """On server boot, scan for stranded uploads and re-enqueue them.

    Phase 3.5's queue is process-local; if the server crashes mid-pipeline
    a row stays in status='processing' or 'queued' forever.  This sweep:
      1. Finds all Upload WHERE status IN ('queued', 'processing').
      2. Resets 'processing' → 'queued' (we're starting from scratch).
      3. Clears all partial-progress fields.
      4. enqueue()s each one + creates an asyncio.Task for run_pipeline_for_upload.

    Re-running from scratch is safe because:
      - Photos are already on disk (content-addressed storage).
      - Pipelines are side-effect-free until 'publishing' (Phase 7).

    Args:
        session_factory: Async session maker for DB access.

    Returns:
        The number of uploads re-enqueued.
    """
    async with session_factory() as session:
        stmt = select(Upload).where(Upload.status.in_(["queued", "processing"]))
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        upload_ids = [u.id for u in rows]

        for upload in rows:
            upload.status = "queued"
            upload.current_stage = "queued"
            upload.completed_stages = "[]"
            upload.cell_progress = None
            upload.total_cells = None
            upload.error = None
            upload.finished_at = None

        # Delete any partial Event rows from prior crash-interrupted runs.
        if upload_ids:
            await session.execute(
                delete(Event).where(Event.upload_id.in_(upload_ids))
            )

        if rows:
            await session.commit()

    # After the commit, re-enqueue and dispatch each recovered upload.
    for upload in rows:
        await enqueue(upload.id)
        task: asyncio.Task[None] = asyncio.create_task(
            run_pipeline_for_upload(upload.id, session_factory)
        )
        _recovery_tasks.add(task)
        task.add_done_callback(_recovery_tasks.discard)

    return len(rows)
