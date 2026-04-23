"""search_docs tool.

Uses Azure AI Search when all three AZURE_AI_SEARCH_* vars are
set; otherwise falls back to a local SQLite FTS5 index populated
from api/sample_docs/*.md. Either way the tool signature is the
same — the agent doesn't care which backend served it.
"""

from __future__ import annotations

from typing import Any

from ..agent import Tool
from ..config import settings
from ..persistence import connect


PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query. Use natural language.",
        },
        "top_k": {
            "type": "integer",
            "description": "How many results to return. Default 4.",
            "default": 4,
        },
    },
    "required": ["query"],
}


def _search_azure(query: str, top_k: int) -> list[dict[str, Any]]:
    from azure.core.credentials import AzureKeyCredential
    from azure.search.documents import SearchClient

    client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=AzureKeyCredential(settings.azure_search_key),
    )
    results = client.search(search_text=query, top=top_k)
    out = []
    for r in results:
        out.append({
            "title": r.get("title") or r.get("id") or "",
            "snippet": (r.get("content") or r.get("body") or "")[:500],
            "source": "azure-ai-search",
            "path": r.get("metadata_storage_name") or r.get("path") or "",
            "score": r.get("@search.score"),
        })
    return out


def _search_local(query: str, top_k: int) -> list[dict[str, Any]]:
    # Sanitize to alphanumerics + whitespace so FTS5 can tokenize
    # the query without us having to worry about quoting rules.
    # Each resulting token is quoted individually so that hyphens
    # and other punctuation inside a token don't blow up FTS.
    import re
    tokens = [t for t in re.split(r"[^A-Za-z0-9]+", query) if t]
    if not tokens:
        return []
    fts_query = " OR ".join(f'"{t}"' for t in tokens)
    with connect() as c:
        rows = c.execute(
            """
            SELECT path, title, snippet(docs, 2, '[', ']', ' ... ', 16) AS snippet
              FROM docs
             WHERE docs MATCH ?
             ORDER BY rank
             LIMIT ?
            """,
            (fts_query, top_k),
        ).fetchall()
    return [
        {
            "title": r["title"],
            "snippet": r["snippet"],
            "source": "sqlite-fts5",
            "path": r["path"],
        }
        for r in rows
    ]


def _run(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    top_k = int(args.get("top_k") or 4)
    if not query:
        return {"results": [], "backend": "none", "error": "Empty query."}

    if settings.flags.get("azure_ai_search"):
        try:
            results = _search_azure(query, top_k)
            return {"results": results, "backend": "azure-ai-search"}
        except Exception as exc:
            # Fall back to local index if the Azure call fails.
            local = _search_local(query, top_k)
            return {
                "results": local,
                "backend": "sqlite-fts5",
                "warning": f"Azure Search failed, falling back to local FTS5: {exc}",
            }

    return {"results": _search_local(query, top_k), "backend": "sqlite-fts5"}


search_docs = Tool(
    name="search_docs",
    description=(
        "Search the knowledge base for documents relevant to the query. "
        "Returns a list of results with title, snippet, and source path."
    ),
    parameters=PARAMETERS,
    fn=_run,
)
