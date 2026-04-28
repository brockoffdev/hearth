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

from backend.app.vision import CellPromptContext, ExtractedEvent
from backend.app.vision._prompt import build_cell_prompt

logger = logging.getLogger(__name__)


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
        """Assemble the full prompt string for a cell.

        Delegates to the shared ``build_cell_prompt`` helper so the prompt text
        is identical across all VisionProvider implementations.
        """
        return build_cell_prompt(context)

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
