"""Tests for STAGE_MEDIAN_SECONDS and estimate_remaining_seconds helper.

Phase 3.5 uses hard-coded medians; Phase 4 will replace with measured values.
"""

from __future__ import annotations

from backend.app.uploads.pipeline import (
    HEARTH_STAGES_ORDER,
    STAGE_MEDIAN_SECONDS,
    estimate_remaining_seconds,
)


def test_stage_median_seconds_covers_all_stages() -> None:
    """Every stage in HEARTH_STAGES_ORDER must have an entry in STAGE_MEDIAN_SECONDS."""
    for stage in HEARTH_STAGES_ORDER:
        assert stage in STAGE_MEDIAN_SECONDS, (
            f"Stage '{stage}' missing from STAGE_MEDIAN_SECONDS"
        )


def test_estimate_remaining_seconds_full_pipeline() -> None:
    """completed=[] should return sum of all median seconds."""
    total = sum(STAGE_MEDIAN_SECONDS[s] for s in HEARTH_STAGES_ORDER)
    assert estimate_remaining_seconds([]) == round(total)


def test_estimate_remaining_seconds_after_one_stage() -> None:
    """completed=['received'] should return sum minus median for 'received'."""
    total = sum(STAGE_MEDIAN_SECONDS[s] for s in HEARTH_STAGES_ORDER)
    expected = round(total - STAGE_MEDIAN_SECONDS["received"])
    assert estimate_remaining_seconds(["received"]) == expected


def test_estimate_remaining_seconds_almost_done() -> None:
    """completed=[all but 'done', 'publishing'] → median['publishing'] + median['done']."""
    completed = [s for s in HEARTH_STAGES_ORDER if s not in ("done", "publishing")]
    expected = round(STAGE_MEDIAN_SECONDS["publishing"] + STAGE_MEDIAN_SECONDS["done"])
    assert estimate_remaining_seconds(completed) == expected


def test_estimate_remaining_seconds_done() -> None:
    """completed=all stages → 0."""
    all_stages = list(HEARTH_STAGES_ORDER)
    assert estimate_remaining_seconds(all_stages) == 0


def test_estimate_remaining_seconds_decreases_monotonically() -> None:
    """Progressively completing stages should never increase remaining seconds."""
    completed: list[str] = []
    prev = estimate_remaining_seconds(completed)
    for stage in HEARTH_STAGES_ORDER:
        completed.append(stage)
        current = estimate_remaining_seconds(completed)
        assert current <= prev, (
            f"remaining_seconds increased after completing '{stage}': "
            f"{prev} → {current}"
        )
        prev = current
