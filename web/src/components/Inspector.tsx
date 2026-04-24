import { useEffect, useState } from "react";
import {
  Budget,
  EvalResult,
  evaluateLast,
  getBudget,
  resetBudget,
} from "../api";

type ToolEvent = {
  id: string;
  name: string;
  args?: any;
  result?: any;
  latencyMs?: number;
  startedAt: number;
};

type Props = {
  sessionId: string | null;
  budget: Budget | null;
  refreshBudget: () => void;
  toolEvents: ToolEvent[];
};

export function Inspector({ sessionId, budget, refreshBudget, toolEvents }: Props) {
  return (
    <div className="h-full overflow-y-auto">
      <Section title="Budget">
        <BudgetBlock sessionId={sessionId} budget={budget} refreshBudget={refreshBudget} />
      </Section>
      <Section title="Usage">
        <UsageBlock budget={budget} />
      </Section>
      <Section title="Tool timeline">
        <ToolTimeline events={toolEvents} />
      </Section>
      <Section title="Evaluation">
        <EvaluationBlock sessionId={sessionId} />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border-b border-ink-200">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-4 py-3 flex items-center justify-between text-xs uppercase tracking-wider text-ink-400 hover:bg-ink-50"
      >
        <span>{title}</span>
        <span>{open ? "-" : "+"}</span>
      </button>
      {open && <div className="px-4 py-3 text-sm">{children}</div>}
    </div>
  );
}

function Bar({ used, limit }: { used: number; limit: number }) {
  const pct = limit > 0 ? Math.min(100, (used / limit) * 100) : 0;
  return (
    <div className="h-2 bg-ink-100 rounded overflow-hidden">
      <div className="h-full bg-ink-700" style={{ width: `${pct}%` }} />
    </div>
  );
}

function BudgetBlock({
  sessionId,
  budget,
  refreshBudget,
}: {
  sessionId: string | null;
  budget: Budget | null;
  refreshBudget: () => void;
}) {
  if (!budget) return <div className="text-ink-400">No session yet.</div>;
  return (
    <div className="space-y-3">
      <div>
        <div className="flex justify-between text-xs text-ink-500 mb-1">
          <span>Tokens</span>
          <span>
            {budget.total_tokens.toLocaleString()} / {budget.limits.token_budget.toLocaleString()}
          </span>
        </div>
        <Bar used={budget.total_tokens} limit={budget.limits.token_budget} />
      </div>
      <div>
        <div className="flex justify-between text-xs text-ink-500 mb-1">
          <span>Spend (USD)</span>
          <span>
            ${budget.cost_usd.toFixed(4)} / ${budget.limits.usd_budget.toFixed(2)}
          </span>
        </div>
        <Bar used={budget.cost_usd} limit={budget.limits.usd_budget} />
      </div>
      <button
        disabled={!sessionId}
        onClick={async () => {
          if (sessionId) {
            await resetBudget(sessionId);
            refreshBudget();
          }
        }}
        className="text-xs px-3 py-1.5 rounded border border-ink-200 hover:bg-ink-50 disabled:opacity-40"
      >
        Reset session
      </button>
    </div>
  );
}

function UsageBlock({ budget }: { budget: Budget | null }) {
  if (!budget) return <div className="text-ink-400">No usage yet.</div>;
  return (
    <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
      <dt className="text-ink-400">Prompt tokens</dt>
      <dd className="text-right">{budget.prompt_tokens.toLocaleString()}</dd>
      <dt className="text-ink-400">Completion tokens</dt>
      <dd className="text-right">{budget.completion_tokens.toLocaleString()}</dd>
      <dt className="text-ink-400">Total tokens</dt>
      <dd className="text-right">{budget.total_tokens.toLocaleString()}</dd>
      <dt className="text-ink-400">Cost (USD)</dt>
      <dd className="text-right">${budget.cost_usd.toFixed(6)}</dd>
      <dt className="text-ink-400">Remaining tokens</dt>
      <dd className="text-right">{budget.remaining_tokens.toLocaleString()}</dd>
      <dt className="text-ink-400">Remaining USD</dt>
      <dd className="text-right">${budget.remaining_usd.toFixed(4)}</dd>
    </dl>
  );
}

function ToolTimeline({ events }: { events: ToolEvent[] }) {
  if (!events.length) return <div className="text-ink-400">No tool calls yet.</div>;
  return (
    <ol className="space-y-2 text-xs">
      {events.map((e, i) => (
        <li key={e.id} className="flex gap-2">
          <span className="text-ink-400 w-4 text-right">{i + 1}.</span>
          <div className="flex-1">
            <div className="flex justify-between">
              <span className="font-medium">{e.name}</span>
              <span className="text-ink-400">
                {e.latencyMs !== undefined ? `${e.latencyMs} ms` : "running..."}
              </span>
            </div>
            {e.args && (
              <div
                className="text-ink-400 break-all whitespace-pre-wrap font-mono text-[10px] leading-snug mt-0.5"
                title={JSON.stringify(e.args)}
              >
                {JSON.stringify(e.args)}
              </div>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function EvaluationBlock({ sessionId }: { sessionId: string | null }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<EvalResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setResult(null);
    setError(null);
  }, [sessionId]);

  async function run() {
    if (!sessionId) return;
    setBusy(true);
    setError(null);
    try {
      const r = await evaluateLast(sessionId);
      if (r.error) setError(r.error);
      else setResult(r);
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <button
        disabled={!sessionId || busy}
        onClick={run}
        className="text-xs px-3 py-1.5 rounded bg-ink-800 text-white disabled:opacity-40"
      >
        {busy ? "Evaluating..." : "Evaluate last response"}
      </button>
      {error && <div className="text-xs text-red-600">{error}</div>}
      {result && !error && (
        <div className="space-y-2 text-xs">
          <ScoreRow label="Groundedness" score={result.groundedness} />
          <ScoreRow label="Relevance" score={result.relevance} />
          <ScoreRow label="Coherence" score={result.coherence} />
        </div>
      )}
    </div>
  );
}

function ScoreRow({ label, score }: { label: string; score: { score: number; rationale: string } }) {
  return (
    <div className="border border-ink-200 rounded p-2">
      <div className="flex justify-between">
        <span className="font-medium">{label}</span>
        <span>{score.score} / 5</span>
      </div>
      <div className="text-ink-400 mt-1">{score.rationale}</div>
    </div>
  );
}
