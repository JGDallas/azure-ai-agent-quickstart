"""The two V1 agents.

Both use the same loop — only the system prompt and tool bundle
differ. Keep this small. Adding a third agent is adding an entry
to AGENTS and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass

from .agent import Tool
from .tools.calc import calculator
from .tools.search import search_docs
from .tools.sql import run_sql


@dataclass
class AgentSpec:
    id: str
    name: str
    description: str
    system_prompt: str
    tools: list[Tool]


RESEARCH_ASSISTANT = AgentSpec(
    id="research",
    name="Research Assistant",
    description=(
        "Answers questions using search_docs over the Azure docs "
        "corpus (or your own Azure AI Search index)."
    ),
    system_prompt=(
        "You are the Research Assistant. Use the search_docs tool "
        "to find relevant passages before answering. Cite the "
        "titles of the documents you used in your reply. If the "
        "search returns nothing useful, say so plainly instead of "
        "guessing. Keep replies concise and grounded."
    ),
    tools=[search_docs],
)

OPS_HELPER = AgentSpec(
    id="ops",
    name="Ops Helper",
    description=(
        "Answers operational questions about employees, tickets, "
        "and revenue. Can run SQL queries and do arithmetic."
    ),
    system_prompt=(
        "You are the Ops Helper. You have two tools: run_sql "
        "against a read-only SQLite database, and calculator for "
        "arithmetic. Prefer one query per question; inspect the "
        "schema with information_schema-style queries if unsure. "
        "Always explain numeric results in plain English."
    ),
    tools=[run_sql, calculator],
)


AGENTS: dict[str, AgentSpec] = {
    RESEARCH_ASSISTANT.id: RESEARCH_ASSISTANT,
    OPS_HELPER.id: OPS_HELPER,
}


def list_agents() -> list[dict[str, str]]:
    return [
        {"id": a.id, "name": a.name, "description": a.description}
        for a in AGENTS.values()
    ]


def get_agent(agent_id: str) -> AgentSpec:
    spec = AGENTS.get(agent_id)
    if spec is None:
        raise KeyError(f"Unknown agent: {agent_id}")
    return spec
