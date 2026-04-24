"""Tests for InstrumentedProvider.

Confirms that wrapping a provider records llm.request and
llm.response events via the persistence layer, and that the
inner provider's events still flow through unchanged.
"""

from __future__ import annotations

from typing import Any, Iterator
from unittest.mock import patch

from app.providers._instrumented import InstrumentedProvider
from app.providers.base import TextDelta, ToolArgsDelta, ToolCallStart, Usage


class Inner:
    name = "fake"
    model = "fake-m"

    def __init__(self, events: list) -> None:
        self._events = events

    def stream(self, messages, tools, temperature=0.2) -> Iterator:
        yield from self._events

    def complete_json(self, messages, schema=None, temperature=0.0) -> str:
        return '{"ok":true}'


def test_stream_records_request_and_response_with_accumulated_text() -> None:
    inner_events = [
        TextDelta(content="hello "),
        TextDelta(content="world"),
        Usage(prompt_tokens=10, completion_tokens=3),
    ]
    saved: list[tuple[str, dict[str, Any]]] = []

    def fake_save(event_type, payload, session_id=None, run_id=None):
        saved.append((event_type, payload))

    with patch("app.providers._instrumented.save_event", side_effect=fake_save):
        with patch("app.providers._instrumented.record"):  # silence telemetry
            wrapped = InstrumentedProvider(Inner(inner_events))
            out = list(wrapped.stream(
                messages=[{"role": "user", "content": "hi"}],
                tools=None,
                session_id="s_test",
                run_id="r_test",
            ))

    # Inner events flow through unchanged.
    assert [type(e).__name__ for e in out] == ["TextDelta", "TextDelta", "Usage"]

    req = next(p for t, p in saved if t == "llm.request")
    resp = next(p for t, p in saved if t == "llm.response")

    assert req["provider"] == "fake"
    assert req["model"] == "fake-m"
    assert req["kind"] == "stream"
    assert req["messages"][0]["content"] == "hi"
    assert req["request_id"] == resp["request_id"]

    assert resp["status"] == "ok"
    assert resp["text"] == "hello world"
    assert resp["usage"] == {"prompt_tokens": 10, "completion_tokens": 3}
    assert resp["latency_ms"] >= 0


def test_stream_records_tool_calls_in_response() -> None:
    inner_events = [
        ToolCallStart(id="c1", name="search"),
        ToolArgsDelta(id="c1", delta='{"q":"x"}'),
        Usage(prompt_tokens=5, completion_tokens=1),
    ]
    saved: list[tuple[str, dict[str, Any]]] = []

    def fake_save(event_type, payload, session_id=None, run_id=None):
        saved.append((event_type, payload))

    with patch("app.providers._instrumented.save_event", side_effect=fake_save):
        with patch("app.providers._instrumented.record"):
            wrapped = InstrumentedProvider(Inner(inner_events))
            list(wrapped.stream(messages=[], tools=None))

    resp = next(p for t, p in saved if t == "llm.response")
    assert resp["tool_calls"] == [{"id": "c1", "name": "search", "args": '{"q":"x"}'}]


def test_complete_json_records_both_events() -> None:
    saved: list[tuple[str, dict[str, Any]]] = []

    def fake_save(event_type, payload, session_id=None, run_id=None):
        saved.append((event_type, payload))

    with patch("app.providers._instrumented.save_event", side_effect=fake_save):
        with patch("app.providers._instrumented.record"):
            wrapped = InstrumentedProvider(Inner([]))
            raw = wrapped.complete_json(messages=[{"role": "user", "content": "?"}])

    assert raw == '{"ok":true}'
    types = [t for t, _ in saved]
    assert "llm.request" in types
    assert "llm.response" in types
    resp = next(p for t, p in saved if t == "llm.response")
    assert resp["kind"] == "complete_json"
    assert resp["response"] == '{"ok":true}'
