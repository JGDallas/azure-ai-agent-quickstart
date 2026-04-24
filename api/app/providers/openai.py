"""OpenAI provider — same SDK as Azure, different constructor."""

from __future__ import annotations

from openai import OpenAI

from ..config import settings
from ._openai_compat import OpenAICompatProvider


def make() -> OpenAICompatProvider:
    client = OpenAI(api_key=settings.openai_api_key)
    return OpenAICompatProvider(
        client=client,
        model=settings.openai_model,
        name="openai",
    )
