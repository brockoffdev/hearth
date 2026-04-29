"""Shared JSON-shape coercion for VLM cell extraction responses.

All three providers (Ollama, Gemini, Anthropic) ask the model for a JSON
array of event objects, but quantized / smaller models — and even hosted
ones occasionally — return wrapper shapes:

  - bare list:  ``[{...}, {...}]``       ← what we want
  - wrapped:    ``{"events": [...]}``     (also "items"/"data"/"results")
  - single arr: a dict whose only list-valued key is the events list
  - single ev:  ``{"title": "...", ...}`` (one event, not wrapped)
  - empty:      ``{}``                    (legitimately no events)

The coercion below tolerates all of these so an upload doesn't silently
drop every cell when the model's output shape drifts.  Truly unknown
shapes return an empty list — caller surfaces "no events in this cell".
"""

from __future__ import annotations

from typing import Any

_WRAPPER_KEYS: tuple[str, ...] = ("events", "items", "data", "results", "extracted")
_EVENT_FIELD_KEYS: tuple[str, ...] = ("title", "raw_text")


def coerce_to_event_list(parsed: Any) -> list[Any]:
    """Best-effort flatten of a model's JSON output to a list of event dicts.

    Returns ``[]`` when the input is genuinely empty (``[]``/``{}``) or has
    a shape we can't make sense of.  Caller should not distinguish the two
    cases — both mean "no events extractable from this response".
    """
    if isinstance(parsed, list):
        return parsed

    if not isinstance(parsed, dict) or not parsed:
        return []

    for key in _WRAPPER_KEYS:
        value = parsed.get(key)
        if isinstance(value, list):
            return value

    list_values = [v for v in parsed.values() if isinstance(v, list)]
    if len(list_values) == 1:
        return list_values[0]

    if any(field in parsed for field in _EVENT_FIELD_KEYS):
        return [parsed]

    return []
