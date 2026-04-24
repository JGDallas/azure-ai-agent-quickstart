"""web_search tool — Tavily.

Only registered at turn time when:
  1. TAVILY_API_KEY is set in .env (settings.flags.web_search), AND
  2. the chat request opts in via enable_web_search=true.

The tool shape is intentionally similar to search_docs so the
model uses them interchangeably — pick whichever makes sense
for the question.
"""

from __future__ import annotations

from typing import Any

import httpx

from ..agent import Tool
from ..config import settings


TAVILY_URL = "https://api.tavily.com/search"

PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "What to search the public web for. Natural language.",
        },
        "top_k": {
            "type": "integer",
            "description": "How many results to return. Default 5, max 10.",
            "default": 5,
        },
    },
    "required": ["query"],
}


def _run(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"results": [], "error": "Empty query."}

    raw_top_k = args.get("top_k")
    try:
        top_k = int(raw_top_k) if raw_top_k is not None else 5
    except (TypeError, ValueError):
        top_k = 5
    top_k = max(1, min(10, top_k))

    if not settings.tavily_api_key:
        return {
            "results": [],
            "error": (
                "TAVILY_API_KEY is not set on the server. "
                "Add it to .env to enable web search."
            ),
        }

    # Use Bearer header auth (Tavily's current documented auth
    # method) plus an explicit User-Agent so we don't trip CDN
    # filters. `api_key` in the body is still accepted as a
    # fallback by the older endpoint behavior but the header
    # version is what the docs show now.
    try:
        resp = httpx.post(
            TAVILY_URL,
            headers={
                "Authorization": f"Bearer {settings.tavily_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "azure-ai-agent-quickstart/0.1 (+https://github.com/jgdallas/azure-ai-agent-quickstart)",
            },
            json={
                "query": query,
                "max_results": top_k,
                "include_answer": True,
                "search_depth": "basic",
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPStatusError as exc:
        return {"error": f"Tavily HTTP {exc.response.status_code}: {exc.response.text[:300]}"}
    except Exception as exc:
        return {"error": f"Tavily call failed: {type(exc).__name__}: {exc}"}

    return {
        "backend": "tavily",
        "answer": body.get("answer"),
        "results": [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": (r.get("content") or "")[:500],
                "score": r.get("score"),
            }
            for r in body.get("results", [])
        ],
    }


web_search = Tool(
    name="web_search",
    description=(
        "Search the public web for up-to-date information. Use for "
        "current events, recent releases, or topics outside the "
        "local document corpus. Returns a Tavily-generated summary "
        "plus a list of results (title, URL, snippet). Always cite "
        "URLs when you use them."
    ),
    parameters=PARAMETERS,
    fn=_run,
)
