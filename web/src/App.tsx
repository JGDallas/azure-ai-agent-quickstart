import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AgentSpec,
  Budget,
  Flags,
  getBudget,
  getHealth,
  listAgents,
} from "./api";
import { AgentPicker } from "./components/AgentPicker";
import { ChatPanel } from "./components/ChatPanel";
import { ClientEvent, DevDrawer } from "./components/DevDrawer";
import { Inspector } from "./components/Inspector";

type ToolEvent = {
  id: string;
  name: string;
  args?: any;
  result?: any;
  latencyMs?: number;
  startedAt: number;
};

export default function App() {
  const [agents, setAgents] = useState<AgentSpec[]>([]);
  const [agentId, setAgentId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [budget, setBudget] = useState<Budget | null>(null);
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([]);
  const [flags, setFlags] = useState<Flags | null>(null);
  const [deployment, setDeployment] = useState<string>("");
  const [banner, setBanner] = useState<string | null>(null);

  // Dev drawer state
  const [devOpen, setDevOpen] = useState(false);
  const [clientEvents, setClientEvents] = useState<ClientEvent[]>([]);
  const [serverRefreshToken, setServerRefreshToken] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const h = await getHealth();
        setFlags(h.features);
        setDeployment(`${h.provider}/${h.model}`);
        if (!h.features.provider_azure && !h.features.provider_openai && !h.features.provider_anthropic) {
          setBanner("No LLM provider is configured. Fill in the provider block for your LLM_PROVIDER in .env and restart.");
        }
      } catch (e) {
        setBanner("Cannot reach the API. Is the api container running?");
      }
      try {
        const a = await listAgents();
        setAgents(a);
        if (a.length && !agentId) setAgentId(a[0].id);
      } catch {}
    })();
  }, []);

  const refreshBudget = useCallback(async () => {
    if (!sessionId) {
      setBudget(null);
      return;
    }
    try {
      setBudget(await getBudget(sessionId));
    } catch {}
  }, [sessionId]);

  useEffect(() => {
    refreshBudget();
  }, [refreshBudget]);

  const onEvent = useCallback((event: string, data: any) => {
    // Record every SSE event for the dev drawer's Client tab.
    setClientEvents((evs) => [...evs, { ts: Date.now(), event, data }]);

    if (event === "tool_call") {
      setToolEvents((ts) => [
        ...ts,
        { id: data.id, name: data.name, args: data.args, startedAt: Date.now() },
      ]);
    } else if (event === "tool_result") {
      setToolEvents((ts) =>
        ts.map((t) =>
          t.id === data.id ? { ...t, result: data.result, latencyMs: data.latency_ms } : t,
        ),
      );
    } else if (event === "usage" || event === "final") {
      refreshBudget();
      if (event === "final") setServerRefreshToken((n) => n + 1);
    }
  }, [refreshBudget]);

  function startNewSession() {
    setSessionId(null);
    setBudget(null);
    setToolEvents([]);
    setClientEvents([]);
  }

  const integrations = useMemo(() => {
    if (!flags) return "";
    const parts: string[] = [];
    parts.push(`deployment: ${deployment || "?"}`);
    parts.push(flags.azure_ai_search ? "Azure AI Search" : "local FTS5");
    if (flags.app_insights) parts.push("App Insights");
    return parts.join(" · ");
  }, [flags, deployment]);

  return (
    <div className="h-full flex flex-col">
      <header className="px-5 py-3 border-b border-ink-200 flex items-center gap-4 bg-white">
        <div className="font-semibold">Azure AI Agent Quickstart</div>
        <div className="text-xs text-ink-400">{integrations}</div>
        <button
          onClick={() => setDevOpen((v) => !v)}
          className="ml-auto text-xs px-2 py-1 rounded border border-ink-200 hover:bg-ink-50 font-mono"
          title="Developer drawer: raw SSE events, server-side LLM calls"
        >
          {"{ }"} dev
        </button>
        <div className="text-xs text-ink-400">
          {sessionId ? `session ${sessionId}` : "no session yet"}
        </div>
      </header>
      {banner && (
        <div className="px-5 py-2 bg-amber-100 text-amber-900 text-xs border-b border-amber-200">
          {banner}
        </div>
      )}
      <div className="flex-1 min-h-0 grid grid-cols-[260px_minmax(0,1fr)_360px]">
        <aside className="border-r border-ink-200 bg-white">
          <AgentPicker
            agents={agents}
            selected={agentId}
            onSelect={(id) => {
              setAgentId(id);
              startNewSession();
            }}
            onNewSession={startNewSession}
          />
        </aside>
        <main className="min-h-0">
          <ChatPanel
            sessionId={sessionId}
            setSessionId={setSessionId}
            agent={agentId || ""}
            disabled={!agentId}
            onEvent={onEvent}
          />
        </main>
        <aside className="border-l border-ink-200 bg-white">
          <Inspector
            sessionId={sessionId}
            budget={budget}
            refreshBudget={refreshBudget}
            toolEvents={toolEvents}
          />
        </aside>
      </div>
      <DevDrawer
        open={devOpen}
        onClose={() => setDevOpen(false)}
        sessionId={sessionId}
        clientEvents={clientEvents}
        onClear={() => setClientEvents([])}
        refreshToken={serverRefreshToken}
      />
    </div>
  );
}
