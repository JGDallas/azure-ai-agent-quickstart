from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from ..persistence import list_events
from ..telemetry import recent

router = APIRouter()


@router.get("/traces")
def traces(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
) -> dict[str, Any]:
    return {
        "memory": recent(limit=limit, session_id=session_id),
        "persisted": list_events(session_id=session_id, limit=limit),
    }
