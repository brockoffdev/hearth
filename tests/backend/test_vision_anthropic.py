"""Tests for AnthropicProvider using unittest.mock (no real API calls).

All anthropic.AsyncAnthropic calls are patched at the module boundary.

Test coverage:
- JSON response parsed into ExtractedEvent tuple.
- Markdown code fence stripping (```json ... ```).
- Empty response → empty tuple.
- health_check validates API key format.
- Provider name format: "anthropic:<model>".
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.vision import CellPromptContext, FamilyPaletteEntry
from backend.app.vision.anthropic_provider import AnthropicProvider

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
            "title": "Doctor appointment",
            "time_text": "10:00 AM",
            "color_hex": "#3A7D44",
            "owner_guess": "Danya",
            "confidence": 0.88,
            "raw_text": "Doctor appt 10am",
        }
    ]
)


def _make_mock_client(response_text: str) -> MagicMock:
    """Return a mock AsyncAnthropic whose messages.create returns response_text."""
    mock_text_block = MagicMock()
    mock_text_block.text = response_text

    mock_response = MagicMock()
    mock_response.content = [mock_text_block]

    mock_messages = MagicMock()
    mock_messages.create = AsyncMock(return_value=mock_response)

    mock_client = MagicMock()
    mock_client.messages = mock_messages
    return mock_client


# ---------------------------------------------------------------------------
# extract_events_from_cell — parsing
# ---------------------------------------------------------------------------


async def test_extract_events_from_cell_parses_response() -> None:
    """A valid JSON response is parsed into a tuple of ExtractedEvent objects."""
    mock_client = _make_mock_client(_SINGLE_EVENT_JSON)

    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert len(result) == 1
    event = result[0]
    assert event.title == "Doctor appointment"
    assert event.time_text == "10:00 AM"
    assert event.color_hex == "#3A7D44"
    assert event.owner_guess == "Danya"
    assert event.confidence == pytest.approx(0.88)
    assert event.raw_text == "Doctor appt 10am"


async def test_extract_events_strips_markdown_code_fences() -> None:
    """JSON wrapped in ```json ... ``` fences is parsed correctly."""
    fenced = f"```json\n{_SINGLE_EVENT_JSON}\n```"
    mock_client = _make_mock_client(fenced)

    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert len(result) == 1
    assert result[0].title == "Doctor appointment"


async def test_extract_events_strips_plain_code_fences() -> None:
    """JSON wrapped in plain ``` fences (no language tag) is also parsed."""
    fenced = f"```\n{_SINGLE_EVENT_JSON}\n```"
    mock_client = _make_mock_client(fenced)

    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert len(result) == 1
    assert result[0].title == "Doctor appointment"


async def test_extract_events_handles_empty_response() -> None:
    """An empty-ish response (empty content text) returns an empty tuple."""
    mock_client = _make_mock_client("[]")

    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert result == ()


async def test_extract_events_handles_no_text_blocks() -> None:
    """A response with no text blocks returns an empty tuple."""
    # Simulate a response where content blocks have no .text attribute
    mock_block = MagicMock(spec=[])  # No attributes at all

    mock_response = MagicMock()
    mock_response.content = [mock_block]

    mock_messages = MagicMock()
    mock_messages.create = AsyncMock(return_value=mock_response)

    mock_client = MagicMock()
    mock_client.messages = mock_messages

    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890")
        result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert result == ()


async def test_extract_events_sends_image_as_base64_content_block() -> None:
    """messages.create is called with an image content block containing base64 data."""
    import base64

    mock_client = _make_mock_client("[]")

    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890")
        await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    create_call = mock_client.messages.create
    call_kwargs = create_call.call_args[1]
    messages = call_kwargs["messages"]
    assert len(messages) == 1
    content = messages[0]["content"]
    # First block is the image
    image_block = content[0]
    assert image_block["type"] == "image"
    assert image_block["source"]["type"] == "base64"
    assert image_block["source"]["media_type"] == "image/jpeg"
    expected_b64 = base64.standard_b64encode(_FAKE_IMAGE).decode("utf-8")
    assert image_block["source"]["data"] == expected_b64


async def test_extract_events_sends_prompt_as_text_content_block() -> None:
    """messages.create is called with a text content block containing the prompt."""
    mock_client = _make_mock_client("[]")

    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic", return_value=mock_client):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890")
        await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    call_kwargs = mock_client.messages.create.call_args[1]
    messages = call_kwargs["messages"]
    content = messages[0]["content"]
    # Second block is the text/prompt
    text_block = content[1]
    assert text_block["type"] == "text"
    assert "Tuesday April 27" in text_block["text"]


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


async def test_health_check_validates_api_key_format_valid() -> None:
    """health_check returns True for a properly formatted sk-ant-... key."""
    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(api_key="sk-ant-api-03-abcdefghijklmn")
    result = await provider.health_check()
    assert result is True


async def test_health_check_validates_api_key_format_invalid() -> None:
    """health_check returns False for a key that doesn't start with 'sk-ant-'."""
    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(api_key="bad-key-1234")
    result = await provider.health_check()
    assert result is False


async def test_health_check_returns_false_for_short_key() -> None:
    """health_check returns False for a key that is too short."""
    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(api_key="sk-ant-")
    result = await provider.health_check()
    assert result is False


async def test_health_check_returns_false_for_empty_key() -> None:
    """health_check returns False for an empty string key."""
    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(api_key="")
    result = await provider.health_check()
    assert result is False


# ---------------------------------------------------------------------------
# Provider name
# ---------------------------------------------------------------------------


def test_provider_name_format() -> None:
    """AnthropicProvider.name is 'anthropic:<model>'."""
    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890", model="claude-haiku-4-5")
    assert provider.name == "anthropic:claude-haiku-4-5"


def test_provider_name_default_model() -> None:
    """AnthropicProvider.name uses 'claude-haiku-4-5' as the default model."""
    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(api_key="sk-ant-test-key-1234567890")
    assert provider.name == "anthropic:claude-haiku-4-5"


def test_provider_name_custom_model() -> None:
    """AnthropicProvider.name reflects a non-default model like claude-sonnet-4-6."""
    with patch("backend.app.vision.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(
            api_key="sk-ant-test-key-1234567890", model="claude-sonnet-4-6"
        )
    assert provider.name == "anthropic:claude-sonnet-4-6"
