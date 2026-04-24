"""Per-session token + USD budget tracking.

State is held in memory (process-local) and mirrored to SQLite
via persistence.py so it survives a restart. Pricing is keyed by
(provider, model) so switching providers — or running different
models through the same provider — always uses the right rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from .config import active_model, settings


class BudgetExceeded(Exception):
    pass


@dataclass
class SessionBudget:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


_state: dict[str, SessionBudget] = {}
_lock = Lock()


def _price(provider: str, model: str) -> dict[str, float]:
    """Look up a price entry; degrade gracefully to 0/0 if unknown."""
    per_provider = settings.price_table.get(provider) or {}
    entry = per_provider.get(model)
    if entry:
        return entry
    # Fall back to the first model we know for this provider,
    # then to any first entry overall. Better than blowing up.
    if per_provider:
        return next(iter(per_provider.values()))
    for models in settings.price_table.values():
        if models:
            return next(iter(models.values()))
    return {"input": 0.0, "output": 0.0}


def _ensure(session_id: str) -> SessionBudget:
    with _lock:
        return _state.setdefault(session_id, SessionBudget())


def remaining(session_id: str) -> dict[str, float]:
    s = _ensure(session_id)
    return {
        "tokens": max(0, settings.session_token_budget - s.total_tokens),
        "usd": max(0.0, settings.session_usd_budget - s.cost_usd),
    }


def get(session_id: str) -> dict[str, Any]:
    s = _ensure(session_id)
    rem = remaining(session_id)
    return {
        "prompt_tokens": s.prompt_tokens,
        "completion_tokens": s.completion_tokens,
        "total_tokens": s.total_tokens,
        "cost_usd": round(s.cost_usd, 6),
        "remaining_tokens": rem["tokens"],
        "remaining_usd": round(rem["usd"], 6),
        "limits": {
            "token_budget": settings.session_token_budget,
            "usd_budget": settings.session_usd_budget,
        },
        "provider": settings.llm_provider,
        "model": active_model(settings),
    }


def reset(session_id: str) -> None:
    with _lock:
        _state[session_id] = SessionBudget()


def apply_usage(
    session_id: str,
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> dict[str, Any]:
    """Add a single API call's usage to the session totals.

    Returns a usage payload suitable for the 'usage' SSE event.
    Raises BudgetExceeded if the session cap is blown. The caller
    decides whether to stop mid-turn or let the event through.
    """
    price = _price(provider, model)
    cost = (prompt_tokens * price["input"] + completion_tokens * price["output"]) / 1_000_000.0

    with _lock:
        s = _state.setdefault(session_id, SessionBudget())
        s.prompt_tokens += prompt_tokens
        s.completion_tokens += completion_tokens
        s.total_tokens = s.prompt_tokens + s.completion_tokens
        s.cost_usd += cost

    over_tokens = s.total_tokens > settings.session_token_budget
    over_usd = s.cost_usd > settings.session_usd_budget

    payload = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(cost, 6),
        "provider": provider,
        "model": model,
        "cumulative": get(session_id),
    }

    if over_tokens or over_usd:
        raise BudgetExceeded(
            f"Session budget exceeded (tokens={s.total_tokens}/"
            f"{settings.session_token_budget}, "
            f"usd={s.cost_usd:.4f}/{settings.session_usd_budget})"
        )
    return payload
