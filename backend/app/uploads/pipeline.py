"""Fake pipeline driver for Phase 3 — emits HEARTH_STAGES events on a timer.

Phase 4 replaces the body of run_fake_pipeline (renamed to run_pipeline) with
real VLM calls; the StageEvent dataclass and HEARTH_STAGES_ORDER constant
remain unchanged so the SSE endpoint needs no edits.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass

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

# Hard-coded median durations per stage (Phase 3.5; Phase 4 will replace with
# measured medians from pipeline_stage_durations table).
STAGE_MEDIAN_SECONDS: dict[str, float] = {
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


def estimate_remaining_seconds(completed: list[str]) -> int:
    """Sum medians of remaining stages.

    Used until Phase 4 measures real durations and replaces with computed values.

    Args:
        completed: List of stage keys that have been completed so far.

    Returns:
        Estimated remaining seconds as an integer.
    """
    completed_set = set(completed)
    total = sum(
        STAGE_MEDIAN_SECONDS[s] for s in HEARTH_STAGES_ORDER if s not in completed_set
    )
    return round(total)


# ---------------------------------------------------------------------------
# Event dataclass
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


# ---------------------------------------------------------------------------
# Fake pipeline
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
