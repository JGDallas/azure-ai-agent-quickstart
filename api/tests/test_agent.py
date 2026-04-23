"""Unit tests for the agent loop.

We stub the Azure OpenAI client so we can script a two-round
scenario: the model calls a tool, the tool returns a value, the
model reads the result and produces a final text answer.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterator
from unittest.mock import patch

import pytest

from app.agent import Tool, run_turn


# ---------- Helpers to build fake streaming chunks ----------

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
    choice = SimpleNamespace(delta=delta)
    u = None
    if usage is not None:
        u = SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1])
    return SimpleNamespace(choices=[choice] if content or tool_calls else [], usage=u)


def _script(rounds: list[list[Any]]) -> Iterator[list[Any]]:
    for chunks in rounds:
        yield chunks


def test_agent_tool_call_then_final_answer() -> None:
    call_count = {"n": 0}

    round_one = [
        _chunk(tool_calls=[{"index": 0, "id": "call_1", "name": "echo", "arguments": ""}]),
        _chunk(tool_calls=[{"index": 0, "arguments": '{"value":'}]),
        _chunk(tool_calls=[{"index": 0, "arguments": ' "hi"}'}]),
        _chunk(usage=(50, 20)),
    ]
    round_two = [
        _chunk(content="The tool returned hi."),
        _chunk(usage=(80, 15)),
    ]
    scripted = [round_one, round_two]

    def fake_stream(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, temperature: float = 0.2) -> Any:
        idx = call_count["n"]
        call_count["n"] += 1
        return iter(scripted[idx])

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

    with patch("app.agent.chat_stream", side_effect=fake_stream):
        events = list(run_turn(session_id="s_test", messages=messages, tools=[echo]))

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

    # Model was called twice: one tool round, one final answer.
    assert call_count["n"] == 2

    # Conversation was mutated: assistant(tool_calls), tool, assistant(final).
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "The tool returned hi."
    assert any(m["role"] == "tool" for m in messages)


def test_agent_streams_plain_text_when_no_tools() -> None:
    round_one = [
        _chunk(content="hello "),
        _chunk(content="world"),
        _chunk(usage=(10, 2)),
    ]

    def fake_stream(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, temperature: float = 0.2) -> Any:
        return iter(round_one)

    messages = [{"role": "user", "content": "hi"}]

    with patch("app.agent.chat_stream", side_effect=fake_stream):
        events = list(run_turn(session_id="s_test2", messages=messages, tools=[]))

    tokens = [e.data["content"] for e in events if e.type == "token"]
    assert "".join(tokens) == "hello world"
    assert events[-1].type == "done"


def test_agent_handles_tool_exception() -> None:
    call_count = {"n": 0}

    def broken(args: dict[str, Any]) -> Any:
        raise RuntimeError("kaboom")

    tool = Tool(
        name="broken",
        description="broken tool",
        parameters={"type": "object", "properties": {}},
        fn=broken,
    )

    rounds = [
        [_chunk(tool_calls=[{"index": 0, "id": "c1", "name": "broken", "arguments": "{}"}]),
         _chunk(usage=(5, 1))],
        [_chunk(content="Sorry, tool failed."), _chunk(usage=(7, 3))],
    ]

    def fake_stream(messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, temperature: float = 0.2) -> Any:
        idx = call_count["n"]
        call_count["n"] += 1
        return iter(rounds[idx])

    with patch("app.agent.chat_stream", side_effect=fake_stream):
        events = list(run_turn(session_id="s_test3", messages=[{"role": "user", "content": "go"}], tools=[tool]))

    result_evt = next(e for e in events if e.type == "tool_result")
    assert "error" in result_evt.data["result"]
    assert events[-1].type == "done"
