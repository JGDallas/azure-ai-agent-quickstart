"""Lightweight LLM-as-judge.

We ask the active provider to score the last assistant reply on
three dimensions: Groundedness, Relevance, Coherence (1-5 each)
with a one-line rationale.

The schema gets inlined into the prompt so the model sees
exactly what shape to return — the openai-compat adapter's
complete_json only enforces "valid JSON", not schema conformance.
The parser is also tolerant of case-insensitive keys as
belt-and-suspenders.
"""

from __future__ import annotations

import json
from typing import Any

from .providers import Provider


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


SYSTEM_PROMPT = """\
You are an evaluator. Score the assistant's last reply on three
dimensions using a 1-5 integer scale (5 is best):

  groundedness — is the reply supported by the user's question
                 and any retrieved context, without invented
                 details?
  relevance    — does the reply answer the question that was
                 asked?
  coherence    — is the reply well-formed, clear, and internally
                 consistent?

Return ONLY a JSON object with EXACTLY this shape:

{
  "groundedness": {"score": <int 1-5>, "rationale": "<one short sentence>"},
  "relevance":    {"score": <int 1-5>, "rationale": "<one short sentence>"},
  "coherence":    {"score": <int 1-5>, "rationale": "<one short sentence>"}
}

Keys MUST be lowercase. Each rationale MUST be one short sentence.
Do not include any extra keys or prose outside the JSON.\
"""


def _pick(parsed: dict[str, Any], name: str) -> dict[str, Any]:
    """Tolerant lookup. Accepts the canonical lowercase key, a
    capitalized variant, or a flat `<name>` key whose value is
    the score (with rationale elsewhere)."""
    node = parsed.get(name)
    if node is None:
        # Try capitalized.
        for k, v in parsed.items():
            if k.lower() == name.lower():
                node = v
                break

    rationale: str = ""
    score_raw: Any = None

    if isinstance(node, dict):
        score_raw = node.get("score")
        rationale = str(node.get("rationale", ""))
    elif isinstance(node, (int, float)):
        # Flat shape: score is the value, rationale elsewhere.
        score_raw = node
        rmap = parsed.get("rationale") or parsed.get("rationales") or {}
        if isinstance(rmap, dict):
            for k, v in rmap.items():
                if k.lower() == name.lower():
                    rationale = str(v)
                    break

    try:
        score = max(1, min(5, int(score_raw)))
    except (TypeError, ValueError):
        score = 0
    return {"score": score, "rationale": rationale}


def evaluate(
    provider: Provider,
    user_message: str,
    assistant_message: str,
    retrieved_context: list[str] | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
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
        raw = provider.complete_json(
            messages=messages,
            schema=SCORE_SCHEMA,
            temperature=0.0,
            session_id=session_id,
            run_id=run_id,
        )
        parsed = json.loads(raw)
    except Exception as exc:
        return {"error": f"Evaluation failed: {exc}"}

    return {
        "groundedness": _pick(parsed, "groundedness"),
        "relevance": _pick(parsed, "relevance"),
        "coherence": _pick(parsed, "coherence"),
    }
