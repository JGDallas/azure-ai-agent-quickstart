from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..persistence import list_runs, list_sessions

router = APIRouter()


@router.get("/sessions")
def sessions() -> list[dict[str, Any]]:
    return list_sessions()


@router.get("/runs")
def runs(session_id: str | None = Query(default=None)) -> list[dict[str, Any]]:
    return list_runs(session_id=session_id)
