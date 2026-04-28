"""Tests for stage median constants and estimate_remaining_seconds helper.

Phase 3.5 used STAGE_MEDIAN_SECONDS (static dict).
Phase 4 Task H replaces it with STAGE_MEDIAN_BASELINE (Final constant) +
get_stage_medians() (dynamic, DB-refreshable cache).

These tests pin the baseline values and verify estimate_remaining_seconds
behaviour using the baseline-seeded cache (no DB required).
"""

from __future__ import annotations

from backend.app.uploads.pipeline import (
    HEARTH_STAGES_ORDER,
    STAGE_MEDIAN_BASELINE,
    estimate_remaining_seconds,
    get_stage_medians,
)


def test_stage_median_baseline_covers_all_stages() -> None:
    """Every stage in HEARTH_STAGES_ORDER must have an entry in STAGE_MEDIAN_BASELINE."""
    for stage in HEARTH_STAGES_ORDER:
        assert stage in STAGE_MEDIAN_BASELINE, (
            f"Stage '{stage}' missing from STAGE_MEDIAN_BASELINE"
        )


def test_get_stage_medians_covers_all_stages() -> None:
    """get_stage_medians() must return an entry for every stage (at least baseline)."""
    medians = get_stage_medians()
    for stage in HEARTH_STAGES_ORDER:
        assert stage in medians, (
            f"Stage '{stage}' missing from get_stage_medians()"
        )


def test_estimate_remaining_seconds_full_pipeline() -> None:
    """completed=[] should return sum of all median seconds."""
    total = sum(STAGE_MEDIAN_BASELINE[s] for s in HEARTH_STAGES_ORDER)
    assert estimate_remaining_seconds([]) == round(total)


def test_estimate_remaining_seconds_after_one_stage() -> None:
    """completed=['received'] should return sum minus median for 'received'."""
    total = sum(STAGE_MEDIAN_BASELINE[s] for s in HEARTH_STAGES_ORDER)
    expected = round(total - STAGE_MEDIAN_BASELINE["received"])
    assert estimate_remaining_seconds(["received"]) == expected


def test_estimate_remaining_seconds_almost_done() -> None:
    """completed=[all but 'done', 'publishing'] → median['publishing'] + median['done']."""
    completed = [s for s in HEARTH_STAGES_ORDER if s not in ("done", "publishing")]
    expected = round(STAGE_MEDIAN_BASELINE["publishing"] + STAGE_MEDIAN_BASELINE["done"])
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
