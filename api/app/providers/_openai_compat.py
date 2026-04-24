"""Shared implementation for providers that speak the OpenAI
chat-completions API — Azure OpenAI and OpenAI proper, plus any
OpenAI-compatible gateway.

The two concrete adapters (azure.py, openai.py) are thin
factories: they construct the right SDK client and hand it to
this class. Everything below this line is format translation.

Anthropic does NOT use this file — its wire format is different
enough that it gets its own adapter in anthropic.py.
"""

from __future__ import annotations

from typing import Any, Iterator

from .base import Provider, ProviderEvent, TextDelta, ToolCallStart, ToolArgsDelta, Usage


class OpenAICompatProvider(Provider):
    """Wraps any openai-sdk-compatible client (AzureOpenAI or OpenAI)."""

    def __init__(self, *, client: Any, model: str, name: str) -> None:
        self._client = client
        self.model = model
        self.name = name

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float = 0.2,
    ) -> Iterator[ProviderEvent]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        stream = self._client.chat.completions.create(**kwargs)

        # Tool-call ids only arrive on the first chunk of each call,
        # so we map the openai-sdk `index` to `id` for the lifetime
        # of the stream and use it to attribute argument deltas.
        id_by_index: dict[int, str] = {}

        for chunk in stream:
            # Usage only arrives on the final chunk when we pass
            # stream_options.include_usage=True.
            if getattr(chunk, "usage", None):
                yield Usage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                )

            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            if delta.content:
                yield TextDelta(content=delta.content)

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    # First chunk for this tool call: has id + name.
                    if tc.id:
                        id_by_index[tc.index] = tc.id
                        name = tc.function.name if tc.function else ""
                        yield ToolCallStart(id=tc.id, name=name or "")
                    # Every chunk may carry partial JSON arguments.
                    if tc.function and tc.function.arguments:
                        tid = id_by_index.get(tc.index)
                        if tid:
                            yield ToolArgsDelta(id=tid, delta=tc.function.arguments)

    def complete_json(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> str:
        # We pass response_format={type: json_object} and let the
        # caller validate. Not using json_schema here because
        # support varies across Azure API versions; json_object is
        # universal and we tolerate the minor validation tax.
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or "{}"
