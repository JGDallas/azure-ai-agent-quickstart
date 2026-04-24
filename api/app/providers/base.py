"""Provider-agnostic event model + the Provider protocol.

The agent loop speaks only in these events. Every concrete
provider (Azure, OpenAI, Anthropic, ...) translates its native
SDK into this same small vocabulary. That's the whole point of
the abstraction — agent.py has no idea which vendor produced
the stream.

Four events is all we need for V1:

  * TextDelta        — more of the assistant's prose arrived.
  * ToolCallStart    — the model wants to call tool <name>.
  * ToolArgsDelta    — more of that tool's JSON arguments arrived.
  * Usage            — token accounting for a single API call.

If a future provider adds concepts we don't model (e.g. audio,
images), they get layered on top — existing events stay stable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Protocol, Union


@dataclass
class TextDelta:
    content: str


@dataclass
class ToolCallStart:
    id: str
    name: str


@dataclass
class ToolArgsDelta:
    id: str
    delta: str  # partial JSON fragment; caller concatenates


@dataclass
class Usage:
    prompt_tokens: int
    completion_tokens: int


ProviderEvent = Union[TextDelta, ToolCallStart, ToolArgsDelta, Usage]


class Provider(Protocol):
    """One concrete LLM vendor. See providers/azure.py for the
    simplest implementation; providers/anthropic.py is where the
    real translation work lives."""

    name: str   # "azure" | "openai" | "anthropic"
    model: str  # deployment name (Azure) or model id (OpenAI/Anthropic)

    def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        temperature: float = 0.2,
    ) -> Iterator[ProviderEvent]:
        ...

    def complete_json(
        self,
        messages: list[dict[str, Any]],
        schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> str:
        ...
