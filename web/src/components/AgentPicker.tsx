import { AgentSpec } from "../api";

type Props = {
  agents: AgentSpec[];
  selected: string | null;
  onSelect: (id: string) => void;
  onNewSession: () => void;
};

export function AgentPicker({ agents, selected, onSelect, onNewSession }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-ink-200">
        <div className="text-xs uppercase tracking-wider text-ink-400">Agents</div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {agents.map((a) => (
          <button
            key={a.id}
            onClick={() => onSelect(a.id)}
            className={
              "w-full text-left px-4 py-3 border-b border-ink-100 hover:bg-ink-100 transition " +
              (selected === a.id ? "bg-ink-100" : "")
            }
          >
            <div className="font-medium text-ink-800">{a.name}</div>
            <div className="text-xs text-ink-400 mt-1 leading-snug">{a.description}</div>
          </button>
        ))}
      </div>
      <div className="p-3 border-t border-ink-200">
        <button
          onClick={onNewSession}
          className="w-full text-sm px-3 py-2 rounded bg-ink-800 text-white hover:bg-ink-700"
        >
          New session
        </button>
      </div>
    </div>
  );
}
