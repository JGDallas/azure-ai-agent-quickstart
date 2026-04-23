"""The agent loop.

This is the piece the repo is meant to teach. Read it top to
bottom. A turn works like this:

    1. Send the conversation + tool schemas to Azure OpenAI with
       streaming enabled.
    2. As chunks arrive, stream text deltas straight to the
       caller AND assemble any tool_calls by index.
    3. If the round produced tool_calls, execute each tool,
       append the assistant message (with tool_calls) and one
       `role: tool` message per result, then loop.
    4. Otherwise, the assistant produced plain text — emit a
       `done` event and return.

There's a hard cap on iterations so a buggy tool loop can't burn
the whole token budget. Budget accounting runs after every round
and halts the turn if the session cap would be exceeded.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from .budget import BudgetExceeded, apply_usage, remaining
from .llm import chat_stream

MAX_ITERATIONS = 6


@dataclass
class AgentEvent:
    """One SSE-shaped event emitted during a turn."""
    type: str  # token | tool_call | tool_result | usage | done | error
    data: dict[str, Any] = field(default_factory=dict)


ToolFn = Callable[[dict[str, Any]], Any]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]   # JSON schema
    fn: ToolFn

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def run_turn(
    session_id: str,
    messages: list[dict[str, Any]],
    tools: list[Tool],
) -> Iterator[AgentEvent]:
    """Run one user turn, yielding AgentEvents as things happen.

    `messages` is mutated in place so the caller can persist the
    final conversation state.
    """
    tool_schemas = [t.schema() for t in tools]
    tool_by_name = {t.name: t for t in tools}

    for iteration in range(MAX_ITERATIONS):
        # Cheap pre-flight: bail early if the session is already
        # over budget. We still call the model for the final text
        # turn up to the cap — this is just the circuit breaker.
        rem = remaining(session_id)
        if rem["tokens"] <= 0 or rem["usd"] <= 0:
            yield AgentEvent("error", {"message": "Session budget exhausted."})
            return

        try:
            stream = chat_stream(messages=messages, tools=tool_schemas)
        except Exception as exc:  # surface auth/config errors to the UI
            yield AgentEvent("error", {"message": f"LLM call failed: {exc}"})
            return

        content_buf = ""
        tool_calls_buf: dict[int, dict[str, str]] = {}
        usage: Any = None

        for chunk in stream:
            # Usage chunk arrives last when stream_options.include_usage=True.
            if getattr(chunk, "usage", None):
                usage = chunk.usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content_buf += delta.content
                yield AgentEvent("token", {"content": delta.content})
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    slot = tool_calls_buf.setdefault(
                        tc.index, {"id": "", "name": "", "args": ""}
                    )
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        slot["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments

        # Apply usage to the session budget. If this turn pushed
        # us over, emit the event anyway so the UI updates, then
        # stop.
        usage_payload = None
        if usage is not None:
            try:
                usage_payload = apply_usage(
                    session_id,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                )
                yield AgentEvent("usage", usage_payload)
            except BudgetExceeded as exc:
                yield AgentEvent("error", {"message": str(exc)})
                return

        # No tool calls -> the assistant just wrote prose. Persist
        # the message and we're done with this turn.
        if not tool_calls_buf:
            messages.append({"role": "assistant", "content": content_buf})
            yield AgentEvent("done", {"content": content_buf})
            return

        # Tool calls present: record the assistant message exactly
        # as the API expects, then execute each tool in order.
        ordered = [tool_calls_buf[i] for i in sorted(tool_calls_buf)]
        messages.append({
            "role": "assistant",
            "content": content_buf or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["args"] or "{}"},
                }
                for tc in ordered
            ],
        })

        for tc in ordered:
            try:
                args = json.loads(tc["args"] or "{}")
            except json.JSONDecodeError:
                args = {}
            yield AgentEvent("tool_call", {"id": tc["id"], "name": tc["name"], "args": args})

            tool = tool_by_name.get(tc["name"])
            t0 = time.perf_counter()
            if tool is None:
                result: Any = {"error": f"Unknown tool: {tc['name']}"}
            else:
                try:
                    result = tool.fn(args)
                except Exception as exc:  # never crash the turn on a bad tool
                    result = {"error": f"{type(exc).__name__}: {exc}"}
            latency_ms = round((time.perf_counter() - t0) * 1000)

            yield AgentEvent("tool_result", {
                "id": tc["id"],
                "name": tc["name"],
                "result": result,
                "latency_ms": latency_ms,
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, default=str),
            })

        # Loop back and let the model read the tool outputs.

    yield AgentEvent("error", {"message": f"Max iterations ({MAX_ITERATIONS}) hit."})
