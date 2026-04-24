from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..evaluation import evaluate
from ..persistence import load_messages
from ..providers import get_provider

router = APIRouter()


class EvalRequest(BaseModel):
    session_id: str | None = None
    user_message: str | None = None
    assistant_message: str | None = None
    retrieved_context: list[str] | None = None
    provider: str | None = None  # override; None uses .env default


@router.post("/evaluate")
def run_eval(req: EvalRequest) -> dict[str, Any]:
    user_msg = req.user_message
    assistant_msg = req.assistant_message

    if req.session_id and (not user_msg or not assistant_msg):
        history = load_messages(req.session_id)
        last_user = last_assistant = None
        for m in reversed(history):
            if m.get("role") == "assistant" and m.get("content") and not last_assistant:
                last_assistant = m["content"]
            elif m.get("role") == "user" and m.get("content") and last_assistant and not last_user:
                last_user = m["content"]
                break
        user_msg = user_msg or last_user
        assistant_msg = assistant_msg or last_assistant

    if not user_msg or not assistant_msg:
        raise HTTPException(
            status_code=400,
            detail="Need either (user_message + assistant_message) or a session_id with prior turns.",
        )

    return evaluate(get_provider(req.provider), user_msg, assistant_msg, req.retrieved_context)
