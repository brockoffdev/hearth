"""Pipeline driver for Hearth upload photos.

Phase 3: run_fake_pipeline — emits HEARTH_STAGES events on a timer.
Phase 4: run_pipeline — real VLM orchestration:
    preprocessing → grid detection → per-cell VLM → HSV color match
    → date normalization → confidence gate → events written to DB via callback.

The StageEvent dataclass and HEARTH_STAGES_ORDER constant are unchanged so
the SSE endpoint needs no edits between phases.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.app.uploads.color import match_ink_color_async
from backend.app.uploads.grid_detect import crop_cell, detect_grid
from backend.app.uploads.preprocessing import preprocess_photo
from backend.app.uploads.storage import read_photo, store_photo
from backend.app.vision import (
    CellPromptContext,
    FamilyPaletteEntry,
    get_vision_provider,
)

if TYPE_CHECKING:
    from backend.app.config import Settings
    from backend.app.db.models import FamilyMember

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage data
# ---------------------------------------------------------------------------

# Order matches HEARTH_STAGES in frontend/src/lib/stages.ts exactly.
HEARTH_STAGES_ORDER: tuple[str, ...] = (
    "received",
    "preprocessing",
    "grid_detected",
    "model_loading",
    "cell_progress",
    "color_matching",
    "date_normalization",
    "confidence_gating",
    "publishing",
    "done",
)

# A "fake" cell count for Phase 3 — Phase 4 replaces with real grid detection.
FAKE_TOTAL_CELLS: int = 35

# Hard-coded baseline values (Phase 3.5 ships these; Phase 4+ measures real).
# These remain as a fallback when pipeline_stage_durations has too few samples.
STAGE_MEDIAN_BASELINE: Final[Mapping[str, float]] = {
    "received": 0.5,
    "preprocessing": 2.0,
    "grid_detected": 1.0,
    "model_loading": 18.0,
    "cell_progress": 280.0,  # 35 cells x 8 sec
    "color_matching": 2.0,
    "date_normalization": 1.0,
    "confidence_gating": 0.5,
    "publishing": 1.5,
    "done": 0.0,
}

# Module-level cache refreshed by the lifespan boot hook.
# Starts at baseline; replaced by refresh_stage_medians_from_db() on startup.
_stage_medians: dict[str, float] = dict(STAGE_MEDIAN_BASELINE)

# Keep STAGE_MEDIAN_SECONDS as a compatibility alias so existing imports don't break.
# Phase 4 Task H deprecates direct references; prefer get_stage_medians() instead.
STAGE_MEDIAN_SECONDS: Mapping[str, float] = _stage_medians


def get_stage_medians() -> Mapping[str, float]:
    """Return the current stage-median map.

    Initially returns STAGE_MEDIAN_BASELINE values.  After the lifespan boot
    hook calls refresh_stage_medians_from_db(), returns measured medians for
    stages with enough samples (fallback: baseline for stages with fewer than
    min_samples_per_stage measurements).

    Returns:
        A mapping from stage name to median duration in seconds.
    """
    return _stage_medians


async def refresh_stage_medians_from_db(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    min_samples_per_stage: int = 5,
) -> None:
    """Recompute stage medians from the pipeline_stage_durations table.

    For each stage:
      - If at least min_samples_per_stage measurements exist, use the median.
      - Otherwise fall back to STAGE_MEDIAN_BASELINE for that stage.

    Updates the module-level _stage_medians dict in place so all callers
    (estimate_remaining_seconds, queue_wait_seconds_simple) see the new values.

    Args:
        session_factory: Async session maker for DB access.
        min_samples_per_stage: Minimum number of measurements required before
            the computed median overrides the baseline value.
    """
    from backend.app.db.models import PipelineStageDuration  # avoid circular import

    async with session_factory() as session:
        stmt = select(PipelineStageDuration.stage, PipelineStageDuration.duration_seconds)
        result = await session.execute(stmt)
        rows = result.all()

    by_stage: dict[str, list[float]] = {}
    for stage, duration in rows:
        by_stage.setdefault(stage, []).append(float(duration))

    new_medians: dict[str, float] = dict(STAGE_MEDIAN_BASELINE)
    for stage, durations in by_stage.items():
        if len(durations) >= min_samples_per_stage:
            durations.sort()
            mid = len(durations) // 2
            if len(durations) % 2 == 0:
                new_medians[stage] = (durations[mid - 1] + durations[mid]) / 2
            else:
                new_medians[stage] = durations[mid]
        # else: leave the baseline value

    _stage_medians.clear()
    _stage_medians.update(new_medians)


FULL_PIPELINE_MEDIAN_SECONDS: int = round(sum(STAGE_MEDIAN_BASELINE.values()))
"""Sum of all stage medians — used as an upper-bound per-upload ETA for queue waits."""


def queue_wait_seconds_simple(position: int) -> int:
    """Upper-bound queue wait: position x full pipeline median.

    Args:
        position: Number of uploads ahead in the queue.
            0 → the upload is at the head (running now) → returns 0.

    Returns:
        Estimated wait in seconds before this upload starts running.
    """
    return position * FULL_PIPELINE_MEDIAN_SECONDS


def estimate_remaining_seconds(completed: list[str]) -> int:
    """Sum medians of remaining stages.

    Reads from get_stage_medians() so results reflect refreshed DB values
    after refresh_stage_medians_from_db() has been called on startup.

    Args:
        completed: List of stage keys that have been completed so far.

    Returns:
        Estimated remaining seconds as an integer.
    """
    completed_set = set(completed)
    medians = get_stage_medians()
    total = sum(medians.get(s, 0.0) for s in HEARTH_STAGES_ORDER if s not in completed_set)
    return round(total)


# ---------------------------------------------------------------------------
# Event dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageEvent:
    stage: str  # one of HEARTH_STAGES_ORDER
    message: str | None = None
    progress: dict[str, int] | None = None  # {"cell": int, "total": int} for cell_progress
    # Phase 3.5: cumulative list of stages completed so far at time of emission.
    completed_stages: list[str] | None = None
    # Phase 3.5: backend-computed ETA in seconds.
    remaining_seconds: int | None = None


@dataclass(frozen=True)
class ExtractedEventRecord:
    """One event extracted from a cell, ready to persist as an Event row.

    Built by run_pipeline for each VLM-detected event and delivered to the
    runner via the on_event_extracted callback.
    """

    cell_row: int
    cell_col: int
    cell_date_iso: str
    title: str
    time_text: str | None
    color_hex: str | None
    family_member_id: int | None
    color_match_confidence: float
    vision_confidence: float
    composite_confidence: float
    raw_vlm_json: str  # the original JSON from the VLM, for audit
    cell_crop_path: str | None  # the saved crop file path, for review UI


# ---------------------------------------------------------------------------
# Fake pipeline (Phase 3 — kept as config-toggleable test mode)
# ---------------------------------------------------------------------------


async def run_fake_pipeline(
    upload_id: int,
    *,
    stage_delay_seconds: float = 0.5,
    cell_delay_seconds: float = 0.05,
) -> AsyncGenerator[StageEvent, None]:
    """Emit stages in order with configurable delays.

    ``cell_progress`` fans out into FAKE_TOTAL_CELLS per-cell events, each
    carrying ``progress={"cell": n, "total": FAKE_TOTAL_CELLS}``.

    Each event carries ``completed_stages`` (stages completed before this event
    was emitted) and ``remaining_seconds`` (ETA from hard-coded medians).

    For ``cell_progress`` sub-events, ``completed_stages`` does NOT include
    ``cell_progress`` (it's still in flight) — only the cell number advances.

    Args:
        upload_id: The Upload row id being processed (not used in the fake
            implementation; present for API compatibility with Phase 4).
        stage_delay_seconds: Pause before each non-first stage.
        cell_delay_seconds: Pause between consecutive cell_progress events.

    Yields:
        StageEvent instances in HEARTH_STAGES_ORDER order.
    """
    _ = upload_id  # unused in Phase 3; Phase 4 will use it for VLM calls
    completed: list[str] = []
    first = True
    for stage_key in HEARTH_STAGES_ORDER:
        if first:
            first = False
        else:
            if stage_delay_seconds > 0:
                await asyncio.sleep(stage_delay_seconds)

        if stage_key == "cell_progress":
            # Fan out into per-cell sub-events.
            # completed_stages does NOT include cell_progress during cell events —
            # the stage is still in flight.
            for cell_n in range(1, FAKE_TOTAL_CELLS + 1):
                yield StageEvent(
                    stage="cell_progress",
                    progress={"cell": cell_n, "total": FAKE_TOTAL_CELLS},
                    completed_stages=completed.copy(),
                    remaining_seconds=estimate_remaining_seconds(completed),
                )
                if cell_delay_seconds > 0 and cell_n < FAKE_TOTAL_CELLS:
                    await asyncio.sleep(cell_delay_seconds)
        else:
            yield StageEvent(
                stage=stage_key,
                completed_stages=completed.copy(),
                remaining_seconds=estimate_remaining_seconds(completed),
            )

        # Mark stage as completed after yielding (so "received" event has
        # completed_stages=[], meaning received hasn't finished yet at emit time).
        completed.append(stage_key)


# ---------------------------------------------------------------------------
# Real pipeline (Phase 4)
# ---------------------------------------------------------------------------


async def run_pipeline(
    upload_id: int,
    image_path: str,
    settings: Settings,
    family_members: Sequence[FamilyMember],
    *,
    stage_delay_seconds: float = 0.0,
    cell_delay_seconds: float = 0.0,
    few_shot_corrections: Sequence[dict[str, str]] = (),
    on_event_extracted: Callable[[ExtractedEventRecord], Awaitable[None]] | None = None,
    data_dir: Path = Path("/data"),
) -> AsyncGenerator[StageEvent, None]:
    """Run the real VLM pipeline for one upload.

    Yields StageEvent in order matching HEARTH_STAGES_ORDER.  Same shape as
    run_fake_pipeline so the SSE consumer doesn't change.

    As each cell yields VLM events, on_event_extracted is called for each
    ExtractedEventRecord so the runner can persist them without coupling this
    module to the DB session.

    Args:
        upload_id: DB primary key of the Upload row being processed.
        image_path: Relative path to the photo file (relative to data_dir).
        settings: Application settings; used to build the VisionProvider.
        family_members: FamilyMember rows for color matching and palette context.
        stage_delay_seconds: Optional throttle pause between non-cell stages.
        cell_delay_seconds: Optional throttle pause between cell processing steps.
        few_shot_corrections: Recent user corrections for few-shot VLM context.
        on_event_extracted: Async callback fired after each event record is
            built.  The runner supplies a callback that persists to the DB.
        data_dir: Root directory for reading and writing photos.

    Yields:
        StageEvent instances in HEARTH_STAGES_ORDER order.
    """
    completed: list[str] = []

    # ------------------------------------------------------------------
    # Stage 1: received
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="received",
        completed_stages=completed.copy(),
        remaining_seconds=estimate_remaining_seconds(completed),
    )
    completed.append("received")
    if stage_delay_seconds > 0:
        await asyncio.sleep(stage_delay_seconds)

    # Read the photo bytes from disk.
    raw_bytes = await read_photo(image_path, data_dir)

    # ------------------------------------------------------------------
    # Stage 2: preprocessing
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="preprocessing",
        completed_stages=completed.copy(),
        remaining_seconds=estimate_remaining_seconds(completed),
    )
    preprocessed_bytes = await preprocess_photo(raw_bytes)
    completed.append("preprocessing")
    if stage_delay_seconds > 0:
        await asyncio.sleep(stage_delay_seconds)

    # ------------------------------------------------------------------
    # Stage 3: grid_detected
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="grid_detected",
        completed_stages=completed.copy(),
        remaining_seconds=estimate_remaining_seconds(completed),
    )
    grid = await detect_grid(preprocessed_bytes)
    completed.append("grid_detected")

    if not grid.cells:
        # Catastrophic failure — no cells to process.  Skip straight to done.
        logger.warning(
            "pipeline: upload_id=%d grid detection returned empty cells; "
            "skipping VLM processing",
            upload_id,
        )
        if stage_delay_seconds > 0:
            await asyncio.sleep(stage_delay_seconds)

        for skip_stage in (
            "model_loading",
            "cell_progress",
            "color_matching",
            "date_normalization",
            "confidence_gating",
            "publishing",
        ):
            yield StageEvent(
                stage=skip_stage,
                completed_stages=completed.copy(),
                remaining_seconds=estimate_remaining_seconds(completed),
            )
            completed.append(skip_stage)

        yield StageEvent(
            stage="done",
            completed_stages=completed.copy(),
            remaining_seconds=0,
        )
        return

    if stage_delay_seconds > 0:
        await asyncio.sleep(stage_delay_seconds)

    # ------------------------------------------------------------------
    # Stage 4: model_loading
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="model_loading",
        completed_stages=completed.copy(),
        remaining_seconds=estimate_remaining_seconds(completed),
    )
    provider = get_vision_provider(settings)
    completed.append("model_loading")
    if stage_delay_seconds > 0:
        await asyncio.sleep(stage_delay_seconds)

    # Build the family palette for VLM context.
    palette = tuple(
        FamilyPaletteEntry(
            name=fm.name,
            color_label=_color_label_for(fm),
            color_hex=fm.color_hex_center,
        )
        for fm in family_members
    )

    # ------------------------------------------------------------------
    # Stage 5: cell_progress (loop over all detected cells)
    # ------------------------------------------------------------------
    total_cells = len(grid.cells)
    today = date.today()

    for i, cell in enumerate(grid.cells, start=1):
        yield StageEvent(
            stage="cell_progress",
            progress={"cell": i, "total": total_cells},
            completed_stages=completed.copy(),
            remaining_seconds=estimate_remaining_seconds(completed),
        )

        # Crop the cell bytes.
        try:
            cell_bytes = crop_cell(preprocessed_bytes, cell)
        except Exception:
            logger.warning(
                "pipeline: upload_id=%d failed to crop cell row=%d col=%d; skipping",
                upload_id, cell.row, cell.col,
            )
            continue

        # Save the crop for the review UI (Phase 6 will display it).
        cell_crop_path: str | None = None
        try:
            _sha, rel_path = await store_photo(cell_bytes, "image/jpeg", data_dir)
            cell_crop_path = rel_path
        except Exception:
            logger.warning(
                "pipeline: upload_id=%d failed to store cell crop row=%d col=%d",
                upload_id, cell.row, cell.col,
            )

        # Determine the calendar date for this cell.
        cell_date_iso = _compute_cell_date_iso(cell, photographed_month=today)
        cell_label = _format_cell_label(cell_date_iso)

        # Build VLM prompt context.
        context = CellPromptContext(
            cell_date_iso=cell_date_iso,
            cell_label=cell_label,
            family_palette=palette,
            few_shot_corrections=tuple(few_shot_corrections),
        )

        # VLM call — errors are caught per-cell so the pipeline continues.
        try:
            vlm_events = await provider.extract_events_from_cell(cell_bytes, context)
        except Exception as exc:
            logger.warning(
                "pipeline: upload_id=%d VLM call failed for cell row=%d col=%d: %s",
                upload_id, cell.row, cell.col, exc,
            )
            vlm_events = ()

        # Color match this cell independently of the VLM result.
        color_match = await match_ink_color_async(cell_bytes, family_members)

        # Build a record for each VLM-extracted event.
        for vlm_event in vlm_events:
            family_member_id = color_match.family_member_id if color_match else None
            color_match_confidence = color_match.confidence if color_match else 0.0

            # Date confidence: deterministic computation → 1.0 for Phase 4.
            date_confidence = 1.0

            composite = vlm_event.confidence * max(color_match_confidence, 0.3) * date_confidence

            record = ExtractedEventRecord(
                cell_row=cell.row,
                cell_col=cell.col,
                cell_date_iso=cell_date_iso,
                title=vlm_event.title,
                time_text=vlm_event.time_text,
                color_hex=vlm_event.color_hex,
                family_member_id=family_member_id,
                color_match_confidence=color_match_confidence,
                vision_confidence=vlm_event.confidence,
                composite_confidence=composite,
                raw_vlm_json=json.dumps(asdict(vlm_event)),
                cell_crop_path=cell_crop_path,
            )

            if on_event_extracted is not None:
                await on_event_extracted(record)

        if cell_delay_seconds > 0:
            await asyncio.sleep(cell_delay_seconds)

    completed.append("cell_progress")

    # ------------------------------------------------------------------
    # Stage 6: color_matching — marker stage (already done per-cell above)
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="color_matching",
        completed_stages=completed.copy(),
        remaining_seconds=estimate_remaining_seconds(completed),
    )
    completed.append("color_matching")
    if stage_delay_seconds > 0:
        await asyncio.sleep(stage_delay_seconds)

    # ------------------------------------------------------------------
    # Stage 7: date_normalization — marker stage (already done per-cell above)
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="date_normalization",
        completed_stages=completed.copy(),
        remaining_seconds=estimate_remaining_seconds(completed),
    )
    completed.append("date_normalization")
    if stage_delay_seconds > 0:
        await asyncio.sleep(stage_delay_seconds)

    # ------------------------------------------------------------------
    # Stage 8: confidence_gating
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="confidence_gating",
        completed_stages=completed.copy(),
        remaining_seconds=estimate_remaining_seconds(completed),
    )
    completed.append("confidence_gating")
    if stage_delay_seconds > 0:
        await asyncio.sleep(stage_delay_seconds)

    # ------------------------------------------------------------------
    # Stage 9: publishing — actual GCal push is Phase 7; marker only here.
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="publishing",
        completed_stages=completed.copy(),
        remaining_seconds=estimate_remaining_seconds(completed),
    )
    completed.append("publishing")
    if stage_delay_seconds > 0:
        await asyncio.sleep(stage_delay_seconds)

    # ------------------------------------------------------------------
    # Stage 10: done
    # ------------------------------------------------------------------
    yield StageEvent(
        stage="done",
        completed_stages=completed.copy(),
        remaining_seconds=0,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _color_label_for(fm: FamilyMember) -> str:
    """Derive a friendly color label from a FamilyMember's color_hex_center.

    Covers the five canonical Hearth ink colors seeded in migration 0002.
    Falls back to "Unknown" for any unrecognised hex.

    Args:
        fm: A FamilyMember row (or any object with a color_hex_center attribute).

    Returns:
        A descriptive label such as "Blue", "Red", "Purple", "Pink", "Orange".
    """
    _hex_labels: dict[str, str] = {
        "#2E5BA8": "Blue",
        "#C0392B": "Red",
        "#7B4FB8": "Purple",
        "#E17AA1": "Pink",
        "#D97A2C": "Orange",
    }
    return _hex_labels.get(fm.color_hex_center.upper(), "Unknown")


def _compute_cell_date_iso(cell: object, *, photographed_month: date) -> str:
    """Compute the ISO date for a grid cell.

    The grid's first row (row 0) starts on the Sunday on or immediately before
    the first day of *photographed_month*.  Each column is one day of the week
    (0=Sunday … 6=Saturday); each row is one week.

    Args:
        cell: An object with ``row`` and ``col`` integer attributes
            (a :class:`~backend.app.uploads.grid_detect.CellBox`).
        photographed_month: Any date within the photographed month; only the
            year and month are used.

    Returns:
        ISO 8601 date string, e.g. ``"2026-04-27"``.
    """
    first_of_month = photographed_month.replace(day=1)
    # weekday(): Mon=0 … Sun=6.  Days since the preceding Sunday:
    days_to_sunday = (first_of_month.weekday() + 1) % 7
    grid_start = first_of_month - timedelta(days=days_to_sunday)

    row: int = cell.row  # type: ignore[attr-defined]
    col: int = cell.col  # type: ignore[attr-defined]
    cell_date = grid_start + timedelta(days=row * 7 + col)
    return cell_date.isoformat()


def _format_cell_label(iso_date: str) -> str:
    """Format an ISO date as a human-friendly cell label.

    Args:
        iso_date: An ISO 8601 date string, e.g. ``"2026-04-27"``.

    Returns:
        A string such as ``"Monday April 27"``.
    """
    d = date.fromisoformat(iso_date)
    return d.strftime("%A %B %-d")
