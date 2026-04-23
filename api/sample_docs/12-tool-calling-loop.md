# The tool-calling loop

The tool-calling loop is the core of any agent. Each iteration:

1. Send the current conversation plus the tool schemas to the model.
2. If the response contains `tool_calls`, execute each and append the results as `role: tool` messages.
3. Otherwise, the response is the final answer — break.

Always cap the iteration count so a misbehaving tool loop cannot burn the token budget. Six to ten iterations is usually enough. Record every tool call and every result for observability; this is what makes an agent debuggable.
