"""Tests for OllamaProvider using httpx.MockTransport (no real network calls).

The _transport constructor kwarg is a test seam: we inject a MockTransport
so OllamaProvider's httpx.AsyncClient never opens a real connection.

Test coverage:
- Nominal JSON parsing → ExtractedEvent tuple
- Empty cell (model returns [])
- Invalid JSON (defensive fallback)
- Malformed items in the array (skipped)
- Missing "confidence" field → defaults to 0.5
- health_check returns True on HTTP 200
- health_check returns False on HTTP 500
- health_check returns False on connection error
- image_bytes are base64-encoded in the request payload
- few_shot_corrections appear in the prompt
- model name is forwarded in the request payload
"""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from backend.app.vision import CellPromptContext, FamilyPaletteEntry
from backend.app.vision.ollama_provider import OllamaProvider

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


def _make_generate_transport(
    response_json: str,
    status_code: int = 200,
) -> httpx.MockTransport:
    """Return a MockTransport that responds to POST /api/generate."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status_code,
            json={"response": response_json, "model": "qwen2.5-vl:7b"},
        )

    return httpx.MockTransport(handler)


def _make_version_transport(status_code: int = 200) -> httpx.MockTransport:
    """Return a MockTransport that responds to GET /api/version."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status_code,
            json={"version": "0.3.0"},
        )

    return httpx.MockTransport(handler)


def _make_capture_transport(
    captured: list[httpx.Request],
    response_json: str = "[]",
) -> httpx.MockTransport:
    """Return a MockTransport that captures the request for later assertions."""

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            status_code=200,
            json={"response": response_json},
        )

    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# extract_events_from_cell — parsing
# ---------------------------------------------------------------------------


async def test_extract_events_from_cell_parses_json_response() -> None:
    """A valid JSON response is parsed into a tuple of ExtractedEvent objects."""
    events_json = json.dumps(
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
    provider = OllamaProvider(_transport=_make_generate_transport(events_json))
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
    provider = OllamaProvider(_transport=_make_generate_transport("[]"))
    result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)
    assert result == ()


async def test_extract_events_handles_invalid_json() -> None:
    """Non-JSON response returns empty tuple without raising."""
    provider = OllamaProvider(_transport=_make_generate_transport("not json at all"))
    result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)
    assert result == ()


async def test_extract_events_skips_malformed_items() -> None:
    """Valid items are kept; non-dict items (string, null) are skipped."""
    events_json = json.dumps(
        [
            {
                "title": "Good event",
                "time_text": None,
                "color_hex": None,
                "owner_guess": None,
                "confidence": 0.8,
                "raw_text": "Good event",
            },
            "this is a string not a dict",
            None,
            {
                "title": "Second event",
                "time_text": "9:00 AM",
                "color_hex": "#3A7D44",
                "owner_guess": "Danya",
                "confidence": 0.75,
                "raw_text": "Second event 9am",
            },
        ]
    )
    provider = OllamaProvider(_transport=_make_generate_transport(events_json))
    result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert len(result) == 2
    assert result[0].title == "Good event"
    assert result[1].title == "Second event"


async def test_extract_events_includes_confidence_default() -> None:
    """An item without a 'confidence' field defaults to 0.5."""
    events_json = json.dumps(
        [
            {
                "title": "Mystery event",
                "time_text": None,
                "color_hex": None,
                "owner_guess": None,
                "raw_text": "Mystery event",
                # no "confidence" key
            }
        ]
    )
    provider = OllamaProvider(_transport=_make_generate_transport(events_json))
    result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert len(result) == 1
    assert result[0].confidence == pytest.approx(0.5)


async def test_extract_events_handles_non_list_top_level() -> None:
    """Model returning a dict (not a list) yields empty tuple."""
    events_json = json.dumps({"title": "Oops, a dict not a list"})
    provider = OllamaProvider(_transport=_make_generate_transport(events_json))
    result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)
    assert result == ()


async def test_extract_events_strips_whitespace_from_title_and_raw_text() -> None:
    """Title and raw_text are stripped of surrounding whitespace."""
    events_json = json.dumps(
        [
            {
                "title": "  Dentist  ",
                "time_text": None,
                "color_hex": None,
                "owner_guess": None,
                "confidence": 0.8,
                "raw_text": "  Dentist  ",
            }
        ]
    )
    provider = OllamaProvider(_transport=_make_generate_transport(events_json))
    result = await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert result[0].title == "Dentist"
    assert result[0].raw_text == "Dentist"


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------


async def test_health_check_returns_true_on_200() -> None:
    """health_check returns True when the daemon responds with HTTP 200."""
    provider = OllamaProvider(_transport=_make_version_transport(200))
    assert await provider.health_check() is True


async def test_health_check_returns_false_on_500() -> None:
    """health_check returns False for any non-200 status."""
    provider = OllamaProvider(_transport=_make_version_transport(500))
    assert await provider.health_check() is False


async def test_health_check_returns_false_on_connection_error() -> None:
    """health_check returns False (not raises) when the connection fails."""

    def raising_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(raising_handler)
    provider = OllamaProvider(_transport=transport)
    assert await provider.health_check() is False


# ---------------------------------------------------------------------------
# Request payload assertions
# ---------------------------------------------------------------------------


async def test_extract_events_sends_image_as_base64() -> None:
    """The request body 'images' field contains base64-encoded image bytes."""
    captured: list[httpx.Request] = []
    provider = OllamaProvider(
        _transport=_make_capture_transport(captured, response_json="[]")
    )
    await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert "images" in body
    assert len(body["images"]) == 1
    decoded = base64.b64decode(body["images"][0])
    assert decoded == _FAKE_IMAGE


async def test_extract_events_includes_few_shot_corrections_in_prompt() -> None:
    """When context has corrections, the prompt text contains them."""
    captured: list[httpx.Request] = []
    ctx = CellPromptContext(
        cell_date_iso="2026-04-27",
        cell_label="Tuesday April 27",
        family_palette=_PALETTE,
        few_shot_corrections=(
            {"before": "Pikuagk Place", "after": "Pineapple Place"},
        ),
    )
    provider = OllamaProvider(
        _transport=_make_capture_transport(captured, response_json="[]")
    )
    await provider.extract_events_from_cell(_FAKE_IMAGE, ctx)

    assert len(captured) == 1
    body = json.loads(captured[0].content)
    prompt: str = body["prompt"]
    assert "Pikuagk Place" in prompt
    assert "Pineapple Place" in prompt


async def test_extract_events_sends_correct_model_name() -> None:
    """The model field in the request payload matches the configured model."""
    captured: list[httpx.Request] = []
    provider = OllamaProvider(
        model="qwen2.5-vl:7b",
        _transport=_make_capture_transport(captured, response_json="[]"),
    )
    await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert body["model"] == "qwen2.5-vl:7b"


async def test_extract_events_no_corrections_prompt_omits_correction_header() -> None:
    """With no corrections, the prompt does NOT mention the correction header."""
    captured: list[httpx.Request] = []
    provider = OllamaProvider(
        _transport=_make_capture_transport(captured, response_json="[]")
    )
    # _DEFAULT_CONTEXT has no corrections
    await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    body = json.loads(captured[0].content)
    assert "Recent corrections from the user" not in body["prompt"]


async def test_extract_events_sends_stream_false_and_format_json() -> None:
    """Request payload has stream=false and format=json for structured output."""
    captured: list[httpx.Request] = []
    provider = OllamaProvider(
        _transport=_make_capture_transport(captured, response_json="[]")
    )
    await provider.extract_events_from_cell(_FAKE_IMAGE, _DEFAULT_CONTEXT)

    body = json.loads(captured[0].content)
    assert body["stream"] is False
    assert body["format"] == "json"


# ---------------------------------------------------------------------------
# Provider name
# ---------------------------------------------------------------------------


def test_provider_name_includes_model() -> None:
    """OllamaProvider.name is 'ollama:<model>'."""
    provider = OllamaProvider(model="qwen2.5-vl:7b")
    assert provider.name == "ollama:qwen2.5-vl:7b"


def test_provider_name_custom_model() -> None:
    """OllamaProvider.name reflects a non-default model."""
    provider = OllamaProvider(model="llava:13b")
    assert provider.name == "ollama:llava:13b"
