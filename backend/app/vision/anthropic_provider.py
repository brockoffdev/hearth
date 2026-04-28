"""AnthropicProvider — VisionProvider backed by the Anthropic Claude API.

BYO-API-key alternative to the local Ollama default.  Uses the
``anthropic`` SDK (v0.40+) with full async support.

Default model: ``claude-haiku-4-5`` — fast and cost-effective for bulk
calendar reading.  Can be switched to ``claude-sonnet-4-6`` or
``claude-opus-4-7`` for hard-to-read entries per spec §6.2.

Configuration:
    Set ``HEARTH_VISION_PROVIDER=anthropic`` and
    ``HEARTH_ANTHROPIC_API_KEY=<key>`` to activate this provider.
    Optionally set ``HEARTH_VISION_MODEL`` to override the default model.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from anthropic import AsyncAnthropic

from backend.app.vision import CellPromptContext, ExtractedEvent
from backend.app.vision._prompt import build_cell_prompt

logger = logging.getLogger(__name__)


class AnthropicProvider:
    """VisionProvider implementation that calls the Anthropic Claude API.

    Attributes:
        api_key: The Anthropic API key used to authenticate requests.
        model:   The Claude model name, e.g. "claude-haiku-4-5".
        name:    Provenance string used in event records,
                 e.g. "anthropic:claude-haiku-4-5".
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "claude-haiku-4-5",
    ) -> None:
        """Create an AnthropicProvider.

        Args:
            api_key: Anthropic API key.  Obtain one at
                     https://console.anthropic.com/.
            model:   Claude model tag (default: "claude-haiku-4-5").
        """
        self.api_key = api_key
        self.model = model
        self.name = f"anthropic:{model}"
        self._client = AsyncAnthropic(api_key=api_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_fences(raw_text: str) -> str:
        """Remove Markdown code fences from a response string.

        Anthropic models sometimes wrap JSON in ```json ... ``` or ``` ... ```.
        This helper strips those fence lines so the remaining text parses cleanly.
        """
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            return "\n".join(line for line in lines if not line.startswith("```")).strip()
        return raw_text

    @staticmethod
    def _parse_response(raw_text: str) -> tuple[ExtractedEvent, ...]:
        """Parse the model's JSON string into a tuple of ExtractedEvent objects."""
        try:
            parsed: Any = json.loads(raw_text)
        except json.JSONDecodeError:
            logger.warning("AnthropicProvider: could not parse JSON response from model")
            return ()

        if not isinstance(parsed, list):
            logger.warning(
                "AnthropicProvider: expected JSON array, got %s", type(parsed).__name__
            )
            return ()

        events: list[ExtractedEvent] = []
        for item in parsed:
            if not isinstance(item, dict):
                logger.debug("AnthropicProvider: skipping non-dict item: %r", item)
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
                logger.debug("AnthropicProvider: skipping malformed item %r: %s", item, exc)
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
        """Send the cropped cell image to Claude and return parsed events.

        Sends a multimodal message with an image content block (base64 JPEG)
        followed by the prompt text.  The response is expected to be a JSON
        array; markdown code fences are stripped if present.

        Args:
            image_bytes: Raw bytes of the cropped calendar cell image.
            context:     Per-cell prompt context (date, family palette, corrections).

        Returns:
            Tuple of ExtractedEvent objects; empty tuple if the cell is blank
            or the model response cannot be parsed.
        """
        prompt = build_cell_prompt(context)
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        response = await self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # Extract text from content blocks; non-text blocks (e.g. tool_use) are skipped.
        text_blocks = [block.text for block in response.content if hasattr(block, "text")]
        raw_text = "".join(text_blocks).strip() or "[]"

        # Strip Markdown code fences if the model wrapped the JSON output.
        raw_text = self._strip_fences(raw_text)

        return self._parse_response(raw_text)

    async def health_check(self) -> bool:
        """Return True if the API key appears structurally valid.

        Trade-off: this is a format-only check (``sk-ant-`` prefix + minimum
        length) rather than a live API call.  It is intentionally cheap — a
        single probe message would cost a fraction of a cent and slow startup.
        Real authentication errors will surface loudly the first time
        ``extract_events_from_cell`` is called.

        Returns True if the key starts with ``sk-ant-`` and is longer than
        20 characters; False otherwise.
        """
        return self.api_key.startswith("sk-ant-") and len(self.api_key) > 20
