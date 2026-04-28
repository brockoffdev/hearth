"""Tests for the VisionProvider Protocol and shared dataclasses.

Verifies:
- The Protocol is runtime_checkable.
- A compliant stub passes isinstance().
- A stub missing extract_events_from_cell fails isinstance().
- A stub missing health_check fails isinstance().
- Dataclass fields and frozen constraints work as expected.
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.app.vision import (
    CellPromptContext,
    ExtractedEvent,
    FamilyPaletteEntry,
    VisionProvider,
)

# ---------------------------------------------------------------------------
# Minimal compliant stub
# ---------------------------------------------------------------------------


class _CompliantProvider:
    """Minimal stub that satisfies the VisionProvider Protocol."""

    name: str = "stub:model"

    async def extract_events_from_cell(
        self,
        image_bytes: bytes,
        context: CellPromptContext,
    ) -> tuple[ExtractedEvent, ...]:
        return ()

    async def health_check(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Stubs missing required members
# ---------------------------------------------------------------------------


class _MissingExtractMethod:
    """Stub without extract_events_from_cell."""

    name: str = "stub:model"

    async def health_check(self) -> bool:
        return True


class _MissingHealthCheck:
    """Stub without health_check."""

    name: str = "stub:model"

    async def extract_events_from_cell(
        self,
        image_bytes: bytes,
        context: CellPromptContext,
    ) -> tuple[ExtractedEvent, ...]:
        return ()


class _MissingName:
    """Stub without the ``name`` attribute."""

    async def extract_events_from_cell(
        self,
        image_bytes: bytes,
        context: CellPromptContext,
    ) -> tuple[ExtractedEvent, ...]:
        return ()

    async def health_check(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Protocol tests
# ---------------------------------------------------------------------------


def test_protocol_runtime_checkable_accepts_compliant_class() -> None:
    """A class implementing all Protocol members passes isinstance()."""
    provider = _CompliantProvider()
    assert isinstance(provider, VisionProvider)


def test_protocol_rejects_missing_extract_method() -> None:
    """A class missing extract_events_from_cell fails isinstance()."""
    stub = _MissingExtractMethod()
    assert not isinstance(stub, VisionProvider)


def test_protocol_rejects_missing_health_check() -> None:
    """A class missing health_check fails isinstance()."""
    stub = _MissingHealthCheck()
    assert not isinstance(stub, VisionProvider)


def test_protocol_rejects_missing_name() -> None:
    """A class missing the name attribute fails isinstance()."""
    stub = _MissingName()
    assert not isinstance(stub, VisionProvider)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------


def test_family_palette_entry_is_frozen() -> None:
    """FamilyPaletteEntry is immutable."""
    entry = FamilyPaletteEntry(name="Bryant", color_label="Blue", color_hex="#2E5BA8")
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.name = "Danya"  # type: ignore[misc]


def test_extracted_event_defaults_none_for_optional_fields() -> None:
    """ExtractedEvent fields with None are acceptable."""
    event = ExtractedEvent(
        title="Doctor",
        time_text=None,
        color_hex=None,
        owner_guess=None,
        confidence=0.9,
        raw_text="Doctor",
    )
    assert event.time_text is None
    assert event.color_hex is None
    assert event.owner_guess is None


def test_cell_prompt_context_defaults_empty_corrections() -> None:
    """CellPromptContext.few_shot_corrections defaults to empty tuple."""
    ctx = CellPromptContext(
        cell_date_iso="2026-04-27",
        cell_label="Tuesday April 27",
        family_palette=(),
    )
    assert ctx.few_shot_corrections == ()


def test_cell_prompt_context_accepts_corrections() -> None:
    """CellPromptContext stores provided few-shot corrections."""
    corr = ({"before": "Pikuagk Place", "after": "Pineapple Place"},)
    ctx = CellPromptContext(
        cell_date_iso="2026-04-27",
        cell_label="Tuesday April 27",
        family_palette=(),
        few_shot_corrections=corr,
    )
    assert ctx.few_shot_corrections == corr


def test_cell_prompt_context_is_frozen() -> None:
    """CellPromptContext is immutable."""
    ctx = CellPromptContext(
        cell_date_iso="2026-04-27",
        cell_label="Tuesday April 27",
        family_palette=(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.cell_date_iso = "2026-04-28"  # type: ignore[misc]
