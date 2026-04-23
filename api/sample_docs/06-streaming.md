# Streaming responses

Setting `stream=true` on a chat completion returns a series of Server-Sent Events, one per token delta. This dramatically improves perceived latency in chat UIs. Tool calls are streamed incrementally as well — the `id` and `name` arrive first, then `arguments` in chunks that you concatenate by `index`.

Pass `stream_options: { include_usage: true }` to receive a final chunk containing prompt and completion token counts. This is the only reliable way to do budget accounting when streaming.
