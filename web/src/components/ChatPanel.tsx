import { useEffect, useRef, useState } from "react";
import { streamChat } from "../api";

export type ToolCallCard = {
  id: string;
  name: string;
  args: any;
  result?: any;
  latencyMs?: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  toolCalls: ToolCallCard[];
};

type Props = {
  sessionId: string | null;
  setSessionId: (id: string) => void;
  agent: string;
  disabled: boolean;
  onEvent: (event: string, data: any) => void;
  enableWebSearch: boolean;
};

export function ChatPanel({ sessionId, setSessionId, agent, disabled, onEvent, enableWebSearch }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Only clear the transcript when the parent explicitly
    // starts a new session (sessionId -> null). Transitions
    // from null to a real id happen mid-stream on the first
    // turn and must NOT wipe the freshly-added bubbles.
    if (sessionId === null) setMessages([]);
  }, [sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || busy || disabled) return;
    setInput("");
    setBusy(true);

    const userMsg: ChatMessage = { role: "user", content: text, toolCalls: [] };
    const assistantMsg: ChatMessage = { role: "assistant", content: "", toolCalls: [] };
    setMessages((ms) => [...ms, userMsg, assistantMsg]);

    try {
      for await (const evt of streamChat({
        session_id: sessionId,
        agent,
        message: text,
        enable_web_search: enableWebSearch,
      })) {
        onEvent(evt.event, evt.data);

        if (evt.event === "session" && evt.data?.session_id && !sessionId) {
          setSessionId(evt.data.session_id);
        }

        if (evt.event === "token") {
          const chunk = evt.data?.content ?? "";
          setMessages((ms) => {
            const copy = [...ms];
            const last = { ...copy[copy.length - 1] };
            last.content = last.content + chunk;
            copy[copy.length - 1] = last;
            return copy;
          });
        } else if (evt.event === "tool_call") {
          setMessages((ms) => {
            const copy = [...ms];
            const last = { ...copy[copy.length - 1] };
            last.toolCalls = [
              ...last.toolCalls,
              { id: evt.data.id, name: evt.data.name, args: evt.data.args },
            ];
            copy[copy.length - 1] = last;
            return copy;
          });
        } else if (evt.event === "tool_result") {
          setMessages((ms) => {
            const copy = [...ms];
            const last = { ...copy[copy.length - 1] };
            last.toolCalls = last.toolCalls.map((tc) =>
              tc.id === evt.data.id
                ? { ...tc, result: evt.data.result, latencyMs: evt.data.latency_ms }
                : tc,
            );
            copy[copy.length - 1] = last;
            return copy;
          });
        } else if (evt.event === "error") {
          setMessages((ms) => {
            const copy = [...ms];
            const last = { ...copy[copy.length - 1] };
            last.content = (last.content || "") + `\n\n[error] ${evt.data?.message ?? evt.data}`;
            copy[copy.length - 1] = last;
            return copy;
          });
        }
      }
    } catch (e: any) {
      setMessages((ms) => {
        const copy = [...ms];
        const last = { ...copy[copy.length - 1] };
        last.content = (last.content || "") + `\n\n[fetch error] ${e?.message ?? e}`;
        copy[copy.length - 1] = last;
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-full flex flex-col bg-white">
      <div className="px-5 py-3 border-b border-ink-200 flex items-center gap-3">
        <div className="font-medium">Chat</div>
        <div className="text-xs text-ink-400">
          {sessionId ? `session ${sessionId}` : "no active session"}
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-sm text-ink-400 max-w-xl">
            Pick an agent on the left and ask it something. Try:
            <ul className="list-disc ml-6 mt-2 space-y-1">
              <li>Research: "What does the repo say about function calling?"</li>
              <li>Ops: "Which P1 tickets are currently open?"</li>
              <li>Ops: "What was total revenue in Q1 2026?"</li>
            </ul>
          </div>
        )}
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
      </div>

      <div className="p-3 border-t border-ink-200 flex gap-2">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={disabled ? "Select an agent to start" : "Ask something... (Enter to send, Shift+Enter for newline)"}
          rows={2}
          disabled={disabled}
          className="flex-1 px-3 py-2 rounded border border-ink-200 resize-none text-sm focus:outline-none focus:ring-1 focus:ring-ink-500 disabled:bg-ink-50"
        />
        <button
          onClick={send}
          disabled={disabled || busy || !input.trim()}
          className="px-4 py-2 rounded bg-ink-800 text-white text-sm disabled:opacity-40"
        >
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={"max-w-3xl " + (isUser ? "ml-auto" : "")}>
      <div
        className={
          "rounded-lg px-4 py-3 whitespace-pre-wrap text-sm leading-relaxed " +
          (isUser ? "bg-ink-800 text-white" : "bg-ink-100 text-ink-800")
        }
      >
        {message.content || (isUser ? "" : <span className="text-ink-400">thinking...</span>)}
      </div>
      {message.toolCalls.length > 0 && (
        <div className="mt-2 space-y-2">
          {message.toolCalls.map((tc) => (
            <ToolCard key={tc.id} tc={tc} />
          ))}
        </div>
      )}
    </div>
  );
}

function ToolCard({ tc }: { tc: ToolCallCard }) {
  return (
    <details className="border border-ink-200 rounded bg-white text-xs">
      <summary className="px-3 py-2 cursor-pointer flex items-center gap-3">
        <span className="font-mono text-ink-500">tool</span>
        <span className="font-medium">{tc.name}</span>
        {tc.latencyMs !== undefined && (
          <span className="text-ink-400 ml-auto">{tc.latencyMs} ms</span>
        )}
        {tc.result === undefined && tc.latencyMs === undefined && (
          <span className="text-ink-400 ml-auto">running...</span>
        )}
      </summary>
      <div className="border-t border-ink-100 p-3 space-y-2">
        <div>
          <div className="text-ink-400 mb-1">args</div>
          <pre className="bg-ink-50 p-2 rounded overflow-x-auto">{JSON.stringify(tc.args, null, 2)}</pre>
        </div>
        {tc.result !== undefined && (
          <div>
            <div className="text-ink-400 mb-1">result</div>
            <pre className="bg-ink-50 p-2 rounded overflow-x-auto max-h-64">{JSON.stringify(tc.result, null, 2)}</pre>
          </div>
        )}
      </div>
    </details>
  );
}
