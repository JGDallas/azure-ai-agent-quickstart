"""SQLite persistence.

Two databases live under /data:

  * app.db   — sessions, runs, messages, events
  * demo.db  — seeded employees/tickets/revenue tables exposed to
               the Ops Helper via the run_sql tool

Both are created on API startup if missing.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from .config import settings


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_message TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    tool_call_id TEXT,
    tool_calls_json TEXT,
    ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    session_id TEXT,
    type TEXT NOT NULL,
    payload_json TEXT,
    ts REAL NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5(
    path UNINDEXED,
    title,
    body,
    tokenize = 'porter'
);
"""


DEMO_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    name TEXT,
    team TEXT,
    role TEXT,
    location TEXT,
    start_date TEXT
);
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY,
    title TEXT,
    status TEXT,
    priority TEXT,
    assignee_id INTEGER,
    opened_at TEXT,
    closed_at TEXT
);
CREATE TABLE IF NOT EXISTS revenue (
    id INTEGER PRIMARY KEY,
    month TEXT,
    product TEXT,
    amount_usd REAL
);
"""


@contextmanager
def connect(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect() as c:
        c.executescript(SCHEMA)
    _init_demo()
    _index_sample_docs()


def _init_demo() -> None:
    fresh = not os.path.exists(settings.demo_db_path)
    with connect(settings.demo_db_path) as c:
        c.executescript(DEMO_SCHEMA)
        if fresh:
            c.executemany(
                "INSERT INTO employees(id, name, team, role, location, start_date) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (1, "Ada Lovelace", "Platform", "Staff Engineer", "London", "2022-03-14"),
                    (2, "Grace Hopper", "Data", "Engineering Manager", "Philadelphia", "2021-07-01"),
                    (3, "Alan Turing", "ML", "Principal Researcher", "Manchester", "2020-06-23"),
                    (4, "Katherine Johnson", "Platform", "Senior Engineer", "Hampton", "2023-01-09"),
                    (5, "Hedy Lamarr", "Security", "Security Engineer", "Vienna", "2024-02-18"),
                    (6, "Linus Torvalds", "Platform", "Senior Engineer", "Portland", "2023-11-04"),
                ],
            )
            c.executemany(
                "INSERT INTO tickets(id, title, status, priority, assignee_id, opened_at, closed_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (1, "API 500s on /chat", "open", "P1", 1, "2026-04-18", None),
                    (2, "Index rebuild slow", "open", "P2", 2, "2026-04-19", None),
                    (3, "Login flakiness", "closed", "P2", 5, "2026-04-10", "2026-04-15"),
                    (4, "Docs search 404", "open", "P3", 4, "2026-04-20", None),
                    (5, "GPU node evict loop", "closed", "P1", 3, "2026-04-05", "2026-04-07"),
                    (6, "Auth rate limit low", "open", "P3", 5, "2026-04-21", None),
                ],
            )
            c.executemany(
                "INSERT INTO revenue(id, month, product, amount_usd) VALUES (?, ?, ?, ?)",
                [
                    (1, "2026-01", "Platform", 142000.0),
                    (2, "2026-01", "AI Add-on", 58000.0),
                    (3, "2026-02", "Platform", 151500.0),
                    (4, "2026-02", "AI Add-on", 71200.0),
                    (5, "2026-03", "Platform", 163900.0),
                    (6, "2026-03", "AI Add-on", 84300.0),
                ],
            )


def _index_sample_docs() -> None:
    """Populate FTS5 with markdown from sample_docs/, idempotent."""
    if not os.path.isdir(settings.sample_docs_dir):
        return
    with connect() as c:
        already = c.execute("SELECT COUNT(*) AS n FROM docs").fetchone()["n"]
        if already:
            return
        for name in sorted(os.listdir(settings.sample_docs_dir)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(settings.sample_docs_dir, name)
            with open(path, encoding="utf-8") as fh:
                body = fh.read()
            title = name.removesuffix(".md").replace("-", " ").title()
            first_line = body.splitlines()[0] if body else ""
            if first_line.startswith("#"):
                title = first_line.lstrip("# ").strip() or title
            c.execute(
                "INSERT INTO docs(path, title, body) VALUES (?, ?, ?)",
                (name, title, body),
            )


# ---------- Sessions / runs / messages / events ----------

def create_session(session_id: str, agent: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT OR IGNORE INTO sessions(id, agent, created_at) VALUES (?, ?, ?)",
            (session_id, agent, time.time()),
        )


def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            "SELECT id, agent, created_at FROM sessions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def start_run(run_id: str, session_id: str, user_message: str) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO runs(id, session_id, user_message, started_at) VALUES (?, ?, ?, ?)",
            (run_id, session_id, user_message, time.time()),
        )


def finish_run(
    run_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float,
) -> None:
    with connect() as c:
        c.execute(
            """
            UPDATE runs
               SET finished_at = ?,
                   prompt_tokens = ?,
                   completion_tokens = ?,
                   total_tokens = ?,
                   cost_usd = ?
             WHERE id = ?
            """,
            (time.time(), prompt_tokens, completion_tokens, total_tokens, cost_usd, run_id),
        )


def list_runs(session_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    with connect() as c:
        if session_id:
            rows = c.execute(
                "SELECT * FROM runs WHERE session_id = ? ORDER BY started_at DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def save_message(
    session_id: str,
    role: str,
    content: str | None,
    tool_call_id: str | None = None,
    tool_calls: Any = None,
) -> None:
    with connect() as c:
        c.execute(
            """
            INSERT INTO messages(session_id, role, content, tool_call_id, tool_calls_json, ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                role,
                content,
                tool_call_id,
                json.dumps(tool_calls) if tool_calls else None,
                time.time(),
            ),
        )


def load_messages(session_id: str) -> list[dict[str, Any]]:
    with connect() as c:
        rows = c.execute(
            "SELECT role, content, tool_call_id, tool_calls_json FROM messages "
            "WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    out = []
    for r in rows:
        msg: dict[str, Any] = {"role": r["role"]}
        if r["content"] is not None:
            msg["content"] = r["content"]
        if r["tool_call_id"]:
            msg["tool_call_id"] = r["tool_call_id"]
        if r["tool_calls_json"]:
            msg["tool_calls"] = json.loads(r["tool_calls_json"])
        out.append(msg)
    return out


def save_event(
    event_type: str,
    payload: Any,
    session_id: str | None = None,
    run_id: str | None = None,
) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO events(run_id, session_id, type, payload_json, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, session_id, event_type, json.dumps(payload, default=str), time.time()),
        )


def list_events(session_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    with connect() as c:
        if session_id:
            rows = c.execute(
                "SELECT run_id, session_id, type, payload_json, ts FROM events "
                "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT run_id, session_id, type, payload_json, ts FROM events "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out = []
    for r in rows:
        out.append({
            "run_id": r["run_id"],
            "session_id": r["session_id"],
            "type": r["type"],
            "payload": json.loads(r["payload_json"]) if r["payload_json"] else None,
            "ts": r["ts"],
        })
    return list(reversed(out))
