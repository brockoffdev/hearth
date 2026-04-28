"""Tests for the run_fake_pipeline generator — Phase 3.5 additions.

Verifies that StageEvent carries completed_stages and remaining_seconds
correctly across all stages including the cell_progress fan-out.
"""

from __future__ import annotations

import pytest

from backend.app.uploads.pipeline import (
    FAKE_TOTAL_CELLS,
    HEARTH_STAGES_ORDER,
    StageEvent,
    estimate_remaining_seconds,
    run_fake_pipeline,
)


async def _collect_all_events() -> list[StageEvent]:
    """Run the fake pipeline with zero delays and collect all events."""
    events: list[StageEvent] = []
    async for event in run_fake_pipeline(
        upload_id=1,
        stage_delay_seconds=0,
        cell_delay_seconds=0,
    ):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_pipeline_completed_stages_starts_empty_for_received() -> None:
    """The 'received' event should have completed_stages=[] (not yet complete)."""
    events = await _collect_all_events()
    received = next(e for e in events if e.stage == "received")
    assert received.completed_stages == []


@pytest.mark.asyncio
async def test_pipeline_completed_stages_progress() -> None:
    """Each non-cell_progress stage carries cumulative completed_stages up to that point.

    At emit time, the current stage hasn't been appended yet — only prior stages appear.
    cell_progress is added to completed after the fan-out completes, so stages after
    cell_progress will see it in completed_stages.
    """
    events = await _collect_all_events()
    # Filter to one-per-stage events (skip cell sub-events)
    stage_events = [e for e in events if e.stage != "cell_progress"]

    # Build expected completed_stages at each emit point:
    # at emit time, the stage hasn't been added yet — only prior stages.
    # cell_progress IS included in completed for stages after it.
    expected_completed_at_emit: list[list[str]] = []
    accumulated: list[str] = []
    for stage in HEARTH_STAGES_ORDER:
        if stage == "cell_progress":
            # cell_progress is added to accumulated; skipped from representative stage_events
            accumulated.append(stage)
            continue
        expected_completed_at_emit.append(accumulated.copy())
        accumulated.append(stage)

    for event, expected in zip(stage_events, expected_completed_at_emit, strict=False):
        assert event.completed_stages == expected, (
            f"Stage '{event.stage}': expected completed_stages={expected}, "
            f"got {event.completed_stages}"
        )


@pytest.mark.asyncio
async def test_pipeline_cell_progress_completed_stages_stable() -> None:
    """cell_progress events should keep completed_stages stable (cell_progress not added)."""
    events = await _collect_all_events()
    cell_events = [e for e in events if e.stage == "cell_progress"]
    assert len(cell_events) == FAKE_TOTAL_CELLS

    # All cell events should have the same completed_stages.
    first_cs = cell_events[0].completed_stages
    for ev in cell_events:
        assert ev.completed_stages == first_cs, (
            f"cell_progress event has inconsistent completed_stages: {ev.completed_stages}"
        )

    # cell_progress itself must NOT appear in completed_stages during the fan-out.
    assert first_cs is not None
    assert "cell_progress" not in first_cs


@pytest.mark.asyncio
async def test_pipeline_cell_progress_updates_cell_number() -> None:
    """cell_progress events advance cellProgress from 1..FAKE_TOTAL_CELLS."""
    events = await _collect_all_events()
    cell_events = [e for e in events if e.stage == "cell_progress"]
    assert len(cell_events) == FAKE_TOTAL_CELLS
    for n, ev in enumerate(cell_events, start=1):
        assert ev.progress == {"cell": n, "total": FAKE_TOTAL_CELLS}


@pytest.mark.asyncio
async def test_pipeline_remaining_seconds_decreases() -> None:
    """remaining_seconds should be non-increasing across successive stage events."""
    events = await _collect_all_events()
    # Take one representative event per logical stage transition (first of each stage).
    seen_stages: set[str] = set()
    representative: list[StageEvent] = []
    for ev in events:
        if ev.stage not in seen_stages:
            representative.append(ev)
            seen_stages.add(ev.stage)

    prev_remaining = representative[0].remaining_seconds
    assert prev_remaining is not None
    for ev in representative[1:]:
        assert ev.remaining_seconds is not None
        assert ev.remaining_seconds <= prev_remaining, (
            f"remaining_seconds increased at stage '{ev.stage}': "
            f"{prev_remaining} → {ev.remaining_seconds}"
        )
        prev_remaining = ev.remaining_seconds


@pytest.mark.asyncio
async def test_pipeline_done_event_has_all_stages_completed() -> None:
    """The 'done' event should have completed_stages containing all prior stages."""
    events = await _collect_all_events()
    done_event = next(e for e in events if e.stage == "done")
    assert done_event.completed_stages is not None
    # At 'done' emit time, 'done' itself is not yet complete — all others are.
    for stage in HEARTH_STAGES_ORDER:
        if stage != "done":
            assert stage in done_event.completed_stages, (
                f"Stage '{stage}' missing from done event's completed_stages"
            )


@pytest.mark.asyncio
async def test_pipeline_remaining_seconds_on_received_is_full_sum() -> None:
    """At 'received' (completed=[]), remaining_seconds equals sum of all medians."""
    events = await _collect_all_events()
    received = next(e for e in events if e.stage == "received")
    expected = estimate_remaining_seconds([])
    assert received.remaining_seconds == expected


@pytest.mark.asyncio
async def test_fake_pipeline_grid_detected_carries_total_cells() -> None:
    """The grid_detected StageEvent from run_fake_pipeline carries progress.total > 0.

    This ensures the UI can render "of N" immediately after grid detection,
    before the slow model_loading stage begins.
    """
    events = await _collect_all_events()
    grid_event = next(e for e in events if e.stage == "grid_detected")
    assert grid_event.progress is not None, "grid_detected event must carry progress"
    assert grid_event.progress["total"] > 0, "progress.total must be > 0"
    assert grid_event.progress["cell"] == 0, "progress.cell must be 0 at grid_detected"
    assert grid_event.progress["total"] == FAKE_TOTAL_CELLS
