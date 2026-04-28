"""Tests for data-driven STAGE_MEDIAN_SECONDS (Phase 4 Task H).

get_stage_medians() starts at baseline values; refresh_stage_medians_from_db()
reads pipeline_stage_durations and replaces medians when enough samples exist.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.app.auth.passwords import hash_password
from backend.app.db.base import get_session_factory
from backend.app.db.models import PipelineStageDuration, Upload, User
from backend.app.uploads.pipeline import (
    HEARTH_STAGES_ORDER,
    STAGE_MEDIAN_BASELINE,
    _stage_medians,
    estimate_remaining_seconds,
    get_stage_medians,
    refresh_stage_medians_from_db,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_user(db_engine: AsyncEngine) -> int:
    """Insert a minimal user row and return its id."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        user = User(
            username="testuser",
            password_hash=hash_password("password123"),
            role="user",
            must_change_password=False,
            must_complete_google_setup=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def _make_upload(db_engine: AsyncEngine, user_id: int) -> int:
    """Insert a minimal Upload row and return its id."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        upload = Upload(
            user_id=user_id,
            image_path="uploads/fake.jpg",
            status="completed",
            current_stage="done",
            completed_stages="[]",
        )
        session.add(upload)
        await session.commit()
        await session.refresh(upload)
        return upload.id


async def _insert_durations(
    db_engine: AsyncEngine,
    upload_id: int,
    stage: str,
    durations: list[float],
) -> None:
    """Insert multiple PipelineStageDuration rows for the given stage."""
    factory = get_session_factory(db_engine)
    async with factory() as session:
        for d in durations:
            session.add(
                PipelineStageDuration(
                    upload_id=upload_id,
                    stage=stage,
                    duration_seconds=d,
                )
            )
        await session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_stage_medians() -> None:
    """Reset _stage_medians to baseline before each test."""
    _stage_medians.clear()
    _stage_medians.update(STAGE_MEDIAN_BASELINE)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_stage_medians_returns_baseline_initially() -> None:
    """Before any DB call, get_stage_medians() returns the hard-coded baseline values."""
    medians = get_stage_medians()
    for stage, value in STAGE_MEDIAN_BASELINE.items():
        assert medians[stage] == value, (
            f"Stage '{stage}': expected baseline {value}, got {medians[stage]}"
        )


def test_baseline_covers_all_stages() -> None:
    """Every stage in HEARTH_STAGES_ORDER must have a baseline entry."""
    for stage in HEARTH_STAGES_ORDER:
        assert stage in STAGE_MEDIAN_BASELINE, (
            f"Stage '{stage}' missing from STAGE_MEDIAN_BASELINE"
        )


@pytest.mark.asyncio
async def test_refresh_stage_medians_uses_db_data_when_enough_samples(
    db_engine: AsyncEngine,
) -> None:
    """6 samples → median replaces baseline for that stage; others stay at baseline."""
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    await _insert_durations(
        db_engine, upload_id, "preprocessing", [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    )

    factory = get_session_factory(db_engine)
    await refresh_stage_medians_from_db(factory, min_samples_per_stage=5)

    medians = get_stage_medians()
    # Median of [1.0, 1.5, 2.0, 2.5, 3.0, 3.5] = (2.0 + 2.5) / 2 = 2.25
    assert medians["preprocessing"] == pytest.approx(2.25)
    # All other stages stay at baseline
    for stage in HEARTH_STAGES_ORDER:
        if stage != "preprocessing":
            assert medians[stage] == STAGE_MEDIAN_BASELINE[stage], (
                f"Stage '{stage}' should still be at baseline"
            )


@pytest.mark.asyncio
async def test_refresh_stage_medians_falls_back_to_baseline_below_threshold(
    db_engine: AsyncEngine,
) -> None:
    """Only 3 samples for 'preprocessing' → stays at baseline (threshold=5)."""
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    await _insert_durations(db_engine, upload_id, "preprocessing", [1.0, 2.0, 3.0])

    factory = get_session_factory(db_engine)
    await refresh_stage_medians_from_db(factory, min_samples_per_stage=5)

    medians = get_stage_medians()
    assert medians["preprocessing"] == STAGE_MEDIAN_BASELINE["preprocessing"]


@pytest.mark.asyncio
async def test_refresh_stage_medians_handles_empty_table(
    db_engine: AsyncEngine,
) -> None:
    """No rows in pipeline_stage_durations → all stages stay at baseline."""
    factory = get_session_factory(db_engine)
    await refresh_stage_medians_from_db(factory, min_samples_per_stage=5)

    medians = get_stage_medians()
    for stage, value in STAGE_MEDIAN_BASELINE.items():
        assert medians[stage] == value


@pytest.mark.asyncio
async def test_estimate_remaining_seconds_uses_current_medians(
    db_engine: AsyncEngine,
) -> None:
    """After refreshing medians, estimate_remaining_seconds reflects the new value."""
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    # Insert enough samples to change the preprocessing median
    await _insert_durations(
        db_engine, upload_id, "preprocessing", [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    )

    factory = get_session_factory(db_engine)

    # Before refresh — uses baseline 2.0
    before = estimate_remaining_seconds([])
    await refresh_stage_medians_from_db(factory, min_samples_per_stage=5)
    after = estimate_remaining_seconds([])

    # After refresh 'preprocessing' = 10.0 (was 2.0) → after > before
    assert after > before
    # Delta should equal the difference in medians
    delta = after - before
    assert delta == round(10.0 - STAGE_MEDIAN_BASELINE["preprocessing"])


@pytest.mark.asyncio
async def test_refresh_stage_medians_idempotent(
    db_engine: AsyncEngine,
) -> None:
    """Calling refresh twice with the same DB state yields the same result."""
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    await _insert_durations(
        db_engine, upload_id, "grid_detected", [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    )

    factory = get_session_factory(db_engine)
    await refresh_stage_medians_from_db(factory, min_samples_per_stage=5)
    first_result = dict(get_stage_medians())

    await refresh_stage_medians_from_db(factory, min_samples_per_stage=5)
    second_result = dict(get_stage_medians())

    assert first_result == second_result


@pytest.mark.asyncio
async def test_refresh_stage_medians_odd_sample_count(
    db_engine: AsyncEngine,
) -> None:
    """Odd number of samples → middle element is the median."""
    user_id = await _make_user(db_engine)
    upload_id = await _make_upload(db_engine, user_id)
    # 5 samples: sorted = [1.0, 2.0, 3.0, 4.0, 5.0] → median = 3.0
    await _insert_durations(
        db_engine, upload_id, "color_matching", [5.0, 1.0, 3.0, 2.0, 4.0]
    )

    factory = get_session_factory(db_engine)
    await refresh_stage_medians_from_db(factory, min_samples_per_stage=5)

    medians = get_stage_medians()
    assert medians["color_matching"] == pytest.approx(3.0)
