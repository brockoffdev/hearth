"""OllamaProvider — VisionProvider backed by a local Ollama daemon.

Phase 4 default provider.  Talks to http://localhost:11434 by default
using the ``qwen2.5-vl:7b`` multimodal model.

The provider is tested via httpx.MockTransport (see tests/backend/test_vision_ollama.py).
The ``_transport`` constructor kwarg is a **test seam only** — do not pass it in
production code.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from backend.app.vision import CellPromptContext, ExtractedEvent, FamilyPaletteEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------

_PALETTE_LINE = "- {name} ({color_label}, hex {color_hex})"

_PROMPT_TEMPLATE = """\
You are reading one cell of a wall calendar dated {cell_label}.
The cell may contain handwritten events. Each event was written by one
of these family members (each in a distinct ink color):

{palette_lines}

Output ONLY a JSON array of events found in this cell. Each event has:
- "title": the event description text
- "time_text": time of day (e.g. "8:30 AM") or null if all-day
- "color_hex": the dominant ink color in the writing (best-guess hex)
- "owner_guess": the family member name (one of the listed family) whose
  ink color most closely matches
- "confidence": 0.0-1.0, your confidence in this reading
- "raw_text": the literal text you read from the handwriting

If the cell is empty, output []. Do not output explanations, just the JSON.\
"""

_CORRECTIONS_HEADER = (
    "\nRecent corrections from the user (use these to improve your reading):\n"
)


def _build_palette_lines(palette: tuple[FamilyPaletteEntry, ...]) -> str:
    return "\n".join(
        _PALETTE_LINE.format(
            name=entry.name,
            color_label=entry.color_label,
            color_hex=entry.color_hex,
        )
        for entry in palette
    )


def _build_corrections_section(corrections: tuple[dict[str, str], ...]) -> str:
    if not corrections:
        return ""
    lines = [_CORRECTIONS_HEADER]
    for correction in corrections:
        before = correction.get("before", "")
        after = correction.get("after", "")
        lines.append(f'- "{before}" was actually "{after}"')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# OllamaProvider
# ---------------------------------------------------------------------------


class OllamaProvider:
    """VisionProvider implementation that talks to a local Ollama daemon.

    Attributes:
        endpoint: Base URL of the Ollama daemon (no trailing slash).
        model:    Model tag to use for inference.
        name:     Provenance string used in event records, e.g. "ollama:qwen2.5-vl:7b".
    """

    def __init__(
        self,
        *,
        endpoint: str = "http://localhost:11434",
        model: str = "qwen2.5-vl:7b",
        _transport: httpx.MockTransport | None = None,
    ) -> None:
        """Create an OllamaProvider.

        Args:
            endpoint:   URL of the Ollama daemon.
            model:      Model tag for inference requests.
            _transport: **Test seam only.** Inject an httpx.MockTransport to
                        avoid real network calls in tests.  Do not pass in
                        production code.
        """
        self.endpoint = endpoint
        self.model = model
        self.name = f"ollama:{model}"
        self._transport = _transport

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_client(self, timeout: float) -> httpx.AsyncClient:
        """Return an AsyncClient, wired to the test transport if set."""
        if self._transport is not None:
            return httpx.AsyncClient(transport=self._transport, timeout=timeout)
        return httpx.AsyncClient(timeout=timeout)

    def _build_prompt(self, context: CellPromptContext) -> str:
        """Assemble the full prompt string for a cell."""
        palette_lines = _build_palette_lines(context.family_palette)
        base = _PROMPT_TEMPLATE.format(
            cell_label=context.cell_label,
            palette_lines=palette_lines,
        )
        corrections = _build_corrections_section(context.few_shot_corrections)
        if corrections:
            # Insert corrections block just before the "Output ONLY" instruction.
            output_marker = '\nOutput ONLY a JSON array'
            insert_at = base.find(output_marker)
            if insert_at != -1:
                base = base[:insert_at] + corrections + base[insert_at:]
            else:
                base = base + corrections
        return base

    @staticmethod
    def _parse_response(raw_response: str) -> tuple[ExtractedEvent, ...]:
        """Parse the model's JSON string into a tuple of ExtractedEvent objects."""
        try:
            parsed: Any = json.loads(raw_response)
        except json.JSONDecodeError:
            # Ollama with format='json' should always return valid JSON, but be
            # defensive; return empty rather than surfacing a parse error.
            logger.warning("OllamaProvider: could not parse JSON response from model")
            return ()

        if not isinstance(parsed, list):
            logger.warning(
                "OllamaProvider: expected JSON array, got %s", type(parsed).__name__
            )
            return ()

        events: list[ExtractedEvent] = []
        for item in parsed:
            if not isinstance(item, dict):
                logger.debug("OllamaProvider: skipping non-dict item in response: %r", item)
                continue
            try:
                events.append(
                    ExtractedEvent(
                        title=str(item.get("title", "")).strip(),
                        time_text=item.get("time_text") or None,
                        color_hex=item.get("color_hex") or None,
                        owner_guess=item.get("owner_guess") or None,
                        confidence=float(item.get("confidence", 0.5)),
                        raw_text=str(item.get("raw_text", "")).strip(),
                    )
                )
            except (ValueError, TypeError) as exc:
                logger.debug("OllamaProvider: skipping malformed item %r: %s", item, exc)
                continue

        return tuple(events)

    # ------------------------------------------------------------------
    # VisionProvider interface
    # ------------------------------------------------------------------

    async def extract_events_from_cell(
        self,
        image_bytes: bytes,
        context: CellPromptContext,
    ) -> tuple[ExtractedEvent, ...]:
        """Send the cropped cell image to Ollama and return parsed events.

        Args:
            image_bytes: Raw bytes of the cropped calendar cell image.
            context:     Per-cell prompt context (date, family palette, corrections).

        Returns:
            Tuple of ExtractedEvent objects; empty tuple if the cell is blank
            or the model response cannot be parsed.

        Raises:
            httpx.HTTPStatusError: If the Ollama daemon returns a non-2xx response.
        """
        image_b64 = base64.b64encode(image_bytes).decode()
        prompt = self._build_prompt(context)

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
            },
        }

        async with self._make_client(timeout=60.0) as client:
            response = await client.post(
                f"{self.endpoint}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            body: dict[str, Any] = response.json()

        raw_response: str = body.get("response", "[]")
        return self._parse_response(raw_response)

    async def health_check(self) -> bool:
        """Return True if the Ollama daemon is reachable and responds with 200.

        Never raises — any error (connection refused, timeout, HTTP error) maps
        to False.
        """
        try:
            async with self._make_client(timeout=2.0) as client:
                response = await client.get(f"{self.endpoint}/api/version")
                return response.status_code == 200
        except (httpx.HTTPError, OSError):
            return False
