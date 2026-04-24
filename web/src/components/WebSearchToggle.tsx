type Props = {
  enabled: boolean;
  onChange: (v: boolean) => void;
  available: boolean;
};

export function WebSearchToggle({ enabled, onChange, available }: Props) {
  const disabled = !available;
  const title = disabled
    ? "Set TAVILY_API_KEY in .env and restart to enable web search."
    : enabled
      ? "Web search: on. Research Assistant will use Tavily for current-events questions."
      : "Web search: off. Research Assistant uses the local corpus only.";

  return (
    <button
      onClick={() => !disabled && onChange(!enabled)}
      disabled={disabled}
      title={title}
      className={
        "text-xs px-2 py-1 rounded border transition " +
        (disabled
          ? "border-ink-200 text-ink-300 cursor-not-allowed"
          : enabled
            ? "border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100"
            : "border-ink-200 text-ink-600 hover:bg-ink-50")
      }
    >
      <span className="mr-1">web search</span>
      <span className="font-mono">{enabled ? "on" : "off"}</span>
    </button>
  );
}
