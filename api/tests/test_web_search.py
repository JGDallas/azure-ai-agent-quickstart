"""Tests for the web_search tool.

httpx is patched so we never hit the real Tavily API.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.tools import web as web_tool


def _fake_response(json_body: dict[str, Any], status: int = 200) -> SimpleNamespace:
    def raise_for_status():
        if status >= 400:
            import httpx
            raise httpx.HTTPStatusError("boom", request=None, response=SimpleNamespace(status_code=status, text=""))
    return SimpleNamespace(json=lambda: json_body, raise_for_status=raise_for_status, status_code=status)


def test_returns_clean_error_when_key_missing() -> None:
    with patch.object(web_tool.settings, "tavily_api_key", ""):
        out = web_tool._run({"query": "anything"})
    assert "TAVILY_API_KEY" in out["error"]
    assert out["results"] == []


def test_returns_empty_for_empty_query() -> None:
    with patch.object(web_tool.settings, "tavily_api_key", "t-test"):
        out = web_tool._run({"query": "   "})
    assert out["error"] == "Empty query."


def test_successful_call_shapes_results() -> None:
    body = {
        "answer": "the answer",
        "results": [
            {"title": "Doc 1", "url": "https://x/1", "content": "a" * 600, "score": 0.9},
            {"title": "Doc 2", "url": "https://x/2", "content": "b", "score": 0.5},
        ],
    }
    with patch.object(web_tool.settings, "tavily_api_key", "t-test"):
        with patch("app.tools.web.httpx.post", return_value=_fake_response(body)) as post:
            out = web_tool._run({"query": "azure foundry", "top_k": 2})

    # Request went to Tavily with the expected body shape.
    call_kwargs = post.call_args.kwargs
    assert call_kwargs["json"]["api_key"] == "t-test"
    assert call_kwargs["json"]["query"] == "azure foundry"
    assert call_kwargs["json"]["max_results"] == 2

    # Response was normalized.
    assert out["backend"] == "tavily"
    assert out["answer"] == "the answer"
    assert len(out["results"]) == 2
    assert out["results"][0]["title"] == "Doc 1"
    assert out["results"][0]["url"] == "https://x/1"
    assert len(out["results"][0]["snippet"]) == 500  # truncated to 500 chars


def test_top_k_is_clamped_to_1_10() -> None:
    with patch.object(web_tool.settings, "tavily_api_key", "t-test"):
        with patch("app.tools.web.httpx.post", return_value=_fake_response({"results": []})) as post:
            web_tool._run({"query": "x", "top_k": 99})
            assert post.call_args.kwargs["json"]["max_results"] == 10
            web_tool._run({"query": "x", "top_k": 0})
            assert post.call_args.kwargs["json"]["max_results"] == 1


def test_http_error_surfaces_a_clean_message() -> None:
    with patch.object(web_tool.settings, "tavily_api_key", "t-test"):
        with patch("app.tools.web.httpx.post", side_effect=RuntimeError("connection refused")):
            out = web_tool._run({"query": "x"})
    assert "Tavily call failed" in out["error"]
    assert "connection refused" in out["error"]
