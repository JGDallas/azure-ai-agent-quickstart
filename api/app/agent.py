"""The agent loop.

This is the piece the repo is meant to teach. Read it top to
bottom. A turn works like this:

    1. Ask the active provider to stream a response for the
       current conversation + tool schemas.
    2. As events arrive (text deltas, tool-call starts, tool-arg
       deltas, and a final usage record), pass text straight
       through to the caller and assemble tool calls by id.
    3. If the round produced tool_calls, execute each, append
       the assistant message (with tool_calls) and one `role:
       tool` message per result, then loop.
    4. Otherwise, the assistant produced plain text — emit a
       `done` event and return.

The provider abstraction in `providers/base.py` means this file
has zero vendor knowledge. Swap LLM_PROVIDER in .env and the
same loop runs against Azure, OpenAI, or (Phase 2) Anthropic.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from .budget import BudgetExceeded, apply_usage, remaining
from .providers import Provider, TextDelta, ToolArgsDelta, ToolCallStart, Usage

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
    provider: Provider,
) -> Iterator[AgentEvent]:
    """Run one user turn, yielding AgentEvents as things happen.

    `messages` is mutated in place so the caller can persist the
    final conversation state.
    """
    tool_schemas = [t.schema() for t in tools]
    tool_by_name = {t.name: t for t in tools}

    for _iteration in range(MAX_ITERATIONS):
        # Circuit breaker: bail early if the session is already
        # over budget. We still call the model for the final text
        # turn up to the cap — this is just belt and suspenders.
        rem = remaining(session_id)
        if rem["tokens"] <= 0 or rem["usd"] <= 0:
            yield AgentEvent("error", {"message": "Session budget exhausted."})
            return

        try:
            stream = provider.stream(messages=messages, tools=tool_schemas)
        except Exception as exc:  # surface auth/config errors to the UI
            yield AgentEvent("error", {"message": f"LLM call failed: {exc}"})
            return

        content_buf = ""
        # Ordered so we can serialize assistant.tool_calls in call order.
        tool_calls: dict[str, dict[str, str]] = {}
        usage: Usage | None = None

        for evt in stream:
            if isinstance(evt, TextDelta):
                if evt.content:
                    content_buf += evt.content
                    yield AgentEvent("token", {"content": evt.content})
            elif isinstance(evt, ToolCallStart):
                tool_calls.setdefault(evt.id, {"id": evt.id, "name": evt.name, "args": ""})
                # Keep name fresh if a later event updates it.
                tool_calls[evt.id]["name"] = evt.name or tool_calls[evt.id]["name"]
            elif isinstance(evt, ToolArgsDelta):
                slot = tool_calls.setdefault(evt.id, {"id": evt.id, "name": "", "args": ""})
                slot["args"] += evt.delta
            elif isinstance(evt, Usage):
                usage = evt

        # Apply usage to the session budget. If this turn pushed
        # us over, emit the event anyway so the UI updates, then
        # stop.
        if usage is not None:
            try:
                usage_payload = apply_usage(
                    session_id,
                    provider=provider.name,
                    model=provider.model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                )
                yield AgentEvent("usage", usage_payload)
            except BudgetExceeded as exc:
                yield AgentEvent("error", {"message": str(exc)})
                return

        # No tool calls -> the assistant just wrote prose. Persist
        # the message and we're done with this turn.
        if not tool_calls:
            messages.append({"role": "assistant", "content": content_buf})
            yield AgentEvent("done", {"content": content_buf})
            return

        # Tool calls present: record the assistant message exactly
        # as the OpenAI API expects, then execute each tool in order.
        messages.append({
            "role": "assistant",
            "content": content_buf or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["args"] or "{}"},
                }
                for tc in tool_calls.values()
            ],
        })

        for tc in tool_calls.values():
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
