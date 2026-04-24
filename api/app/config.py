"""Runtime configuration.

Reads environment variables once at import and exposes a typed
`settings` object. Also reports which providers and optional
integrations are active so the UI can render clear banners
instead of crashing on missing keys.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


def _env(key: str, default: str = "") -> str:
    value = os.environ.get(key, default)
    return value.strip() if value else ""


def _placeholder(value: str) -> bool:
    """Treat the obvious placeholder shapes as empty."""
    if not value:
        return True
    lowered = value.lower()
    return lowered in {"changeme", "your-key-here", "todo", "xxx"}


# Default price table, per 1M tokens. Overridable via PRICE_TABLE_JSON.
# Structure is {provider: {model: {input, output}}}.
DEFAULT_PRICES: dict[str, dict[str, dict[str, float]]] = {
    "azure": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
    },
    "openai": {
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o": {"input": 2.50, "output": 10.00},
    },
    "anthropic": {
        "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
        "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "claude-opus-4-7": {"input": 15.00, "output": 75.00},
    },
}


@dataclass
class Settings:
    # Active provider selection.
    llm_provider: str  # "azure" | "openai" | "anthropic"

    # Azure OpenAI.
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str
    azure_openai_api_version: str

    # OpenAI.
    openai_api_key: str
    openai_model: str

    # Anthropic (Phase 2).
    anthropic_api_key: str
    anthropic_model: str

    # Budgets.
    session_token_budget: int
    session_usd_budget: float
    price_table: dict[str, dict[str, dict[str, float]]]

    # Optional Azure AI Search.
    azure_search_endpoint: str
    azure_search_key: str
    azure_search_index: str

    # Optional App Insights.
    app_insights_conn: str

    # Optional Tavily (web search).
    tavily_api_key: str

    # Local paths.
    db_path: str
    demo_db_path: str
    sample_docs_dir: str

    # Derived flags.
    flags: dict[str, bool] = field(default_factory=dict)


def _merge_prices(override_json: str) -> dict[str, dict[str, dict[str, float]]]:
    """Merge user-supplied PRICE_TABLE_JSON onto the defaults.

    Accepts either the nested shape {provider: {model: {...}}} or
    the legacy flat shape {model: {...}} — in the latter case we
    apply the flat table to whichever provider is active.
    """
    if not override_json.strip():
        return DEFAULT_PRICES

    try:
        parsed = json.loads(override_json)
    except json.JSONDecodeError:
        return DEFAULT_PRICES

    merged: dict[str, dict[str, dict[str, float]]] = {
        p: dict(m) for p, m in DEFAULT_PRICES.items()
    }

    if parsed and all(isinstance(v, dict) and {"input", "output"} <= set(v.keys()) for v in parsed.values()):
        # Legacy flat shape — apply to all known providers.
        for provider in merged:
            merged[provider].update(parsed)
        return merged

    # Nested provider shape.
    for provider, models in parsed.items():
        if not isinstance(models, dict):
            continue
        merged.setdefault(provider, {})
        for model, price in models.items():
            if isinstance(price, dict):
                merged[provider][model] = price
    return merged


def load_settings() -> Settings:
    provider = _env("LLM_PROVIDER", "azure").lower() or "azure"

    az_endpoint = _env("AZURE_OPENAI_ENDPOINT")
    az_key = _env("AZURE_OPENAI_API_KEY")
    az_deployment = _env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    az_version = _env("AZURE_OPENAI_API_VERSION", "2024-10-21")

    oa_key = _env("OPENAI_API_KEY")
    oa_model = _env("OPENAI_MODEL", "gpt-4o-mini")

    an_key = _env("ANTHROPIC_API_KEY")
    an_model = _env("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    try:
        token_budget = int(_env("SESSION_TOKEN_BUDGET", "200000"))
    except ValueError:
        token_budget = 200000
    try:
        usd_budget = float(_env("SESSION_USD_BUDGET", "2.00"))
    except ValueError:
        usd_budget = 2.00

    price_table = _merge_prices(_env("PRICE_TABLE_JSON"))

    search_endpoint = _env("AZURE_AI_SEARCH_ENDPOINT")
    search_key = _env("AZURE_AI_SEARCH_KEY")
    search_index = _env("AZURE_AI_SEARCH_INDEX", "quickstart-docs")

    ai_conn = _env("APPLICATIONINSIGHTS_CONNECTION_STRING")

    tavily_key = _env("TAVILY_API_KEY")

    data_dir = _env("DATA_DIR", "/data")
    os.makedirs(data_dir, exist_ok=True)

    flags = {
        "provider_azure": not _placeholder(az_endpoint) and not _placeholder(az_key),
        "provider_openai": not _placeholder(oa_key),
        "provider_anthropic": not _placeholder(an_key),
        "azure_ai_search": (
            not _placeholder(search_endpoint)
            and not _placeholder(search_key)
            and not _placeholder(search_index)
        ),
        "app_insights": not _placeholder(ai_conn),
        "web_search": not _placeholder(tavily_key),
    }

    return Settings(
        llm_provider=provider,
        azure_openai_endpoint=az_endpoint,
        azure_openai_api_key=az_key,
        azure_openai_deployment=az_deployment,
        azure_openai_api_version=az_version,
        openai_api_key=oa_key,
        openai_model=oa_model,
        anthropic_api_key=an_key,
        anthropic_model=an_model,
        session_token_budget=token_budget,
        session_usd_budget=usd_budget,
        price_table=price_table,
        azure_search_endpoint=search_endpoint,
        azure_search_key=search_key,
        azure_search_index=search_index,
        app_insights_conn=ai_conn,
        tavily_api_key=tavily_key,
        db_path=os.path.join(data_dir, "app.db"),
        demo_db_path=os.path.join(data_dir, "demo.db"),
        sample_docs_dir=_env("SAMPLE_DOCS_DIR", "/app/sample_docs"),
        flags=flags,
    )


def active_model(settings_obj: "Settings") -> str:
    """Model id for the currently-active provider."""
    if settings_obj.llm_provider == "azure":
        return settings_obj.azure_openai_deployment
    if settings_obj.llm_provider == "openai":
        return settings_obj.openai_model
    if settings_obj.llm_provider == "anthropic":
        return settings_obj.anthropic_model
    return ""


settings = load_settings()
