"""Lightweight LLM-as-judge.

We ask the same deployment to score the last assistant reply on
three dimensions: Groundedness, Relevance, Coherence (1-5 each)
with a one-line rationale. Output is coerced to JSON via the
response_format argument.

This deliberately does NOT use `azure-ai-evaluation` — that SDK
pulls in extra dependencies and setup. Upgrade path is obvious:
swap this file for the SDK if you want production-grade metrics.
"""

from __future__ import annotations

import json
from typing import Any

from .llm import chat_once


SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "groundedness": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 1, "maximum": 5},
                "rationale": {"type": "string"},
            },
            "required": ["score", "rationale"],
        },
        "relevance": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 1, "maximum": 5},
                "rationale": {"type": "string"},
            },
            "required": ["score", "rationale"],
        },
        "coherence": {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 1, "maximum": 5},
                "rationale": {"type": "string"},
            },
            "required": ["score", "rationale"],
        },
    },
    "required": ["groundedness", "relevance", "coherence"],
}


SYSTEM_PROMPT = (
    "You are an evaluator. Score the assistant's last reply on "
    "Groundedness, Relevance, and Coherence using a 1-5 scale "
    "(5 is best). Return ONLY JSON matching the provided schema. "
    "Keep each rationale to one short sentence."
)


def evaluate(
    user_message: str,
    assistant_message: str,
    retrieved_context: list[str] | None = None,
) -> dict[str, Any]:
    context_block = ""
    if retrieved_context:
        context_block = "\n\nRetrieved context:\n" + "\n---\n".join(retrieved_context)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User question:\n{user_message}\n\n"
                f"Assistant reply:\n{assistant_message}{context_block}"
            ),
        },
    ]

    try:
        resp = chat_once(
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        parsed = json.loads(raw)
    except Exception as exc:
        return {"error": f"Evaluation failed: {exc}"}

    # Clamp and normalize shape defensively.
    def _pick(name: str) -> dict[str, Any]:
        node = parsed.get(name) or {}
        score = node.get("score")
        try:
            score = max(1, min(5, int(score)))
        except (TypeError, ValueError):
            score = 0
        return {"score": score, "rationale": str(node.get("rationale", ""))}

    return {
        "groundedness": _pick("groundedness"),
        "relevance": _pick("relevance"),
        "coherence": _pick("coherence"),
    }
