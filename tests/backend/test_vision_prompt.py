"""Tests for the shared build_cell_prompt helper.

Verifies:
- The cell label appears in the prompt.
- Each FamilyPaletteEntry is listed with name, label, and hex.
- The corrections section is omitted when few_shot_corrections is empty.
- The corrections section appears when corrections are provided, with each pair.
- The prompt always ends with JSON output instructions.
"""

from __future__ import annotations

from backend.app.vision import CellPromptContext, FamilyPaletteEntry
from backend.app.vision._prompt import build_cell_prompt

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PALETTE = (
    FamilyPaletteEntry(name="Bryant", color_label="Blue", color_hex="#2E5BA8"),
    FamilyPaletteEntry(name="Danya", color_label="Green", color_hex="#3A7D44"),
)

_DEFAULT_CONTEXT = CellPromptContext(
    cell_date_iso="2026-04-27",
    cell_label="Tuesday April 27",
    family_palette=_PALETTE,
)


# ---------------------------------------------------------------------------
# Cell label
# ---------------------------------------------------------------------------


def test_prompt_includes_cell_label() -> None:
    """The cell_label appears verbatim in the prompt."""
    prompt = build_cell_prompt(_DEFAULT_CONTEXT)
    assert "Tuesday April 27" in prompt


# ---------------------------------------------------------------------------
# Family palette entries
# ---------------------------------------------------------------------------


def test_prompt_lists_each_palette_entry() -> None:
    """Each FamilyPaletteEntry is listed with name, color_label, and color_hex."""
    prompt = build_cell_prompt(_DEFAULT_CONTEXT)
    assert "Bryant" in prompt
    assert "Blue" in prompt
    assert "#2E5BA8" in prompt
    assert "Danya" in prompt
    assert "Green" in prompt
    assert "#3A7D44" in prompt


def test_prompt_palette_line_format() -> None:
    """Each palette entry uses the '- Name (label, hex #XXXXXX)' format."""
    prompt = build_cell_prompt(_DEFAULT_CONTEXT)
    assert "- Bryant (Blue, hex #2E5BA8)" in prompt
    assert "- Danya (Green, hex #3A7D44)" in prompt


# ---------------------------------------------------------------------------
# Corrections section — absent when empty
# ---------------------------------------------------------------------------


def test_prompt_omits_corrections_when_none() -> None:
    """Corrections section is absent when few_shot_corrections is empty."""
    prompt = build_cell_prompt(_DEFAULT_CONTEXT)
    assert "Recent corrections from the user" not in prompt


def test_prompt_omits_corrections_header_for_empty_tuple() -> None:
    """Explicitly empty corrections tuple omits the header."""
    ctx = CellPromptContext(
        cell_date_iso="2026-04-27",
        cell_label="Tuesday April 27",
        family_palette=_PALETTE,
        few_shot_corrections=(),
    )
    prompt = build_cell_prompt(ctx)
    assert "Recent corrections from the user" not in prompt


# ---------------------------------------------------------------------------
# Corrections section — present when provided
# ---------------------------------------------------------------------------


def test_prompt_includes_corrections_section() -> None:
    """Corrections header appears when few_shot_corrections is non-empty."""
    ctx = CellPromptContext(
        cell_date_iso="2026-04-27",
        cell_label="Tuesday April 27",
        family_palette=_PALETTE,
        few_shot_corrections=(
            {"before": "Pikuagk Place", "after": "Pineapple Place"},
        ),
    )
    prompt = build_cell_prompt(ctx)
    assert "Recent corrections from the user" in prompt


def test_prompt_includes_each_correction_pair() -> None:
    """Each before/after pair is listed in the corrections section."""
    ctx = CellPromptContext(
        cell_date_iso="2026-04-27",
        cell_label="Tuesday April 27",
        family_palette=_PALETTE,
        few_shot_corrections=(
            {"before": "Pikuagk Place", "after": "Pineapple Place"},
            {"before": "Dentst", "after": "Dentist"},
        ),
    )
    prompt = build_cell_prompt(ctx)
    assert '"Pikuagk Place" was actually "Pineapple Place"' in prompt
    assert '"Dentst" was actually "Dentist"' in prompt


def test_prompt_multiple_corrections_all_appear() -> None:
    """Multiple corrections are all present in the prompt."""
    ctx = CellPromptContext(
        cell_date_iso="2026-04-27",
        cell_label="Tuesday April 27",
        family_palette=_PALETTE,
        few_shot_corrections=(
            {"before": "A", "after": "B"},
            {"before": "C", "after": "D"},
            {"before": "E", "after": "F"},
        ),
    )
    prompt = build_cell_prompt(ctx)
    assert '"A" was actually "B"' in prompt
    assert '"C" was actually "D"' in prompt
    assert '"E" was actually "F"' in prompt


# ---------------------------------------------------------------------------
# JSON output instructions always present
# ---------------------------------------------------------------------------


def test_prompt_ends_with_json_instructions() -> None:
    """Prompt contains the JSON output directive."""
    prompt = build_cell_prompt(_DEFAULT_CONTEXT)
    assert "Output ONLY a JSON array" in prompt


def test_prompt_contains_empty_cell_instruction() -> None:
    """Prompt instructs the model to output [] for empty cells."""
    prompt = build_cell_prompt(_DEFAULT_CONTEXT)
    assert "If the cell is empty, output []" in prompt


def test_prompt_contains_all_required_fields() -> None:
    """Prompt enumerates all required JSON fields: title, time_text, color_hex, etc."""
    prompt = build_cell_prompt(_DEFAULT_CONTEXT)
    for field in ("title", "time_text", "color_hex", "owner_guess", "confidence", "raw_text"):
        assert f'"{field}"' in prompt, f"Expected field '{field}' in prompt"
