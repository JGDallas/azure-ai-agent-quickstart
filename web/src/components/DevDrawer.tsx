import { useCallback, useEffect, useMemo, useState } from "react";
import { getTraces, TraceEvent } from "../api";

export type ClientEvent = {
  ts: number;
  event: string;
  data: any;
};

type Tab = "client" | "server";

type Props = {
  open: boolean;
  onClose: () => void;
  sessionId: string | null;
  clientEvents: ClientEvent[];
  onClear: () => void;
  refreshToken: number;  // bumped by the parent after each `final` SSE event
};

export function DevDrawer({ open, onClose, sessionId, clientEvents, onClear, refreshToken }: Props) {
  const [tab, setTab] = useState<Tab>("client");
  const [serverEvents, setServerEvents] = useState<TraceEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchServer = useCallback(async () => {
    if (!sessionId) {
      setServerEvents([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await getTraces(sessionId);
      setServerEvents(res.persisted ?? []);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (open) fetchServer();
  }, [open, fetchServer]);

  // Auto-refresh when the parent signals a turn just finished.
  useEffect(() => {
    if (open && refreshToken > 0) fetchServer();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshToken]);

  return (
    <>
      {open && <div className="fixed inset-0 bg-black/20 z-10" onClick={onClose} />}
      <aside
        className={
          "fixed top-0 right-0 bottom-0 w-[560px] max-w-full bg-white border-l border-ink-200 shadow-xl z-20 " +
          "transform transition-transform duration-150 " +
          (open ? "translate-x-0" : "translate-x-full")
        }
      >
        <header className="px-4 py-3 border-b border-ink-200 flex items-center gap-3">
          <div className="font-medium">Developer</div>
          <div className="text-xs text-ink-400">
            {sessionId ? `session ${sessionId}` : "no session"}
          </div>
          <button
            onClick={onClose}
            className="ml-auto text-xs px-2 py-1 rounded hover:bg-ink-100"
            aria-label="Close"
          >
            close
          </button>
        </header>
        <nav className="px-2 pt-2 flex gap-1 border-b border-ink-200">
          <TabButton active={tab === "client"} onClick={() => setTab("client")}>
            Client events ({clientEvents.length})
          </TabButton>
          <TabButton active={tab === "server"} onClick={() => setTab("server")}>
            Server events ({serverEvents.filter((e) => e.type.startsWith("llm.")).length})
          </TabButton>
        </nav>

        <div className="h-[calc(100%-110px)] overflow-y-auto">
          {tab === "client" && (
            <ClientEventsPane events={clientEvents} onClear={onClear} />
          )}
          {tab === "server" && (
            <ServerEventsPane
              events={serverEvents}
              loading={loading}
              error={error}
              onRefresh={fetchServer}
            />
          )}
        </div>
      </aside>
    </>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "text-xs px-3 py-2 rounded-t " +
        (active
          ? "bg-white border border-ink-200 border-b-white -mb-px text-ink-800 font-medium"
          : "text-ink-400 hover:text-ink-700")
      }
    >
      {children}
    </button>
  );
}

function ClientEventsPane({ events, onClear }: { events: ClientEvent[]; onClear: () => void }) {
  if (events.length === 0) {
    return (
      <div className="p-4 text-sm text-ink-400">
        No events yet. Send a chat and raw SSE events will stream in here.
      </div>
    );
  }
  return (
    <div>
      <div className="px-4 py-2 border-b border-ink-100 flex items-center justify-between sticky top-0 bg-white">
        <div className="text-xs text-ink-400">
          SSE events this browser received, newest at the bottom
        </div>
        <button
          onClick={onClear}
          className="text-xs px-2 py-1 rounded border border-ink-200 hover:bg-ink-50"
        >
          Clear
        </button>
      </div>
      <ol>
        {events.map((e, i) => (
          <EventRow
            key={i}
            label={e.event}
            ts={e.ts}
            body={e.data}
            accent={accentForClient(e.event)}
          />
        ))}
      </ol>
    </div>
  );
}

function ServerEventsPane({
  events,
  loading,
  error,
  onRefresh,
}: {
  events: TraceEvent[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}) {
  const llm = useMemo(
    () => events.filter((e) => e.type.startsWith("llm.")),
    [events],
  );

  if (error) return <div className="p-4 text-sm text-red-600">Error: {error}</div>;

  return (
    <div>
      <div className="px-4 py-2 border-b border-ink-100 flex items-center justify-between sticky top-0 bg-white">
        <div className="text-xs text-ink-400">
          LLM calls captured server-side. Paired as request → response by request_id.
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="text-xs px-2 py-1 rounded border border-ink-200 hover:bg-ink-50 disabled:opacity-40"
        >
          {loading ? "…" : "Refresh"}
        </button>
      </div>
      {llm.length === 0 ? (
        <div className="p-4 text-sm text-ink-400">No LLM calls yet for this session.</div>
      ) : (
        <ol>
          {llm.map((e, i) => (
            <EventRow
              key={i}
              label={e.type}
              ts={e.ts * 1000}
              body={e.payload}
              accent={accentForServer(e.type)}
              subtitle={serverSubtitle(e)}
            />
          ))}
        </ol>
      )}
    </div>
  );
}

function EventRow({
  label,
  ts,
  body,
  accent,
  subtitle,
}: {
  label: string;
  ts: number;
  body: any;
  accent: string;
  subtitle?: string;
}) {
  const time = new Date(ts).toLocaleTimeString(undefined, { hour12: false }) +
    "." + String(ts % 1000).padStart(3, "0");
  return (
    <li className="border-b border-ink-100">
      <details>
        <summary className="px-4 py-2 cursor-pointer flex items-center gap-3 hover:bg-ink-50">
          <span className={"text-[10px] font-mono rounded px-1.5 py-0.5 " + accent}>
            {label}
          </span>
          {subtitle && <span className="text-xs text-ink-500">{subtitle}</span>}
          <span className="ml-auto text-[10px] text-ink-400 font-mono">{time}</span>
        </summary>
        <pre className="text-[11px] bg-ink-50 px-4 py-3 overflow-x-auto whitespace-pre-wrap break-words">
          {JSON.stringify(body, null, 2)}
        </pre>
      </details>
    </li>
  );
}

function serverSubtitle(e: TraceEvent): string {
  const p = e.payload || {};
  const parts: string[] = [];
  if (p.provider) parts.push(p.provider);
  if (p.model) parts.push(p.model);
  if (e.type === "llm.response") {
    if (p.latency_ms !== undefined) parts.push(`${p.latency_ms} ms`);
    if (p.usage) {
      parts.push(`${p.usage.prompt_tokens} in / ${p.usage.completion_tokens} out`);
    }
    if (p.status === "error") parts.push("ERROR");
  }
  return parts.join(" · ");
}

function accentForClient(name: string): string {
  switch (name) {
    case "token":
      return "bg-ink-100 text-ink-600";
    case "tool_call":
      return "bg-amber-100 text-amber-800";
    case "tool_result":
      return "bg-emerald-100 text-emerald-800";
    case "usage":
      return "bg-sky-100 text-sky-800";
    case "error":
      return "bg-red-100 text-red-800";
    case "final":
    case "done":
      return "bg-violet-100 text-violet-800";
    case "session":
      return "bg-slate-200 text-slate-700";
    default:
      return "bg-ink-100 text-ink-700";
  }
}

function accentForServer(type: string): string {
  if (type === "llm.request") return "bg-indigo-100 text-indigo-800";
  if (type === "llm.response") return "bg-teal-100 text-teal-800";
  return "bg-ink-100 text-ink-700";
}
