# Function calling

Function calling lets the model request that the application execute a typed function (tool) and feed the result back into the conversation. The pattern is: you pass a list of tool schemas alongside the user's message; the model may respond with `tool_calls` instead of prose; the application executes the calls and appends one `role: tool` message per result; the model is invoked again and produces a final answer.

Function calling is the foundation of agentic workflows on Azure OpenAI. The agent loop is just this cycle repeated until the model returns plain text. Keep tool schemas narrow and well-described — the model picks the right tool from the description.
