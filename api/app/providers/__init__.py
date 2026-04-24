"""Provider registry + dispatcher.

The active provider is chosen by the LLM_PROVIDER env var and
resolved once per process. If you change it, restart the api
container. list_configured() reports which providers have
complete credentials so the UI can show a picker later on.
"""

from __future__ import annotations

from ..config import settings
from ._instrumented import InstrumentedProvider
from .base import Provider, ProviderEvent, TextDelta, ToolArgsDelta, ToolCallStart, Usage

__all__ = [
    "Provider",
    "ProviderEvent",
    "TextDelta",
    "ToolCallStart",
    "ToolArgsDelta",
    "Usage",
    "get_provider",
    "list_configured",
]


_cache: dict[str, Provider] = {}


def _build(name: str) -> Provider:
    if name == "azure":
        from . import azure
        return azure.make()
    if name == "openai":
        from . import openai
        return openai.make()
    if name == "anthropic":
        # Wired in Phase 2. Keep the slot so list_configured() can
        # already advertise availability if ANTHROPIC_API_KEY is set.
        raise RuntimeError(
            "Anthropic provider is not yet implemented on this branch. "
            "Switch LLM_PROVIDER to 'azure' or 'openai' for now."
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {name!r}")


def get_provider(name: str | None = None) -> Provider:
    active = name or settings.llm_provider
    if not settings.flags.get(f"provider_{active}"):
        raise RuntimeError(
            f"Provider '{active}' is selected but not configured. "
            f"Set its env vars in .env or change LLM_PROVIDER."
        )
    if active not in _cache:
        _cache[active] = InstrumentedProvider(_build(active))
    return _cache[active]


def list_configured() -> list[str]:
    out: list[str] = []
    for name in ("azure", "openai", "anthropic"):
        if settings.flags.get(f"provider_{name}"):
            out.append(name)
    return out
