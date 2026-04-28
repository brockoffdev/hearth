"""Vision provider abstractions for the Hearth VLM pipeline.

This module defines:
- FamilyPaletteEntry  — one color → owner mapping for VLM context
- ExtractedEvent      — one event extracted from a single calendar cell
- CellPromptContext   — per-cell context that grounds the VLM prompt
- VisionProvider      — runtime-checkable Protocol every provider implements
- get_vision_provider — factory that builds the configured provider
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.config import Settings


# ---------------------------------------------------------------------------
# Shared dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FamilyPaletteEntry:
    """One color → owner mapping for VLM context."""

    name: str
    """Human-readable name, e.g. "Bryant"."""

    color_label: str
    """Descriptive label, e.g. "Blue"."""

    color_hex: str
    """Hex color string, e.g. "#2E5BA8"."""


@dataclass(frozen=True)
class ExtractedEvent:
    """One event extracted from a single calendar cell."""

    title: str
    """The event description text."""

    time_text: str | None
    """Time of day (e.g. "8:30 AM") or None for all-day events."""

    color_hex: str | None
    """Dominant ink color detected in the writing (best-guess hex); provider best-effort."""

    owner_guess: str | None
    """Provider's best-guess owner name from the family palette."""

    confidence: float
    """Self-reported confidence score in the range 0.0-1.0."""

    raw_text: str
    """The literal text the model read from the handwriting."""


@dataclass(frozen=True)
class CellPromptContext:
    """Per-cell context the provider uses to ground the VLM prompt."""

    cell_date_iso: str
    """ISO 8601 date string derived from grid coords, e.g. "2026-04-27"."""

    cell_label: str
    """Human-friendly label, e.g. "Tuesday April 27"."""

    family_palette: tuple[FamilyPaletteEntry, ...]
    """Ordered tuple of all family member color entries."""

    few_shot_corrections: tuple[dict[str, str], ...] = field(
        default_factory=lambda: ()
    )
    """Recent user corrections passed as few-shot examples (Phase 4+)."""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class VisionProvider(Protocol):
    """The vision provider interface every backend implementation honors.

    Implementations must expose:
    - ``name``                  — provenance string, e.g. "ollama:qwen2.5-vl:7b"
    - ``extract_events_from_cell`` — read handwriting from one cropped cell image
    - ``health_check``          — lightweight liveness probe used at startup
    """

    name: str
    """Provenance identifier, e.g. "ollama:qwen2.5-vl:7b"."""

    async def extract_events_from_cell(
        self,
        image_bytes: bytes,
        context: CellPromptContext,
    ) -> tuple[ExtractedEvent, ...]:
        """Return events found in the cropped cell image.

        Args:
            image_bytes: Raw bytes of the cropped calendar cell image.
            context:     Date, label, palette, and any few-shot corrections.

        Returns:
            Tuple of ExtractedEvent instances (empty if the cell is blank).
        """
        ...

    async def health_check(self) -> bool:
        """Return True if the provider is reachable and ready.

        Never raises — any connection error maps to False.
        Used for startup probes and readiness checks.
        """
        ...


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_vision_provider(settings: Settings) -> VisionProvider:
    """Build the configured VisionProvider from application settings.

    Supports three providers: "ollama" (local default), "gemini" (BYO Google
    key), and "anthropic" (BYO Anthropic key).

    When switching away from Ollama, set **both** ``vision_provider`` and
    ``vision_model`` — the factory does not auto-select a provider-specific
    default model.  Suggested defaults per spec §6.2:

    - ``ollama``     → ``qwen2.5-vl:7b``
    - ``gemini``     → ``gemini-2.5-flash``
    - ``anthropic``  → ``claude-haiku-4-5``

    Args:
        settings: Loaded application settings.

    Returns:
        A VisionProvider instance matching settings.vision_provider.

    Raises:
        ValueError:           When the chosen provider's API key is missing.
        NotImplementedError:  For any unrecognised provider string.
    """
    if settings.vision_provider == "ollama":
        from .ollama_provider import OllamaProvider

        return OllamaProvider(
            endpoint=settings.ollama_endpoint,
            model=settings.vision_model,
        )

    if settings.vision_provider == "gemini":
        from .gemini_provider import GeminiProvider

        if not settings.gemini_api_key:
            raise ValueError(
                "HEARTH_GEMINI_API_KEY is required when vision_provider='gemini'"
            )
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.vision_model)

    if settings.vision_provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        if not settings.anthropic_api_key:
            raise ValueError(
                "HEARTH_ANTHROPIC_API_KEY is required when vision_provider='anthropic'"
            )
        return AnthropicProvider(
            api_key=settings.anthropic_api_key, model=settings.vision_model
        )

    raise NotImplementedError(f"Unknown vision_provider: {settings.vision_provider}")


def get_vision_provider_from_dict(effective: dict[str, Any]) -> VisionProvider:
    """Build a VisionProvider from a pre-resolved effective-settings dict.

    Accepts the dict returned by config_overrides.get_effective_settings so
    that callers can pass DB+env-merged values without constructing a Settings
    object.
    """
    provider = effective.get("vision_provider", "ollama")

    if provider == "ollama":
        from .ollama_provider import OllamaProvider

        return OllamaProvider(
            endpoint=effective.get("ollama_endpoint", "http://localhost:11434"),
            model=effective.get("vision_model", "qwen2.5-vl:7b"),
        )

    if provider == "gemini":
        from .gemini_provider import GeminiProvider

        api_key = effective.get("gemini_api_key", "")
        if not api_key:
            raise ValueError(
                "HEARTH_GEMINI_API_KEY is required when vision_provider='gemini'"
            )
        return GeminiProvider(api_key=api_key, model=effective.get("vision_model", ""))

    if provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        api_key = effective.get("anthropic_api_key", "")
        if not api_key:
            raise ValueError(
                "HEARTH_ANTHROPIC_API_KEY is required when vision_provider='anthropic'"
            )
        return AnthropicProvider(api_key=api_key, model=effective.get("vision_model", ""))

    raise NotImplementedError(f"Unknown vision_provider: {provider}")


async def get_effective_vision_provider(session: AsyncSession) -> VisionProvider:
    """Resolve DB overrides and build the configured VisionProvider.

    Keeps the new DB-override logic local to vision configuration; callers
    in the pipeline pass a session rather than env-only Settings.
    """
    from backend.app.config_overrides import get_effective_settings

    effective = await get_effective_settings(session)
    return get_vision_provider_from_dict(effective)


__all__ = [
    "CellPromptContext",
    "ExtractedEvent",
    "FamilyPaletteEntry",
    "VisionProvider",
    "get_effective_vision_provider",
    "get_vision_provider",
    "get_vision_provider_from_dict",
]
