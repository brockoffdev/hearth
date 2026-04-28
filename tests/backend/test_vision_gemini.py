"""Tests for GeminiProvider using unittest.mock (no real API calls).

All google.generativeai calls are patched at the module boundary.

Test coverage:
- JSON response parsed into ExtractedEvent tuple.
- Empty cell (model returns []).
- Invalid JSON → empty tuple without raising.
- health_check returns True when model is listed.
- health_check returns False on exception.
- Provider name format: "gemini:<model>".
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.vision import CellPromptContext, FamilyPaletteEntry
from backend.app.vision.gemini_provider import GeminiProvider

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

_FAKE_IMAGE = b"\xff\xd8\xff\xe0fake-jpeg"

_SINGLE_EVENT_JSON = json.dumps(
    [
        {
            "title": "Soccer practice",
            "time_text": "4:00 PM",
            "color_hex": "#2E5BA8",
            "owner_guess": "Bryant",
            "confidence": 0.92,
            "raw_text": "Soccer practice 4pm",
        }
    ]
)


def _make_mock_model(response_text: str) -> MagicMock:
    """Return a mock GenerativeModel whose generate_content_async returns response_text."""
    mock_response = MagicMock()
    mock_response.text = response_text

    mock_model = MagicMock()
    mock_model.generate_content_async = AsyncMock(return_value=mock_response)
    return mock_model


# ---------------------------------------------------------------------------
# extract_events_from_cell
# ---------------------------------------------------------------------------


async def test_extract_events_from_cell_parses_json_response() -> None:
    """A valid JSON response is parsed into a tuple of ExtractedEvent objects."""
    mock_model = _make_mock_model(_SINGLE_EVENT_JSON)

    with (
        patch("backend.app.vision.gemini_provider.genai") as mock_genai,
    ):
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key="fake-key")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert len(result) == 1
    event = result[0]
    assert event.title == "Soccer practice"
    assert event.time_text == "4:00 PM"
    assert event.color_hex == "#2E5BA8"
    assert event.owner_guess == "Bryant"
    assert event.confidence == pytest.approx(0.92)
    assert event.raw_text == "Soccer practice 4pm"


async def test_extract_events_handles_empty_cell() -> None:
    """Model returning [] yields an empty tuple."""
    mock_model = _make_mock_model("[]")

    with patch("backend.app.vision.gemini_provider.genai") as mock_genai:
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key="fake-key")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert result == ()


async def test_extract_events_handles_invalid_json() -> None:
    """Non-JSON response returns empty tuple without raising."""
    mock_model = _make_mock_model("not valid json at all")

    with patch("backend.app.vision.gemini_provider.genai") as mock_genai:
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key="fake-key")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert result == ()


async def test_extract_events_handles_none_text_response() -> None:
    """A None text response (model returned nothing) is treated as empty."""
    mock_model = _make_mock_model(None)  # type: ignore[arg-type]

    with patch("backend.app.vision.gemini_provider.genai") as mock_genai:
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key="fake-key")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert result == ()


async def test_extract_events_sends_image_to_api() -> None:
    """generate_content_async is called with image bytes in the content parts."""
    mock_model = _make_mock_model("[]")

    with patch("backend.app.vision.gemini_provider.genai") as mock_genai:
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key="fake-key")
        await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    mock_model.generate_content_async.assert_called_once()
    call_args = mock_model.generate_content_async.call_args
    # The first positional argument is the content list: [prompt_str, image_part_dict]
    content_parts = call_args[0][0]
    assert len(content_parts) == 2
    # Second part should be the image dict
    image_part = content_parts[1]
    assert isinstance(image_part, dict)
    assert image_part["data"] == _FAKE_IMAGE
    assert image_part["mime_type"] == "image/jpeg"


async def test_extract_events_uses_json_response_mime_type() -> None:
    """generate_content_async is called with response_mime_type='application/json'."""
    mock_model = _make_mock_model("[]")

    with patch("backend.app.vision.gemini_provider.genai") as mock_genai:
        mock_genai.GenerativeModel.return_value = mock_model

        provider = GeminiProvider(api_key="fake-key")
        await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    call_kwargs = mock_model.generate_content_async.call_args[1]
    gen_config = call_kwargs.get("generation_config", {})
    assert gen_config.get("response_mime_type") == "application/json"


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


async def test_health_check_returns_true_when_model_listed() -> None:
    """health_check returns True when genai.list_models includes the configured model."""

    class _FakeModel:
        name = "models/gemini-2.5-flash"

    with patch("backend.app.vision.gemini_provider.genai") as mock_genai:
        mock_genai.list_models.return_value = [_FakeModel()]

        provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-flash")
        result = await provider.health_check()

    assert result is True


async def test_health_check_returns_false_when_model_not_listed() -> None:
    """health_check returns False when the configured model is not in the list."""

    class _FakeModel:
        name = "models/gemini-1.0-pro"

    with patch("backend.app.vision.gemini_provider.genai") as mock_genai:
        mock_genai.list_models.return_value = [_FakeModel()]

        provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-flash")
        result = await provider.health_check()

    assert result is False


async def test_health_check_returns_false_on_exception() -> None:
    """health_check returns False (not raises) when genai.list_models raises."""
    with patch("backend.app.vision.gemini_provider.genai") as mock_genai:
        mock_genai.list_models.side_effect = Exception("Auth failed")

        provider = GeminiProvider(api_key="bad-key")
        result = await provider.health_check()

    assert result is False


# ---------------------------------------------------------------------------
# Provider name
# ---------------------------------------------------------------------------


def test_provider_name_format() -> None:
    """GeminiProvider.name is 'gemini:<model>'."""
    with patch("backend.app.vision.gemini_provider.genai"):
        provider = GeminiProvider(api_key="fake-key", model="gemini-2.5-flash")
    assert provider.name == "gemini:gemini-2.5-flash"


def test_provider_name_default_model() -> None:
    """GeminiProvider.name uses 'gemini-2.5-flash' as the default model."""
    with patch("backend.app.vision.gemini_provider.genai"):
        provider = GeminiProvider(api_key="fake-key")
    assert provider.name == "gemini:gemini-2.5-flash"
