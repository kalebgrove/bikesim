interface Props {
  label: string;
  value: number | string;
  unit?: string;
  decimals?: number;
  highlight?: boolean;
  warn?: boolean;
  large?: boolean;
}

function safeDisplay(value: number | string, decimals: number): string {
  if (typeof value === "string") return value;
  if (!isFinite(value)) return "--";
  return value.toFixed(decimals);
}

export default function TelemetryValue({ label, value, unit, decimals = 1, highlight, warn, large }: Props) {
  const displayVal = safeDisplay(value, decimals);
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className="text-xs uppercase tracking-widest"
        style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)", letterSpacing: "0.08em" }}
      >
        {label}
      </span>
      <div className="flex items-baseline gap-1">
        <span
          className={`mono font-semibold ${large ? "text-3xl" : "text-xl"}`}
          style={{
            color: warn ? "var(--accent)" : highlight ? "var(--primary)" : "var(--foreground)",
            fontFamily: "var(--font-mono)",
          }}
        >
          {displayVal}
        </span>
        {unit && (
          <span className="text-xs" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            {unit}
          </span>
        )}
      </div>
    </div>
  );
}
