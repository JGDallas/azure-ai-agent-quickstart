"""Azure OpenAI provider — a factory over _openai_compat."""

from __future__ import annotations

from openai import AzureOpenAI

from ..config import settings
from ._openai_compat import OpenAICompatProvider


def make() -> OpenAICompatProvider:
    client = AzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
    return OpenAICompatProvider(
        client=client,
        model=settings.azure_openai_deployment,
        name="azure",
    )
