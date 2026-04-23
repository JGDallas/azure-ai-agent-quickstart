"""POST /chat — streams an agent turn as SSE."""

from __future__ import annotations

import json
import uuid
from typing import Any, Iterator

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..agent import run_turn
from ..agents_registry import get_agent, list_agents
from ..budget import get as budget_get
from ..persistence import (
    create_session,
    finish_run,
    load_messages,
    save_event,
    save_message,
    start_run,
)
from ..telemetry import record

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    agent: str
    message: str


@router.get("/agents")
def agents() -> list[dict[str, Any]]:
    return list_agents()


@router.post("/chat")
def chat(req: ChatRequest) -> EventSourceResponse:
    spec = get_agent(req.agent)

    session_id = req.session_id or f"s_{uuid.uuid4().hex[:12]}"
    run_id = f"r_{uuid.uuid4().hex[:12]}"
    create_session(session_id, spec.id)

    # Assemble the full message history: system + persisted + new user turn.
    persisted = load_messages(session_id)
    messages: list[dict[str, Any]] = [{"role": "system", "content": spec.system_prompt}]
    if persisted and persisted[0].get("role") == "system":
        # Don't duplicate the system prompt if it's already there.
        messages = [persisted[0]] + persisted[1:]
    else:
        messages.extend(persisted)
    messages.append({"role": "user", "content": req.message})

    save_message(session_id, "user", req.message)
    start_run(run_id, session_id, req.message)
    record("run.started", session_id=session_id, run_id=run_id, agent=spec.id)

    def sse() -> Iterator[dict[str, Any]]:
        # First event: the IDs so the client can correlate.
        yield {"event": "session", "data": json.dumps({"session_id": session_id, "run_id": run_id})}

        prompt_tokens = completion_tokens = total_tokens = 0
        cost_usd = 0.0
        last_usage: dict[str, Any] | None = None

        try:
            for evt in run_turn(session_id=session_id, messages=messages, tools=spec.tools):
                payload = evt.data
                # Track final cumulative numbers.
                if evt.type == "usage":
                    last_usage = payload.get("cumulative") or {}
                    prompt_tokens = last_usage.get("prompt_tokens", prompt_tokens)
                    completion_tokens = last_usage.get("completion_tokens", completion_tokens)
                    total_tokens = last_usage.get("total_tokens", total_tokens)
                    cost_usd = last_usage.get("cost_usd", cost_usd)

                save_event(evt.type, payload, session_id=session_id, run_id=run_id)
                record(f"agent.{evt.type}", session_id=session_id, run_id=run_id)
                yield {"event": evt.type, "data": json.dumps(payload)}

            # Persist the final assistant message(s) so the next turn
            # sees them. We replay from `messages` starting at the
            # first appended assistant entry.
            # We know the history built above ended with the user msg,
            # so anything past that index is new.
            user_idx = next(
                i for i in range(len(messages) - 1, -1, -1)
                if messages[i].get("role") == "user"
            )
            for m in messages[user_idx + 1:]:
                save_message(
                    session_id,
                    role=m["role"],
                    content=m.get("content"),
                    tool_call_id=m.get("tool_call_id"),
                    tool_calls=m.get("tool_calls"),
                )

            finish_run(run_id, prompt_tokens, completion_tokens, total_tokens, cost_usd)
            yield {
                "event": "final",
                "data": json.dumps({
                    "run_id": run_id,
                    "session_id": session_id,
                    "budget": budget_get(session_id),
                }),
            }
        except Exception as exc:
            save_event("error", {"message": str(exc)}, session_id=session_id, run_id=run_id)
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(sse())
