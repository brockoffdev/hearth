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
        f"IMPORTANT — when to return an empty array []:\n"
        f"- If the cell is empty, return [].\n"
        f"- If the cell contains only a printed day-of-week label (e.g. 'Sun', 'Mon',\n"
        f"  'Tue', 'Wed', 'Thu', 'Fri', 'Sat') or a column header, return [].\n"
        f"- If the cell contains only a single isolated character or punctuation with\n"
        f"  no event context (e.g. 'B', 'D', '.', '-', '·'), return [].\n"
        f"- If the cell appears to be from a notes section or legend strip (e.g.\n"
        f"  'TO DO', 'World Cup', 'Shaw', 'Bday' without a date context, or a\n"
        f"  colour-swatch label like 'Danielle'), return [].\n"
        f"- Do not invent events from fragments or ambiguous marks.\n"
        f"\n"
        f"Examples:\n"
        f"- Cell contains only 'Sat' or any day-name printed in the grid: return []\n"
        f'- Cell contains only "·" or a single arrow with no text: return []\n'
        f'- Cell contains "TO DO" header text from a notes section: return []\n'
        f'- Cell contains "-June" or a month-range fragment: return []\n'
        f'- Cell contains "BDay 7pm" handwritten in red ink: return\n'
        f'  [{{"title": "BDay", "time_text": "7:00 PM", "color_hex": "#C0392B",\n'
        f'    "owner_guess": "Bryant", "confidence": 0.85, "raw_text": "BDay 7pm"}}]\n'
        f"\n"
        f"Output ONLY a JSON array of events found in this cell. Each event has:\n"
        f'- "title": the event description text\n'
        f'- "time_text": time of day (e.g. "8:30 AM") or null if all-day\n'
        f'- "color_hex": the dominant ink color used by the writer (not the cell\n'
        f"  background) — report the ink/pen color as a best-guess hex value\n"
        f'- "owner_guess": the family member name (one of the listed family) whose\n'
        f"  ink color most closely matches\n"
        f'- "confidence": 0.0-1.0 chosen deliberately using this scale:\n'
        f"    < 0.5  if you're not sure this is even an event (could be a header,\n"
        f"           day name, legend label, or ambiguous fragment)\n"
        f"    0.5-0.75  for partially legible handwriting where the meaning is clear\n"
        f"              but some letters are uncertain\n"
        f"    0.75-0.95  for clear handwriting you can fully read\n"
        f"    Never use 0.85 as a default — choose deliberately based on legibility.\n"
        f'- "raw_text": the literal text you read from the handwriting\n'
        f"\n"
        f"If the cell is empty, output []. Do not output explanations, just the JSON."
    )
