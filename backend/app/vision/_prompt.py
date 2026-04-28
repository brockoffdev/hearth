"""Shared prompt builder for VLM calendar cell extraction.

This module provides a single ``build_cell_prompt`` function used by all
VisionProvider implementations (Ollama, Gemini, Anthropic) so the prompt
text is consistent regardless of which backend is active.
"""

from __future__ import annotations

from backend.app.vision import CellPromptContext


def build_cell_prompt(context: CellPromptContext) -> str:
    """Build the prompt sent to any VLM for one cell of the calendar.

    Args:
        context: Per-cell context containing date label, family palette,
                 and optional few-shot corrections.

    Returns:
        A fully-formed prompt string instructing the model to output a JSON
        array of events extracted from the handwritten calendar cell image.
    """
    palette_lines = "\n".join(
        f"- {p.name} ({p.color_label}, hex {p.color_hex})"
        for p in context.family_palette
    )

    corrections_section = ""
    if context.few_shot_corrections:
        examples = "\n".join(
            f"- \"{c['before']}\" was actually \"{c['after']}\""
            for c in context.few_shot_corrections
        )
        corrections_section = (
            f"\n\nRecent corrections from the user (use these to improve your reading):\n"
            f"{examples}\n"
        )

    return (
        f"You are reading one cell of a wall calendar dated {context.cell_label}.\n"
        f"The cell may contain handwritten events. Each event was written by one\n"
        f"of these family members (each in a distinct ink color):\n"
        f"\n"
        f"{palette_lines}"
        f"{corrections_section}"
        f"\n"
        f"Output ONLY a JSON array of events found in this cell. Each event has:\n"
        f'- "title": the event description text\n'
        f'- "time_text": time of day (e.g. "8:30 AM") or null if all-day\n'
        f'- "color_hex": the dominant ink color in the writing (best-guess hex)\n'
        f'- "owner_guess": the family member name (one of the listed family) whose\n'
        f"  ink color most closely matches\n"
        f'- "confidence": 0.0-1.0, your confidence in this reading\n'
        f'- "raw_text": the literal text you read from the handwriting\n'
        f"\n"
        f"If the cell is empty, output []. Do not output explanations, just the JSON."
    )
