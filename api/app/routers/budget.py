from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..budget import get, reset

router = APIRouter()


@router.get("/budget/{session_id}")
def read_budget(session_id: str) -> dict[str, Any]:
    return get(session_id)


@router.post("/budget/{session_id}/reset")
def reset_budget(session_id: str) -> dict[str, Any]:
    reset(session_id)
    return {"session_id": session_id, "status": "reset", "budget": get(session_id)}
