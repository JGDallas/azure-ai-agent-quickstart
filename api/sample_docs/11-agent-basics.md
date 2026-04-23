# Agent basics

An AI agent is a system that uses an LLM to decide which actions to take to accomplish a user goal. At minimum an agent has a system prompt, a set of tools, and a loop that alternates between model calls and tool executions until the model produces a final answer.

Useful agents are narrow: one clear scope, one to four well-described tools, and a system prompt that makes the scope explicit. Wide-open agents with many overlapping tools are hard to debug and expensive to run. Start small, measure, and add capabilities only when the data justifies it.
