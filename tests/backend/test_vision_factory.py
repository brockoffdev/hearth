"""Tests for the get_vision_provider factory function.

Verifies:
- Default (ollama) settings return an OllamaProvider.
- The OllamaProvider is wired with the settings' endpoint and model.
- Unimplemented providers raise NotImplementedError.
"""

from __future__ import annotations

import pytest

from backend.app.config import Settings
from backend.app.vision import VisionProvider, get_vision_provider
from backend.app.vision.ollama_provider import OllamaProvider


def _make_settings(**overrides: object) -> Settings:
    """Return a minimal Settings instance with test-safe defaults."""
    defaults: dict[str, object] = {
        "session_secret": "test-secret-do-not-use",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


def test_get_vision_provider_returns_ollama_by_default() -> None:
    """vision_provider='ollama' returns an OllamaProvider instance."""
    settings = _make_settings(vision_provider="ollama")
    provider = get_vision_provider(settings)
    assert isinstance(provider, OllamaProvider)


def test_get_vision_provider_is_vision_provider_protocol() -> None:
    """The returned OllamaProvider satisfies the VisionProvider Protocol."""
    settings = _make_settings(vision_provider="ollama")
    provider = get_vision_provider(settings)
    assert isinstance(provider, VisionProvider)


def test_get_vision_provider_wires_endpoint_from_settings() -> None:
    """OllamaProvider.endpoint matches settings.ollama_endpoint."""
    settings = _make_settings(
        vision_provider="ollama",
        ollama_endpoint="http://ollama.internal:11434",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, OllamaProvider)
    assert provider.endpoint == "http://ollama.internal:11434"


def test_get_vision_provider_wires_model_from_settings() -> None:
    """OllamaProvider.model matches settings.vision_model."""
    settings = _make_settings(
        vision_provider="ollama",
        vision_model="llava:13b",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, OllamaProvider)
    assert provider.model == "llava:13b"


def test_get_vision_provider_raises_for_gemini() -> None:
    """vision_provider='gemini' raises NotImplementedError (Task C will implement it)."""
    settings = _make_settings(vision_provider="gemini")
    with pytest.raises(NotImplementedError, match="gemini"):
        get_vision_provider(settings)


def test_get_vision_provider_raises_for_anthropic() -> None:
    """vision_provider='anthropic' raises NotImplementedError (Task C will implement it)."""
    settings = _make_settings(vision_provider="anthropic")
    with pytest.raises(NotImplementedError, match="anthropic"):
        get_vision_provider(settings)
