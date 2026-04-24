"""GET /providers — report which providers are configured.

Used by /healthz and (in Phase 5) by the UI provider picker.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ..config import active_model, settings
from ..providers import list_configured

router = APIRouter()


@router.get("/providers")
def providers() -> dict[str, Any]:
    return {
        "active": settings.llm_provider,
        "active_model": active_model(settings),
        "configured": list_configured(),
        "available": [
            {
                "id": "azure",
                "configured": settings.flags.get("provider_azure", False),
                "model": settings.azure_openai_deployment,
            },
            {
                "id": "openai",
                "configured": settings.flags.get("provider_openai", False),
                "model": settings.openai_model,
            },
            {
                "id": "anthropic",
                "configured": settings.flags.get("provider_anthropic", False),
                "model": settings.anthropic_model,
            },
        ],
    }
