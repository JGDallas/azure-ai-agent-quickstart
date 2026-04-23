"""Runtime configuration.

Reads environment variables once at import and exposes a typed
`settings` object. Also reports which optional integrations are
active so the UI can render clear banners instead of crashing on
missing keys.
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


@dataclass
class Settings:
    # Required Azure OpenAI config.
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment: str
    azure_openai_api_version: str

    # Budgets.
    session_token_budget: int
    session_usd_budget: float
    price_table: dict[str, dict[str, float]]

    # Optional Azure AI Search.
    azure_search_endpoint: str
    azure_search_key: str
    azure_search_index: str

    # Optional App Insights.
    app_insights_conn: str

    # Local paths.
    db_path: str
    demo_db_path: str
    sample_docs_dir: str

    # Derived flags.
    flags: dict[str, bool] = field(default_factory=dict)


def load_settings() -> Settings:
    endpoint = _env("AZURE_OPENAI_ENDPOINT")
    api_key = _env("AZURE_OPENAI_API_KEY")
    deployment = _env("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    api_version = _env("AZURE_OPENAI_API_VERSION", "2024-10-21")

    try:
        token_budget = int(_env("SESSION_TOKEN_BUDGET", "200000"))
    except ValueError:
        token_budget = 200000
    try:
        usd_budget = float(_env("SESSION_USD_BUDGET", "2.00"))
    except ValueError:
        usd_budget = 2.00

    price_json = _env(
        "PRICE_TABLE_JSON",
        '{"gpt-4o-mini":{"input":0.15,"output":0.60}}',
    )
    try:
        price_table = json.loads(price_json)
    except json.JSONDecodeError:
        price_table = {"gpt-4o-mini": {"input": 0.15, "output": 0.60}}

    search_endpoint = _env("AZURE_AI_SEARCH_ENDPOINT")
    search_key = _env("AZURE_AI_SEARCH_KEY")
    search_index = _env("AZURE_AI_SEARCH_INDEX", "quickstart-docs")

    ai_conn = _env("APPLICATIONINSIGHTS_CONNECTION_STRING")

    data_dir = _env("DATA_DIR", "/data")
    os.makedirs(data_dir, exist_ok=True)

    flags = {
        "azure_openai": not _placeholder(endpoint) and not _placeholder(api_key),
        "azure_ai_search": (
            not _placeholder(search_endpoint)
            and not _placeholder(search_key)
            and not _placeholder(search_index)
        ),
        "app_insights": not _placeholder(ai_conn),
    }

    return Settings(
        azure_openai_endpoint=endpoint,
        azure_openai_api_key=api_key,
        azure_openai_deployment=deployment,
        azure_openai_api_version=api_version,
        session_token_budget=token_budget,
        session_usd_budget=usd_budget,
        price_table=price_table,
        azure_search_endpoint=search_endpoint,
        azure_search_key=search_key,
        azure_search_index=search_index,
        app_insights_conn=ai_conn,
        db_path=os.path.join(data_dir, "app.db"),
        demo_db_path=os.path.join(data_dir, "demo.db"),
        sample_docs_dir=_env("SAMPLE_DOCS_DIR", "/app/sample_docs"),
        flags=flags,
    )


settings = load_settings()
