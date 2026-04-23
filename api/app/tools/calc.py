"""calculator tool.

Evaluates a basic arithmetic expression. We parse with `ast` and
walk the tree ourselves so `eval` is never reached with untrusted
input — only numbers and the common operators are permitted.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

from ..agent import Tool


PARAMETERS = {
    "type": "object",
    "properties": {
        "expression": {
            "type": "string",
            "description": "Arithmetic expression, e.g. '(1200 + 350) * 0.08'.",
        },
    },
    "required": ["expression"],
}


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval(node.operand))
    raise ValueError(f"Unsupported expression element: {type(node).__name__}")


def _run(args: dict[str, Any]) -> dict[str, Any]:
    expr = str(args.get("expression", "")).strip()
    if not expr:
        return {"error": "Empty expression."}
    try:
        tree = ast.parse(expr, mode="eval")
        value = _eval(tree)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {"expression": expr, "value": value}


calculator = Tool(
    name="calculator",
    description="Evaluate a basic arithmetic expression.",
    parameters=PARAMETERS,
    fn=_run,
)
