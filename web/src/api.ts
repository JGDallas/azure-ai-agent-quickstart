// Minimal API client. All endpoints are proxied under /api in dev
// (see vite.config.ts) and under nginx in production.

export type AgentSpec = { id: string; name: string; description: string };

export type Flags = {
  azure_openai: boolean;
  azure_ai_search: boolean;
  app_insights: boolean;
};

export type Health = {
  status: string;
  features: Flags;
  deployment: string;
};

export type Budget = {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  remaining_tokens: number;
  remaining_usd: number;
  limits: { token_budget: number; usd_budget: number };
};

export type EvalScore = { score: number; rationale: string };
export type EvalResult = {
  groundedness: EvalScore;
  relevance: EvalScore;
  coherence: EvalScore;
  error?: string;
};

const API = "/api";

export async function getHealth(): Promise<Health> {
  const res = await fetch(`${API}/healthz`);
  return res.json();
}

export async function listAgents(): Promise<AgentSpec[]> {
  const res = await fetch(`${API}/agents`);
  return res.json();
}

export async function getBudget(sessionId: string): Promise<Budget> {
  const res = await fetch(`${API}/budget/${encodeURIComponent(sessionId)}`);
  return res.json();
}

export async function resetBudget(sessionId: string): Promise<void> {
  await fetch(`${API}/budget/${encodeURIComponent(sessionId)}/reset`, { method: "POST" });
}

export async function evaluateLast(sessionId: string): Promise<EvalResult> {
  const res = await fetch(`${API}/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return res.json();
}

export type SSEEvent = { event: string; data: any };

export async function* streamChat(body: {
  session_id: string | null;
  agent: string;
  message: string;
}): AsyncGenerator<SSEEvent> {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    // Normalize CRLF -> LF so our event-boundary scan is trivial;
    // sse-starlette writes \r\n\r\n between events.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");

    let sep = buffer.indexOf("\n\n");
    while (sep !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const event = parseSSE(raw);
      if (event) yield event;
      sep = buffer.indexOf("\n\n");
    }
  }
}

function parseSSE(block: string): SSEEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  if (dataLines.length === 0) return null;
  const raw = dataLines.join("\n");
  try {
    return { event, data: JSON.parse(raw) };
  } catch {
    return { event, data: raw };
  }
}
