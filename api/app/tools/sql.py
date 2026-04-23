"""run_sql tool.

Runs a read-only query against the seeded demo.db. We enforce
read-only by opening the connection with `uri=True&mode=ro` and
by rejecting queries that don't start with SELECT/WITH.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from ..agent import Tool
from ..config import settings


PARAMETERS = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": (
                "A SQL SELECT statement. Tables available: employees"
                "(id, name, team, role, location, start_date), "
                "tickets(id, title, status, priority, assignee_id, opened_at, closed_at), "
                "revenue(id, month, product, amount_usd)."
            ),
        },
        "limit": {
            "type": "integer",
            "description": "Row cap. Default 50, max 500.",
            "default": 50,
        },
    },
    "required": ["query"],
}


ALLOWED_PREFIX = ("select", "with")


def _run(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "")).strip().rstrip(";")
    if not query:
        return {"error": "Empty query."}
    if not query.lower().lstrip("(").startswith(ALLOWED_PREFIX):
        return {"error": "Only SELECT / WITH queries are allowed."}

    try:
        limit = int(args.get("limit") or 50)
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(500, limit))

    uri = f"file:{settings.demo_db_path}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(query)
        rows = cur.fetchmany(limit)
        columns = [d[0] for d in cur.description] if cur.description else []
        data = [dict(r) for r in rows]
        conn.close()
    except sqlite3.Error as exc:
        return {"error": f"SQL error: {exc}"}

    return {"columns": columns, "rows": data, "row_count": len(data), "truncated": len(data) == limit}


run_sql = Tool(
    name="run_sql",
    description=(
        "Execute a read-only SELECT against the demo database. "
        "Return columns and rows for the query."
    ),
    parameters=PARAMETERS,
    fn=_run,
)
