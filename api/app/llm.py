"""Thin wrapper around the Azure OpenAI chat completions API.

We deliberately use the raw OpenAI SDK (pointed at Azure) instead
of a framework like LangChain / Semantic Kernel / Foundry Agent
Service so the agent loop in `agent.py` stays legible. If you
want to swap to Foundry Agent Service later, replace the calls
in `agent.py` — this wrapper is the only other seam you need to
touch.
"""

from __future__ import annotations

from typing import Any, Iterable

from openai import AzureOpenAI

from .config import settings


_client: AzureOpenAI | None = None


def client() -> AzureOpenAI:
    """Singleton AzureOpenAI client. Lazy so tests can patch config."""
    global _client
    if _client is None:
        _client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    return _client


def chat_stream(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.2,
) -> Iterable[Any]:
    """Stream chunks from Azure OpenAI chat completions.

    Usage is requested via `stream_options` so the final chunk
    carries prompt/completion token counts — we need these for
    budget accounting.
    """
    kwargs: dict[str, Any] = {
        "model": settings.azure_openai_deployment,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client().chat.completions.create(**kwargs)


def chat_once(
    messages: list[dict[str, Any]],
    temperature: float = 0.0,
    response_format: dict[str, Any] | None = None,
) -> Any:
    """Single non-streaming completion, used by the evaluator."""
    kwargs: dict[str, Any] = {
        "model": settings.azure_openai_deployment,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format
    return client().chat.completions.create(**kwargs)
