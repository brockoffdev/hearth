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
import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.db.models import PipelineStageDuration, Upload
from backend.app.uploads.pipeline import run_fake_pipeline
from backend.app.uploads.queue import acquire_pipeline_slot, queue_position


async def run_pipeline_for_upload(
    upload_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    stage_delay_seconds: float = 1.5,
    cell_delay_seconds: float = 0.15,
) -> None:
    """Background task: run the full pipeline for *upload_id*, writing progress to DB.

    Waits in the process-wide queue, acquires the pipeline lock, then runs
    ``run_fake_pipeline``, persisting each stage transition to the Upload row
    and recording per-stage durations to ``pipeline_stage_durations``.

    On success: sets upload.status='completed', finished_at, provider.
    On failure: sets upload.status='failed', upload.error, finished_at.
    On cancel (dequeued before reaching head): returns early without touching DB.

    Args:
        upload_id: DB primary key of the Upload row to process.
        session_factory: Async session maker (from ``get_session_factory()``).
        stage_delay_seconds: Passed through to run_fake_pipeline.
        cell_delay_seconds: Passed through to run_fake_pipeline.
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

        try:
            stage_start: dict[str, float] = {}
            prev_stage: str | None = None

            pipeline = run_fake_pipeline(
                upload_id,
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
