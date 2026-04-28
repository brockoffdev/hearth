"""GeminiProvider — VisionProvider backed by the Google Gemini API.

BYO-API-key alternative to the local Ollama default.  Uses the
``google-generativeai`` SDK (v0.8+) with async generation.

Default model: ``gemini-2.5-flash`` (~$0.001/image, 87-94% accuracy on
handwritten calendars per spec §6.2).

Configuration:
    Set ``HEARTH_VISION_PROVIDER=gemini`` and ``HEARTH_GEMINI_API_KEY=<key>``
    to activate this provider.  Optionally set ``HEARTH_VISION_MODEL`` to
    override the default model.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from google import generativeai as genai  # type: ignore[import-untyped]

from backend.app.vision import CellPromptContext, ExtractedEvent
from backend.app.vision._prompt import build_cell_prompt

logger = logging.getLogger(__name__)


class GeminiProvider:
    """VisionProvider implementation that calls the Google Gemini API.

    Attributes:
        api_key: The Gemini API key used to authenticate requests.
        model:   The model name, e.g. "gemini-2.5-flash".
        name:    Provenance string used in event records, e.g. "gemini:gemini-2.5-flash".
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gemini-2.5-flash",
    ) -> None:
        """Create a GeminiProvider.

        Args:
            api_key: Gemini API key.  Obtain one at https://aistudio.google.com/.
            model:   Gemini model tag (default: "gemini-2.5-flash").
        """
        self.api_key = api_key
        self.model = model
        self.name = f"gemini:{model}"
        # Configure the Gemini client — idempotent, safe to call at construction.
        genai.configure(api_key=api_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(raw_text: str) -> tuple[ExtractedEvent, ...]:
        """Parse the model's JSON string into a tuple of ExtractedEvent objects."""
        try:
            parsed: Any = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("GeminiProvider: could not parse JSON response from model")
            return ()

        if not isinstance(parsed, list):
            logger.warning(
                "GeminiProvider: expected JSON array, got %s", type(parsed).__name__
            )
            return ()

        events: list[ExtractedEvent] = []
        for item in parsed:
            if not isinstance(item, dict):
                logger.debug("GeminiProvider: skipping non-dict item: %r", item)
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
                logger.debug("GeminiProvider: skipping malformed item %r: %s", item, exc)
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
        """Send the cropped cell image to Gemini and return parsed events.

        Args:
            image_bytes: Raw bytes of the cropped calendar cell image.
            context:     Per-cell prompt context (date, family palette, corrections).

        Returns:
            Tuple of ExtractedEvent objects; empty tuple if the cell is blank
            or the model response cannot be parsed.
        """
        prompt = build_cell_prompt(context)
        image_part = {"mime_type": "image/jpeg", "data": image_bytes}

        model_client = genai.GenerativeModel(self.model)
        response = await model_client.generate_content_async(
            [prompt, image_part],
            generation_config={
                "temperature": 0.1,
                # Gemini supports JSON-constrained output via response_mime_type.
                "response_mime_type": "application/json",
            },
        )

        raw_text: str = response.text or "[]"
        return self._parse_response(raw_text)

    async def health_check(self) -> bool:
        """Return True if the Gemini API is reachable and the configured model is listed.

        Uses ``asyncio.to_thread`` because ``genai.list_models`` is synchronous.
        Never raises — any error (network, auth, etc.) maps to False.
        """
        try:
            models = await asyncio.to_thread(genai.list_models)
            return any(m.name.endswith(self.model) for m in models)
        except Exception:
            return False
