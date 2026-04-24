"""Unit tests for the agent loop.

Tests use a tiny FakeProvider that emits a scripted sequence of
ProviderEvents per stream() call. That's the whole seam — the
agent loop has no other coupling to a vendor SDK.
"""

from __future__ import annotations

from typing import Any, Iterator

from app.agent import Tool, run_turn
from app.providers.base import Provider, ProviderEvent, TextDelta, ToolArgsDelta, ToolCallStart, Usage


class FakeProvider:
    """Provider stub. Supply a list of event lists (one per round)."""

    name = "fake"
    model = "fake-model"

    def __init__(self, rounds: list[list[ProviderEvent]]) -> None:
        self._rounds = list(rounds)
        self.call_count = 0
        self.json_calls: list[list[dict[str, Any]]] = []
        self.json_response = "{}"

    def stream(self, messages, tools, temperature=0.2, *, session_id=None, run_id=None) -> Iterator[ProviderEvent]:
        idx = self.call_count
        self.call_count += 1
        if idx >= len(self._rounds):
            raise AssertionError(f"FakeProvider called {self.call_count} times; only {len(self._rounds)} rounds scripted")
        yield from self._rounds[idx]

    def complete_json(self, messages, schema=None, temperature=0.0, *, session_id=None, run_id=None) -> str:
        self.json_calls.append(list(messages))
        return self.json_response


def test_agent_tool_call_then_final_answer() -> None:
    fake = FakeProvider([
        [
            ToolCallStart(id="call_1", name="echo"),
            ToolArgsDelta(id="call_1", delta='{"value":'),
            ToolArgsDelta(id="call_1", delta=' "hi"}'),
            Usage(prompt_tokens=50, completion_tokens=20),
        ],
        [
            TextDelta(content="The tool returned hi."),
            Usage(prompt_tokens=80, completion_tokens=15),
        ],
    ])

    def echo_fn(args: dict[str, Any]) -> dict[str, Any]:
        return {"echo": args.get("value")}

    echo = Tool(
        name="echo",
        description="Echoes the input.",
        parameters={"type": "object", "properties": {"value": {"type": "string"}}, "required": ["value"]},
        fn=echo_fn,
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": "you are a test bot"},
        {"role": "user", "content": "say hi"},
    ]

    events = list(run_turn(session_id="s_test", messages=messages, tools=[echo], provider=fake))

    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert types[-1] == "done"

    tool_call = next(e for e in events if e.type == "tool_call")
    assert tool_call.data["name"] == "echo"
    assert tool_call.data["args"] == {"value": "hi"}

    tool_result = next(e for e in events if e.type == "tool_result")
    assert tool_result.data["result"] == {"echo": "hi"}

    done = events[-1]
    assert done.data["content"] == "The tool returned hi."

    assert fake.call_count == 2
    # The conversation was mutated: assistant(tool_calls), tool, assistant(final).
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "The tool returned hi."
    assert any(m["role"] == "tool" for m in messages)


def test_agent_streams_plain_text_when_no_tools() -> None:
    fake = FakeProvider([
        [
            TextDelta(content="hello "),
            TextDelta(content="world"),
            Usage(prompt_tokens=10, completion_tokens=2),
        ],
    ])

    messages = [{"role": "user", "content": "hi"}]
    events = list(run_turn(session_id="s_test2", messages=messages, tools=[], provider=fake))

    tokens = [e.data["content"] for e in events if e.type == "token"]
    assert "".join(tokens) == "hello world"
    assert events[-1].type == "done"


def test_agent_handles_tool_exception() -> None:
    def broken(args: dict[str, Any]) -> Any:
        raise RuntimeError("kaboom")

    tool = Tool(
        name="broken",
        description="broken tool",
        parameters={"type": "object", "properties": {}},
        fn=broken,
    )

    fake = FakeProvider([
        [
            ToolCallStart(id="c1", name="broken"),
            ToolArgsDelta(id="c1", delta="{}"),
            Usage(prompt_tokens=5, completion_tokens=1),
        ],
        [
            TextDelta(content="Sorry, tool failed."),
            Usage(prompt_tokens=7, completion_tokens=3),
        ],
    ])

    events = list(run_turn(
        session_id="s_test3",
        messages=[{"role": "user", "content": "go"}],
        tools=[tool],
        provider=fake,
    ))

    result_evt = next(e for e in events if e.type == "tool_result")
    assert "error" in result_evt.data["result"]
    assert events[-1].type == "done"


def test_agent_attributes_usage_to_provider_and_model() -> None:
    """Budget lookup keys off (provider, model); make sure both pass through."""
    fake = FakeProvider([
        [
            TextDelta(content="ok"),
            Usage(prompt_tokens=100, completion_tokens=50),
        ],
    ])
    messages = [{"role": "user", "content": "hi"}]
    events = list(run_turn(session_id="s_prov", messages=messages, tools=[], provider=fake))

    usage_evts = [e for e in events if e.type == "usage"]
    assert len(usage_evts) == 1
    assert usage_evts[0].data["provider"] == "fake"
    assert usage_evts[0].data["model"] == "fake-model"
    assert usage_evts[0].data["prompt_tokens"] == 100
    assert usage_evts[0].data["completion_tokens"] == 50
