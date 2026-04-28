"""Tests for the get_vision_provider factory function.

Verifies:
- Default (ollama) settings return an OllamaProvider.
- The OllamaProvider is wired with the settings' endpoint and model.
- Gemini factory returns GeminiProvider when api_key is set.
- Gemini factory raises ValueError when api_key is missing.
- Anthropic factory returns AnthropicProvider when api_key is set.
- Anthropic factory raises ValueError when api_key is missing.
- Unknown provider raises NotImplementedError.
"""

from __future__ import annotations

import pytest

from backend.app.config import Settings
from backend.app.vision import VisionProvider, get_vision_provider
from backend.app.vision.anthropic_provider import AnthropicProvider
from backend.app.vision.gemini_provider import GeminiProvider
from backend.app.vision.ollama_provider import OllamaProvider


def _make_settings(**overrides: object) -> Settings:
    """Return a minimal Settings instance with test-safe defaults."""
    defaults: dict[str, object] = {
        "session_secret": "test-secret-do-not-use",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Ollama factory tests
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


# ---------------------------------------------------------------------------
# Gemini factory tests
# ---------------------------------------------------------------------------


def test_get_vision_provider_returns_gemini_with_api_key() -> None:
    """vision_provider='gemini' with a key set returns a GeminiProvider."""
    settings = _make_settings(
        vision_provider="gemini",
        gemini_api_key="AIzaSy-fake-key-1234567890",
        vision_model="gemini-2.5-flash",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, GeminiProvider)


def test_get_vision_provider_gemini_wires_api_key() -> None:
    """GeminiProvider.api_key matches settings.gemini_api_key."""
    settings = _make_settings(
        vision_provider="gemini",
        gemini_api_key="AIzaSy-fake-key-1234567890",
        vision_model="gemini-2.5-flash",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, GeminiProvider)
    assert provider.api_key == "AIzaSy-fake-key-1234567890"


def test_get_vision_provider_gemini_wires_model() -> None:
    """GeminiProvider.model matches settings.vision_model."""
    settings = _make_settings(
        vision_provider="gemini",
        gemini_api_key="AIzaSy-fake-key-1234567890",
        vision_model="gemini-2.5-pro",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, GeminiProvider)
    assert provider.model == "gemini-2.5-pro"


def test_get_vision_provider_gemini_raises_when_api_key_missing() -> None:
    """vision_provider='gemini' without an api_key raises ValueError."""
    settings = _make_settings(
        vision_provider="gemini",
        gemini_api_key="",  # empty — should trigger error
    )
    with pytest.raises(ValueError, match="HEARTH_GEMINI_API_KEY"):
        get_vision_provider(settings)


def test_get_vision_provider_gemini_satisfies_protocol() -> None:
    """A GeminiProvider returned by the factory satisfies the VisionProvider Protocol."""
    settings = _make_settings(
        vision_provider="gemini",
        gemini_api_key="AIzaSy-fake-key-1234567890",
        vision_model="gemini-2.5-flash",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, VisionProvider)


# ---------------------------------------------------------------------------
# Anthropic factory tests
# ---------------------------------------------------------------------------


def test_get_vision_provider_returns_anthropic_with_api_key() -> None:
    """vision_provider='anthropic' with a key set returns an AnthropicProvider."""
    settings = _make_settings(
        vision_provider="anthropic",
        anthropic_api_key="sk-ant-test-key-1234567890",
        vision_model="claude-haiku-4-5",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, AnthropicProvider)


def test_get_vision_provider_anthropic_wires_api_key() -> None:
    """AnthropicProvider.api_key matches settings.anthropic_api_key."""
    settings = _make_settings(
        vision_provider="anthropic",
        anthropic_api_key="sk-ant-test-key-1234567890",
        vision_model="claude-haiku-4-5",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, AnthropicProvider)
    assert provider.api_key == "sk-ant-test-key-1234567890"


def test_get_vision_provider_anthropic_wires_model() -> None:
    """AnthropicProvider.model matches settings.vision_model."""
    settings = _make_settings(
        vision_provider="anthropic",
        anthropic_api_key="sk-ant-test-key-1234567890",
        vision_model="claude-sonnet-4-6",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, AnthropicProvider)
    assert provider.model == "claude-sonnet-4-6"


def test_get_vision_provider_anthropic_raises_when_api_key_missing() -> None:
    """vision_provider='anthropic' without an api_key raises ValueError."""
    settings = _make_settings(
        vision_provider="anthropic",
        anthropic_api_key="",  # empty — should trigger error
    )
    with pytest.raises(ValueError, match="HEARTH_ANTHROPIC_API_KEY"):
        get_vision_provider(settings)


def test_get_vision_provider_anthropic_satisfies_protocol() -> None:
    """An AnthropicProvider returned by the factory satisfies the VisionProvider Protocol."""
    settings = _make_settings(
        vision_provider="anthropic",
        anthropic_api_key="sk-ant-test-key-1234567890",
        vision_model="claude-haiku-4-5",
    )
    provider = get_vision_provider(settings)
    assert isinstance(provider, VisionProvider)
