"""Tests for the real run_pipeline orchestration (Phase 4 Task G).

Tests use mocked VisionProvider, preprocess_photo, detect_grid,
match_ink_color_async, store_photo, read_photo, and crop_cell.
The orchestration logic is what we verify here — the underlying ops
were each tested in their own module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.config import Settings
from backend.app.db.models import FamilyMember
from backend.app.uploads.grid_detect import CellBox, GridDetectionResult
from backend.app.uploads.pipeline import (
    HEARTH_STAGES_ORDER,
    ExtractedEventRecord,
    StageEvent,
    _compute_cell_date_iso,
    _format_cell_label,
    run_pipeline,
)
from backend.app.vision import CellPromptContext, ExtractedEvent

# Short aliases for patch targets to keep line lengths under 100.
_PL = "backend.app.uploads.pipeline"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "session_secret": "test-secret-do-not-use",
        "vision_provider": "ollama",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_cell(row: int, col: int) -> CellBox:
    return CellBox(row=row, col=col, x=col * 100, y=row * 100, width=100, height=100)


def _make_grid(rows: int = 5, cols: int = 7) -> GridDetectionResult:
    cells = tuple(
        _make_cell(r, c) for r in range(rows) for c in range(cols)
    )
    return GridDetectionResult(cells=cells, notes=None, detection_method="fallback")


def _make_empty_grid() -> GridDetectionResult:
    return GridDetectionResult(cells=(), notes=None, detection_method="failed")


def _make_extracted_event(title: str = "Team Meeting", confidence: float = 0.9) -> ExtractedEvent:
    return ExtractedEvent(
        title=title,
        time_text="9:00 AM",
        color_hex="#2E5BA8",
        owner_guess="Bryant",
        confidence=confidence,
        raw_text=title,
    )


@dataclass
class _FakeFamilyMember:
    id: int
    name: str
    color_hex_center: str
    hue_range_low: int
    hue_range_high: int


def _make_family_members() -> list[FamilyMember]:
    """Return fake FamilyMember-like objects cast to list[FamilyMember] for type checking.

    Tests only need duck-typing: these objects expose the same attributes the
    pipeline reads (name, color_hex_center, hue_range_low, hue_range_high, id).
    """
    return cast(
        list[FamilyMember],
        [
            _FakeFamilyMember(
                id=1, name="Bryant", color_hex_center="#2E5BA8",
                hue_range_low=200, hue_range_high=240,
            ),
            _FakeFamilyMember(
                id=2, name="Danya", color_hex_center="#C0392B",
                hue_range_low=350, hue_range_high=20,
            ),
        ],
    )


@dataclass(frozen=True)
class _FakeColorMatch:
    family_member_id: int
    family_member_name: str
    color_hex: str
    confidence: float
    detected_hue_deg: float


# Fake cell bytes returned by the mocked crop_cell
FAKE_CELL_BYTES = b"fake-cell-bytes"


# ---------------------------------------------------------------------------
# Core pipeline stage ordering tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_emits_all_stages_in_order() -> None:
    """run_pipeline yields StageEvents covering all HEARTH_STAGES_ORDER stages."""
    family_members = _make_family_members()
    grid = _make_grid()

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"raw")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(f"{_PL}.match_ink_color_async", new=AsyncMock(return_value=None)),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("abc", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = AsyncMock()
        mock_provider.extract_events_from_cell = AsyncMock(return_value=())
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        events: list[StageEvent] = []
        async for ev in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
            stage_delay_seconds=0.0,
            cell_delay_seconds=0.0,
        ):
            events.append(ev)

    # Check that all stages appear (there may be many cell_progress events)
    seen_stages = [e.stage for e in events]
    for stage in HEARTH_STAGES_ORDER:
        assert stage in seen_stages, f"Stage '{stage}' missing from emitted events"

    # Verify final event is 'done'
    assert events[-1].stage == "done"


@pytest.mark.asyncio
async def test_run_pipeline_skips_to_done_when_grid_detection_returns_empty_cells() -> None:
    """When grid detection returns empty cells, pipeline skips to done without VLM calls."""
    family_members = _make_family_members()

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"fake")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"preprocessed")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=_make_empty_grid())),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(f"{_PL}.match_ink_color_async") as mock_color,
        patch(f"{_PL}.store_photo") as mock_store,
        patch(f"{_PL}.crop_cell") as mock_crop,
    ):
        mock_provider = AsyncMock()
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        events: list[StageEvent] = []
        async for ev in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
        ):
            events.append(ev)

    seen_stages = [e.stage for e in events]
    # All stages must still appear
    for stage in HEARTH_STAGES_ORDER:
        assert stage in seen_stages, f"Stage '{stage}' missing when grid empty"

    assert events[-1].stage == "done"
    # VLM and color-match should not be called
    mock_provider.extract_events_from_cell.assert_not_called()
    mock_color.assert_not_called()
    mock_store.assert_not_called()
    mock_crop.assert_not_called()


@pytest.mark.asyncio
async def test_run_pipeline_calls_on_event_extracted_for_each_vlm_event() -> None:
    """on_event_extracted is called once per extracted VLM event across all cells."""
    family_members = _make_family_members()
    grid = _make_grid(rows=1, cols=2)  # 2 cells
    vlm_event_a = _make_extracted_event("Soccer practice")
    vlm_event_b = _make_extracted_event("Doctor appt", confidence=0.8)

    call_count = 0

    async def mock_extract(
        image_bytes: bytes, context: CellPromptContext
    ) -> tuple[ExtractedEvent, ...]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return (vlm_event_a,)
        return (vlm_event_b, vlm_event_a)

    extracted_records: list[ExtractedEventRecord] = []

    async def on_extracted(record: ExtractedEventRecord) -> None:
        extracted_records.append(record)

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(f"{_PL}.match_ink_color_async", new=AsyncMock(return_value=None)),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = mock_extract
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        async for _ in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
            on_event_extracted=on_extracted,
        ):
            pass

    # 1 event from cell 0 + 2 events from cell 1 = 3 total
    assert len(extracted_records) == 3
    titles = [r.title for r in extracted_records]
    assert "Soccer practice" in titles
    assert "Doctor appt" in titles


@pytest.mark.asyncio
async def test_run_pipeline_assigns_color_match_family_member_id_to_records() -> None:
    """family_member_id on ExtractedEventRecord comes from the ColorMatch result."""
    family_members = _make_family_members()
    grid = _make_grid(rows=1, cols=1)  # 1 cell
    vlm_event = _make_extracted_event()

    color_match = _FakeColorMatch(
        family_member_id=1,
        family_member_name="Bryant",
        color_hex="#2E5BA8",
        confidence=0.92,
        detected_hue_deg=220.0,
    )

    extracted_records: list[ExtractedEventRecord] = []

    async def on_extracted(record: ExtractedEventRecord) -> None:
        extracted_records.append(record)

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(
            f"{_PL}.match_ink_color_async",
            new=AsyncMock(return_value=color_match),
        ),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = AsyncMock(return_value=(vlm_event,))
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        async for _ in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
            on_event_extracted=on_extracted,
        ):
            pass

    assert len(extracted_records) == 1
    assert extracted_records[0].family_member_id == 1
    assert extracted_records[0].color_match_confidence == 0.92


@pytest.mark.asyncio
async def test_run_pipeline_composite_confidence_is_product_of_factors() -> None:
    """composite_confidence = vision_confidence * max(color_match_confidence, 0.3) * 1.0."""
    family_members = _make_family_members()
    grid = _make_grid(rows=1, cols=1)
    vlm_event = _make_extracted_event(confidence=0.8)

    color_match = _FakeColorMatch(
        family_member_id=1,
        family_member_name="Bryant",
        color_hex="#2E5BA8",
        confidence=0.75,
        detected_hue_deg=220.0,
    )

    extracted_records: list[ExtractedEventRecord] = []

    async def on_extracted(record: ExtractedEventRecord) -> None:
        extracted_records.append(record)

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(
            f"{_PL}.match_ink_color_async",
            new=AsyncMock(return_value=color_match),
        ),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = AsyncMock(return_value=(vlm_event,))
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        async for _ in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
            on_event_extracted=on_extracted,
        ):
            pass

    assert len(extracted_records) == 1
    record = extracted_records[0]
    expected_composite = 0.8 * max(0.75, 0.3) * 1.0
    assert abs(record.composite_confidence - expected_composite) < 1e-9
    assert abs(record.vision_confidence - 0.8) < 1e-9
    assert abs(record.color_match_confidence - 0.75) < 1e-9


@pytest.mark.asyncio
async def test_run_pipeline_handles_vlm_failure_per_cell() -> None:
    """VLM exception on one cell is caught; pipeline continues with remaining cells."""
    family_members = _make_family_members()
    grid = _make_grid(rows=1, cols=3)  # 3 cells: 0, 1, 2

    call_count = 0

    async def mock_extract(
        image_bytes: bytes, context: CellPromptContext
    ) -> tuple[ExtractedEvent, ...]:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("VLM exploded on cell 2")
        return (_make_extracted_event(),)

    extracted_records: list[ExtractedEventRecord] = []

    async def on_extracted(record: ExtractedEventRecord) -> None:
        extracted_records.append(record)

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(f"{_PL}.match_ink_color_async", new=AsyncMock(return_value=None)),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = mock_extract
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        events: list[StageEvent] = []
        async for ev in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
            on_event_extracted=on_extracted,
        ):
            events.append(ev)

    # Pipeline should complete (reach 'done')
    assert events[-1].stage == "done"
    # Cells 0 and 2 returned events; cell 1 (call_count==2) raised — 2 records
    assert len(extracted_records) == 2


@pytest.mark.asyncio
async def test_run_pipeline_handles_color_match_returning_none() -> None:
    """When color match returns None, family_member_id=None and color_match_confidence=0.0."""
    family_members = _make_family_members()
    grid = _make_grid(rows=1, cols=1)
    vlm_event = _make_extracted_event()

    extracted_records: list[ExtractedEventRecord] = []

    async def on_extracted(record: ExtractedEventRecord) -> None:
        extracted_records.append(record)

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(
            f"{_PL}.match_ink_color_async",
            new=AsyncMock(return_value=None),
        ),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = AsyncMock(return_value=(vlm_event,))
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        async for _ in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
            on_event_extracted=on_extracted,
        ):
            pass

    assert len(extracted_records) == 1
    record = extracted_records[0]
    assert record.family_member_id is None
    assert record.color_match_confidence == 0.0
    # Composite: vision * max(0.0, 0.3) * 1.0 = 0.9 * 0.3
    expected = 0.9 * 0.3 * 1.0
    assert abs(record.composite_confidence - expected) < 1e-9


@pytest.mark.asyncio
async def test_run_pipeline_uses_provider_from_settings() -> None:
    """get_vision_provider is called with the settings object passed to run_pipeline."""
    family_members = _make_family_members()
    # Use a real (non-empty) grid so the pipeline reaches model_loading.
    grid = _make_grid(rows=1, cols=1)

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(f"{_PL}.match_ink_color_async", new=AsyncMock(return_value=None)),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = AsyncMock(return_value=())
        mock_factory.return_value = mock_provider

        settings = _make_settings(vision_provider="ollama")
        async for _ in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
        ):
            pass

    mock_factory.assert_called_once_with(settings)


@pytest.mark.asyncio
async def test_run_pipeline_records_raw_vlm_json() -> None:
    """raw_vlm_json field is valid JSON containing the VLM event data."""
    family_members = _make_family_members()
    grid = _make_grid(rows=1, cols=1)
    vlm_event = _make_extracted_event(title="Piano recital", confidence=0.95)

    extracted_records: list[ExtractedEventRecord] = []

    async def on_extracted(record: ExtractedEventRecord) -> None:
        extracted_records.append(record)

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(f"{_PL}.match_ink_color_async", new=AsyncMock(return_value=None)),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = AsyncMock(return_value=(vlm_event,))
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        async for _ in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
            on_event_extracted=on_extracted,
        ):
            pass

    assert len(extracted_records) == 1
    raw_json = extracted_records[0].raw_vlm_json
    parsed = json.loads(raw_json)
    assert parsed["title"] == "Piano recital"
    assert abs(parsed["confidence"] - 0.95) < 1e-9


@pytest.mark.asyncio
async def test_run_pipeline_cell_progress_events_have_progress_field() -> None:
    """cell_progress StageEvents carry progress={"cell": n, "total": N}."""
    family_members = _make_family_members()
    grid = _make_grid(rows=1, cols=3)  # 3 cells

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(f"{_PL}.match_ink_color_async", new=AsyncMock(return_value=None)),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = AsyncMock(return_value=())
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        cell_events: list[StageEvent] = []
        async for ev in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
        ):
            if ev.stage == "cell_progress":
                cell_events.append(ev)

    assert len(cell_events) == 3
    for i, ev in enumerate(cell_events, start=1):
        assert ev.progress == {"cell": i, "total": 3}, f"cell {i} has wrong progress: {ev.progress}"


@pytest.mark.asyncio
async def test_run_pipeline_grid_detected_carries_total_cells() -> None:
    """grid_detected StageEvent carries progress={"cell": 0, "total": N} immediately.

    This lets the UI render "of N" before the slow model_loading stage begins.
    """
    family_members = _make_family_members()
    grid = _make_grid(rows=2, cols=7)  # 14 cells

    with (
        patch(f"{_PL}.read_photo", new=AsyncMock(return_value=b"img")),
        patch(f"{_PL}.preprocess_photo", new=AsyncMock(return_value=b"pre")),
        patch(f"{_PL}.detect_grid", new=AsyncMock(return_value=grid)),
        patch(f"{_PL}.get_vision_provider") as mock_factory,
        patch(f"{_PL}.match_ink_color_async", new=AsyncMock(return_value=None)),
        patch(f"{_PL}.store_photo", new=AsyncMock(return_value=("x", "p"))),
        patch(f"{_PL}.crop_cell", return_value=FAKE_CELL_BYTES),
    ):
        mock_provider = MagicMock()
        mock_provider.extract_events_from_cell = AsyncMock(return_value=())
        mock_factory.return_value = mock_provider

        settings = _make_settings()
        events: list[StageEvent] = []
        async for ev in run_pipeline(
            upload_id=1,
            image_path="uploads/fake.jpg",
            settings=settings,
            family_members=family_members,
        ):
            events.append(ev)

    grid_event = next(e for e in events if e.stage == "grid_detected")
    assert grid_event.progress is not None, "grid_detected event must carry progress"
    assert grid_event.progress["cell"] == 0, "progress.cell must be 0 at grid_detected"
    total = grid_event.progress["total"]
    assert total == 14, f"expected total=14, got {total}"

    # Verify model_loading comes after grid_detected in the event stream
    grid_idx = next(i for i, e in enumerate(events) if e.stage == "grid_detected")
    model_idx = next(i for i, e in enumerate(events) if e.stage == "model_loading")
    assert grid_idx < model_idx, "grid_detected must precede model_loading"


# ---------------------------------------------------------------------------
# _compute_cell_date_iso tests
# ---------------------------------------------------------------------------


def test_compute_cell_date_iso_april_2026() -> None:
    """April 2026 starts on Wednesday.  Cell (0,0) should be the Sunday before April 1.

    April 1, 2026 is Wednesday (weekday=2).
    Days since Sunday = (2 + 1) % 7 = 3.
    Grid start = April 1 - 3 days = March 29, 2026.
    Cell (0,0) = March 29.
    """
    photographed_month = date(2026, 4, 1)
    cell = _make_cell(0, 0)
    result = _compute_cell_date_iso(cell, photographed_month=photographed_month)
    assert result == "2026-03-29", f"Expected 2026-03-29, got {result}"


def test_compute_cell_date_iso_april_2026_first_cell_of_april() -> None:
    """Cell (0,3) in April 2026 should be April 1, 2026 (Wednesday = col 3)."""
    photographed_month = date(2026, 4, 1)
    cell = _make_cell(0, 3)
    result = _compute_cell_date_iso(cell, photographed_month=photographed_month)
    assert result == "2026-04-01", f"Expected 2026-04-01, got {result}"


def test_compute_cell_date_iso_handles_month_starting_on_sunday() -> None:
    """When month starts on Sunday, cell (0,0) should be that Sunday itself.

    January 2023 starts on Sunday (weekday=6).
    days_to_sunday = (6 + 1) % 7 = 0.
    Grid start = January 1.  Cell (0,0) = January 1.
    """
    photographed_month = date(2023, 1, 1)
    cell = _make_cell(0, 0)
    result = _compute_cell_date_iso(cell, photographed_month=photographed_month)
    assert result == "2023-01-01", f"Expected 2023-01-01, got {result}"


def test_compute_cell_date_iso_row_offset() -> None:
    """Cell (2,0) for April 2026 should be 14 days after the grid start (March 29)."""
    photographed_month = date(2026, 4, 1)
    cell = _make_cell(2, 0)  # row=2, col=0
    result = _compute_cell_date_iso(cell, photographed_month=photographed_month)
    # March 29 + 2*7 days = April 12
    assert result == "2026-04-12", f"Expected 2026-04-12, got {result}"


def test_compute_cell_date_iso_honors_non_default_photographed_month() -> None:
    """photographed_month=date(2026, 4, 27) is used; cell (0,3) = April 1 for April 2026.

    April 2026 starts on Wednesday (col 3).  Passing a mid-month date (April 27)
    still produces the same grid as passing any other April date because only the
    year and month are used.

    April 1, 2026 = Wednesday → days_to_sunday = (2+1)%7 = 3.
    Grid start = April 1 - 3 = March 29.
    Cell (0,3) = March 29 + 3 = April 1, 2026.
    """
    photographed_month = date(2026, 4, 27)
    cell = _make_cell(0, 3)
    result = _compute_cell_date_iso(cell, photographed_month=photographed_month)
    assert result == "2026-04-01", f"Expected 2026-04-01 for April 2026 cell (0,3), got {result}"


# ---------------------------------------------------------------------------
# _format_cell_label tests
# ---------------------------------------------------------------------------


def test_format_cell_label() -> None:
    """'2026-04-27' → 'Monday April 27'."""
    result = _format_cell_label("2026-04-27")
    assert result == "Monday April 27"


def test_format_cell_label_march() -> None:
    """'2026-03-29' → 'Sunday March 29'."""
    result = _format_cell_label("2026-03-29")
    assert result == "Sunday March 29"


# ---------------------------------------------------------------------------
# ExtractedEventRecord dataclass tests
# ---------------------------------------------------------------------------


def test_extracted_event_record_is_frozen() -> None:
    """ExtractedEventRecord should be a frozen dataclass (immutable)."""
    record = ExtractedEventRecord(
        cell_row=0,
        cell_col=0,
        cell_date_iso="2026-04-27",
        title="Test",
        time_text="10:00 AM",
        color_hex="#2E5BA8",
        family_member_id=1,
        color_match_confidence=0.9,
        vision_confidence=0.85,
        composite_confidence=0.765,
        raw_vlm_json='{"title":"Test"}',
        cell_crop_path="uploads/ab/c/original.jpg",
    )
    with pytest.raises((AttributeError, TypeError)):
        record.title = "Other"  # type: ignore[misc]


def test_extracted_event_record_accepts_none_fields() -> None:
    """Optional fields (time_text, color_hex, family_member_id, cell_crop_path) can be None."""
    record = ExtractedEventRecord(
        cell_row=0,
        cell_col=0,
        cell_date_iso="2026-04-27",
        title="All-day event",
        time_text=None,
        color_hex=None,
        family_member_id=None,
        color_match_confidence=0.0,
        vision_confidence=0.7,
        composite_confidence=0.21,
        raw_vlm_json="{}",
        cell_crop_path=None,
    )
    assert record.time_text is None
    assert record.family_member_id is None
    assert record.cell_crop_path is None
