"""Structured in-process telemetry.

Every agent event is appended to a bounded ring buffer and
mirrored into SQLite via persistence.py. If Application Insights
is configured, we also initialize the azure-monitor-opentelemetry
distro so cloud-side traces light up automatically.
"""

from __future__ import annotations

import logging
import time
from collections import deque
from threading import Lock
from typing import Any, Deque

from .config import settings

_RING_MAX = 1000
_ring: Deque[dict[str, Any]] = deque(maxlen=_RING_MAX)
_lock = Lock()
_log = logging.getLogger("quickstart.telemetry")


def init_app_insights() -> None:
    """Best-effort. Never fail startup on telemetry config."""
    if not settings.flags.get("app_insights"):
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=settings.app_insights_conn)
        _log.info("Application Insights telemetry enabled.")
    except Exception as exc:
        _log.warning("Failed to initialize Application Insights: %s", exc)


def record(event_type: str, **fields: Any) -> dict[str, Any]:
    evt = {"ts": time.time(), "type": event_type, **fields}
    with _lock:
        _ring.append(evt)
    _log.debug("telemetry %s %s", event_type, fields)
    return evt


def recent(limit: int = 200, session_id: str | None = None) -> list[dict[str, Any]]:
    with _lock:
        events = list(_ring)
    if session_id:
        events = [e for e in events if e.get("session_id") == session_id]
    return events[-limit:]
