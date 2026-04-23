# Prompt engineering basics

A system prompt sets the agent's persona, capabilities, and constraints. Keep it short, specific, and testable. Prefer "Do X. Do not do Y." over long abstract descriptions. When a tool is available, tell the model when to use it, not just what it does.

Provide few-shot examples only when you can't achieve the target behavior with instructions alone; examples cost tokens every turn. For reasoning-heavy tasks, ask the model to think step by step in a private scratchpad before producing its final answer.
