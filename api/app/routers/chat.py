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
from ..config import settings
from ..persistence import (
    create_session,
    finish_run,
    load_messages,
    save_event,
    save_message,
    start_run,
)
from ..providers import get_provider
from ..telemetry import record

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    agent: str
    message: str
    provider: str | None = None  # override for future UI picker; None uses .env
    enable_web_search: bool = False  # ignored unless server has TAVILY_API_KEY


@router.get("/agents")
def agents() -> list[dict[str, Any]]:
    return list_agents()


@router.post("/chat")
def chat(req: ChatRequest) -> EventSourceResponse:
    spec = get_agent(req.agent)
    provider = get_provider(req.provider)

    session_id = req.session_id or f"s_{uuid.uuid4().hex[:12]}"
    run_id = f"r_{uuid.uuid4().hex[:12]}"
    create_session(session_id, spec.id)

    # Assemble the tool bundle for this turn. Research Assistant
    # gets an extra web_search tool when the user toggled it ON
    # in the UI and the server is configured (TAVILY_API_KEY set).
    tools = list(spec.tools)
    system_prompt = spec.system_prompt
    web_search_on = (
        req.enable_web_search
        and settings.flags.get("web_search", False)
        and spec.id == "research"
    )
    if web_search_on:
        from ..tools.web import web_search
        tools.append(web_search)
        system_prompt += (
            "\n\nYou also have a web_search tool backed by Tavily. "
            "Use it for questions about current events, recent "
            "releases, or topics not in the local corpus. Always "
            "cite the URLs you used."
        )

    # Assemble the full message history: system + persisted + new user turn.
    persisted = load_messages(session_id)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if persisted and persisted[0].get("role") == "system":
        messages = [persisted[0]] + persisted[1:]
    else:
        messages.extend(persisted)
    messages.append({"role": "user", "content": req.message})

    save_message(session_id, "user", req.message)
    start_run(run_id, session_id, req.message)
    record("run.started", session_id=session_id, run_id=run_id, agent=spec.id, provider=provider.name, model=provider.model)

    def sse() -> Iterator[dict[str, Any]]:
        yield {
            "event": "session",
            "data": json.dumps({
                "session_id": session_id,
                "run_id": run_id,
                "provider": provider.name,
                "model": provider.model,
            }),
        }

        prompt_tokens = completion_tokens = total_tokens = 0
        cost_usd = 0.0

        try:
            for evt in run_turn(
                session_id=session_id,
                run_id=run_id,
                messages=messages,
                tools=tools,
                provider=provider,
            ):
                payload = evt.data
                if evt.type == "usage":
                    cumulative = payload.get("cumulative") or {}
                    prompt_tokens = cumulative.get("prompt_tokens", prompt_tokens)
                    completion_tokens = cumulative.get("completion_tokens", completion_tokens)
                    total_tokens = cumulative.get("total_tokens", total_tokens)
                    cost_usd = cumulative.get("cost_usd", cost_usd)

                save_event(evt.type, payload, session_id=session_id, run_id=run_id)
                record(f"agent.{evt.type}", session_id=session_id, run_id=run_id)
                yield {"event": evt.type, "data": json.dumps(payload)}

            # Persist any new assistant/tool messages accumulated during the turn.
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
