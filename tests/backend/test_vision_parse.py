"""Unit tests for backend.app.vision._parse.coerce_to_event_list.

Each VisionProvider drives this helper through its own _parse_response,
but the shape coercion is provider-agnostic and worth testing on its own
so future shape additions don't have to triple-test.
"""

from __future__ import annotations

import pytest

from backend.app.vision._parse import coerce_to_event_list


def test_bare_list_passes_through() -> None:
    items = [{"title": "A"}, {"title": "B"}]
    assert coerce_to_event_list(items) == items


def test_empty_list_returns_empty() -> None:
    assert coerce_to_event_list([]) == []


def test_empty_dict_returns_empty() -> None:
    assert coerce_to_event_list({}) == []


@pytest.mark.parametrize("key", ["events", "items", "data", "results", "extracted"])
def test_common_wrapper_keys_are_unwrapped(key: str) -> None:
    inner = [{"title": "Wrapped"}]
    assert coerce_to_event_list({key: inner}) == inner


def test_arbitrary_single_list_key_is_unwrapped() -> None:
    inner = [{"title": "Anything"}]
    assert coerce_to_event_list({"calendar_entries_2026": inner}) == inner


def test_dict_with_multiple_list_values_returns_empty() -> None:
    """Ambiguous: two list-valued keys, can't pick one."""
    parsed = {"events": [{"title": "A"}], "skipped": [{"title": "B"}]}
    # Wrapper key 'events' wins because it's checked first.
    assert coerce_to_event_list(parsed) == [{"title": "A"}]


def test_dict_with_two_list_values_no_wrapper_key_returns_empty() -> None:
    """Both values are lists, neither key is a known wrapper → ambiguous."""
    parsed = {"alpha": [{"title": "A"}], "beta": [{"title": "B"}]}
    assert coerce_to_event_list(parsed) == []


def test_single_event_object_is_wrapped_in_list() -> None:
    parsed = {"title": "Single", "time_text": "9am", "raw_text": "Single 9am"}
    assert coerce_to_event_list(parsed) == [parsed]


def test_single_event_object_with_only_raw_text_is_wrapped() -> None:
    parsed = {"raw_text": "scribbled note"}
    assert coerce_to_event_list(parsed) == [parsed]


def test_dict_without_recognizable_shape_returns_empty() -> None:
    assert coerce_to_event_list({"irrelevant": "value", "other": 42}) == []


def test_non_dict_non_list_returns_empty() -> None:
    """Strings, ints, None, etc. → empty."""
    assert coerce_to_event_list("hello") == []
    assert coerce_to_event_list(42) == []
    assert coerce_to_event_list(None) == []
