"""InstrumentedProvider — wraps any Provider and records the
wire-level request+response for each call.

Every upstream LLM call lands in two events:

    llm.request   — exactly what we sent: provider, model,
                    messages array, tool schemas, temperature,
                    plus request id + start timestamp.
    llm.response  — what came back: assembled text, tool-calls
                    (name + final arguments), usage (prompt +
                    completion tokens), latency_ms, request id.

Session/run attribution is passed explicitly by the caller. We
originally tried a ContextVar for this, but sse_starlette runs
sync generators in a worker pool that resets the context
between yields, so the second round of a tool-calling turn
lost attribution. Explicit kwargs are uglier but correct.

Events are written via persistence.save_event (SQLite) and
telemetry.record (in-memory ring), so /traces returns both the
live and persisted view.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Iterator

from ..persistence import save_event
from ..telemetry import record
from .base import Provider, ProviderEvent, TextDelta, ToolArgsDelta, ToolCallStart, Usage


class InstrumentedProvider:
    """Wraps an inner Provider. Delegates after recording the
    request; records the response after the stream drains.
    Implements the same Provider Protocol — callers can pass
    optional session_id/run_id for attribution."""

    def __init__(self, inner: Provider) -> None:
        self._inner = inner

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def model(self) -> str:
        return self._inner.model

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float = 0.2,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> Iterator[ProviderEvent]:
        return _streaming_wrap(self._inner, messages, tools, temperature, session_id, run_id)

    def complete_json(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        *,
        session_id: str | None = None,
        run_id: str | None = None,
    ) -> str:
        req_id = f"llm_{uuid.uuid4().hex[:12]}"
        t0 = time.perf_counter()
        start_ts = time.time()

        _emit("llm.request", {
            "request_id": req_id,
            "provider": self._inner.name,
            "model": self._inner.model,
            "direction": "request",
            "kind": "complete_json",
            "messages": messages,
            "schema": schema,
            "temperature": temperature,
            "start_ts": start_ts,
        }, session_id, run_id)

        try:
            raw = self._inner.complete_json(messages=messages, schema=schema, temperature=temperature)
            status = "ok"
            error: str | None = None
        except Exception as exc:
            latency_ms = round((time.perf_counter() - t0) * 1000)
            _emit("llm.response", {
                "request_id": req_id,
                "provider": self._inner.name,
                "model": self._inner.model,
                "direction": "response",
                "kind": "complete_json",
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "latency_ms": latency_ms,
                "end_ts": time.time(),
            }, session_id, run_id)
            raise

        latency_ms = round((time.perf_counter() - t0) * 1000)
        _emit("llm.response", {
            "request_id": req_id,
            "provider": self._inner.name,
            "model": self._inner.model,
            "direction": "response",
            "kind": "complete_json",
            "status": status,
            "response": raw,
            "latency_ms": latency_ms,
            "end_ts": time.time(),
        }, session_id, run_id)
        return raw


def _streaming_wrap(
    inner: Provider,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    temperature: float,
    session_id: str | None,
    run_id: str | None,
) -> Iterator[ProviderEvent]:
    req_id = f"llm_{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter()
    start_ts = time.time()

    _emit("llm.request", {
        "request_id": req_id,
        "provider": inner.name,
        "model": inner.model,
        "direction": "request",
        "kind": "stream",
        "messages": messages,
        "tools": tools,
        "temperature": temperature,
        "start_ts": start_ts,
    }, session_id, run_id)

    text_buf = ""
    tool_calls: dict[str, dict[str, str]] = {}
    usage: Usage | None = None
    error: str | None = None

    try:
        for evt in inner.stream(messages=messages, tools=tools, temperature=temperature):
            if isinstance(evt, TextDelta):
                text_buf += evt.content
            elif isinstance(evt, ToolCallStart):
                tool_calls.setdefault(evt.id, {"id": evt.id, "name": evt.name, "args": ""})
                tool_calls[evt.id]["name"] = evt.name or tool_calls[evt.id]["name"]
            elif isinstance(evt, ToolArgsDelta):
                slot = tool_calls.setdefault(evt.id, {"id": evt.id, "name": "", "args": ""})
                slot["args"] += evt.delta
            elif isinstance(evt, Usage):
                usage = evt
            yield evt
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        latency_ms = round((time.perf_counter() - t0) * 1000)
        _emit("llm.response", {
            "request_id": req_id,
            "provider": inner.name,
            "model": inner.model,
            "direction": "response",
            "kind": "stream",
            "status": "error" if error else "ok",
            "error": error,
            "text": text_buf,
            "tool_calls": list(tool_calls.values()),
            "usage": (
                {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                }
                if usage
                else None
            ),
            "latency_ms": latency_ms,
            "end_ts": time.time(),
        }, session_id, run_id)


def _emit(event_type: str, payload: dict[str, Any], session_id: str | None, run_id: str | None) -> None:
    save_event(event_type, payload, session_id=session_id, run_id=run_id)
    record(event_type, session_id=session_id, run_id=run_id, request_id=payload.get("request_id"))
