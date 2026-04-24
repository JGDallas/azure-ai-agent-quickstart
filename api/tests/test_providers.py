"""Smoke tests for the OpenAI-compatible adapter.

We stub the openai-sdk client so we can drive canned chunks
through the adapter and assert the internal ProviderEvent
sequence comes out right.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.providers._openai_compat import OpenAICompatProvider
from app.providers.base import TextDelta, ToolArgsDelta, ToolCallStart, Usage


def _chunk(
    content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    usage: tuple[int, int] | None = None,
) -> Any:
    delta = SimpleNamespace(content=content, tool_calls=None)
    if tool_calls:
        delta.tool_calls = [
            SimpleNamespace(
                index=tc["index"],
                id=tc.get("id"),
                function=SimpleNamespace(
                    name=tc.get("name"),
                    arguments=tc.get("arguments"),
                ),
            )
            for tc in tool_calls
        ]
    has_delta = content is not None or bool(tool_calls)
    choice = SimpleNamespace(delta=delta) if has_delta else None
    u = None
    if usage is not None:
        u = SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1])
    return SimpleNamespace(choices=[choice] if choice else [], usage=u)


class FakeCompletions:
    def __init__(self, chunks: list[Any], json_response: str = "{}") -> None:
        self._chunks = chunks
        self._json_response = json_response
        self.create_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.create_calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(self._chunks)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self._json_response))]
        )


class FakeClient:
    def __init__(self, completions: FakeCompletions) -> None:
        self.chat = SimpleNamespace(completions=completions)


def test_stream_yields_text_and_usage_in_order() -> None:
    chunks = [
        _chunk(content="hello"),
        _chunk(content=" world"),
        _chunk(usage=(12, 4)),
    ]
    client = FakeClient(FakeCompletions(chunks))
    p = OpenAICompatProvider(client=client, model="m", name="t")

    events = list(p.stream(messages=[{"role": "user", "content": "hi"}], tools=None))

    assert isinstance(events[0], TextDelta) and events[0].content == "hello"
    assert isinstance(events[1], TextDelta) and events[1].content == " world"
    assert isinstance(events[2], Usage)
    assert events[2].prompt_tokens == 12
    assert events[2].completion_tokens == 4


def test_stream_assembles_tool_call_ids_and_args() -> None:
    chunks = [
        _chunk(tool_calls=[{"index": 0, "id": "call_a", "name": "search", "arguments": ""}]),
        _chunk(tool_calls=[{"index": 0, "arguments": '{"q":'}]),
        _chunk(tool_calls=[{"index": 0, "arguments": ' "x"}'}]),
        _chunk(usage=(5, 1)),
    ]
    client = FakeClient(FakeCompletions(chunks))
    p = OpenAICompatProvider(client=client, model="m", name="t")

    events = list(p.stream(messages=[], tools=[{"type": "function", "function": {"name": "search", "parameters": {}}}]))

    starts = [e for e in events if isinstance(e, ToolCallStart)]
    deltas = [e for e in events if isinstance(e, ToolArgsDelta)]
    assert len(starts) == 1
    assert starts[0].id == "call_a"
    assert starts[0].name == "search"
    # ToolArgsDelta events carry the call id, not the sdk index.
    assert all(d.id == "call_a" for d in deltas)
    assert "".join(d.delta for d in deltas) == '{"q": "x"}'


def test_complete_json_requests_json_object_response_format() -> None:
    completions = FakeCompletions(chunks=[], json_response='{"score":5}')
    client = FakeClient(completions)
    p = OpenAICompatProvider(client=client, model="m", name="t")

    out = p.complete_json(messages=[{"role": "user", "content": "score"}])
    assert out == '{"score":5}'
    assert completions.create_calls[0]["response_format"] == {"type": "json_object"}
    assert "stream" not in completions.create_calls[0]  # non-streaming call
