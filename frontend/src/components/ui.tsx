// Shared UI primitives: panels, readouts, buttons, badges.
import type { ReactNode, ButtonHTMLAttributes } from "react";
import { Link } from "react-router";

type Tone = "default" | "accent" | "ok" | "warn" | "err";

const toneText: Record<Tone, string> = {
  default: "text-fg",
  accent: "text-accent",
  ok: "text-ok",
  warn: "text-warn",
  err: "text-err",
};

export function Panel({
  title,
  meta,
  actions,
  children,
  className = "",
  bodyClassName = "p-4",
}: {
  title?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`bg-panel border border-line rounded-lg flex flex-col min-w-0 ${className}`}>
      {(title || actions || meta) && (
        <header className="flex items-center justify-between gap-3 px-4 h-10 border-b border-line shrink-0">
          <div className="flex items-baseline gap-3 min-w-0">
            {title && <h2 className="text-[13px] font-semibold text-fg truncate">{title}</h2>}
            {meta && <span className="text-xs text-faint truncate">{meta}</span>}
          </div>
          {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
        </header>
      )}
      {/* grow, not flex-1: flex-basis 0 would override a fixed body height (e.g. h-[170px]) and collapse charts to 0 px */}
      <div className={`grow min-h-0 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

export function Stat({
  label,
  value,
  unit,
  sub,
  tone = "default",
  size = "md",
}: {
  label: ReactNode;
  value: ReactNode;
  unit?: string;
  sub?: ReactNode;
  tone?: Tone;
  size?: "sm" | "md" | "lg";
}) {
  const valueSize = { sm: "text-base", md: "text-xl", lg: "text-[28px] leading-8" }[size];
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <span className="label truncate">{label}</span>
      <div className="flex items-baseline gap-1.5">
        <span className={`num font-semibold ${valueSize} ${toneText[tone]}`}>{value}</span>
        {unit && <span className="num text-xs text-faint">{unit}</span>}
      </div>
      {sub && <span className="text-xs text-faint truncate">{sub}</span>}
    </div>
  );
}

/** A row of stats separated by hairlines, used as a KPI strip. */
export function StatStrip({ children, cols }: { children: ReactNode; cols: string }) {
  return (
    <div className={`grid ${cols} gap-px bg-line border border-line rounded-lg overflow-hidden`}>
      {children}
    </div>
  );
}

export function StatCell(props: Parameters<typeof Stat>[0]) {
  return (
    <div className="bg-panel px-4 py-3">
      <Stat {...props} />
    </div>
  );
}

type Variant = "primary" | "secondary" | "ghost" | "danger";

const variantClass: Record<Variant, string> = {
  primary: "bg-accent-strong text-white hover:bg-accent border border-transparent",
  secondary: "bg-panel-2 text-fg border border-line hover:border-line-strong",
  ghost: "text-dim hover:text-fg hover:bg-panel-2 border border-transparent",
  danger: "text-err border border-err/40 hover:bg-err/10",
};

function buttonClass(variant: Variant, size: "sm" | "md") {
  const sizing = size === "sm" ? "h-7 px-2.5 text-xs" : "h-9 px-3.5 text-[13px]";
  return `inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap ${sizing} ${variantClass[variant]}`;
}

export function Button({
  variant = "secondary",
  size = "md",
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" }) {
  return <button {...rest} className={`${buttonClass(variant, size)} ${className}`} />;
}

export function ButtonLink({
  to,
  variant = "secondary",
  size = "md",
  children,
}: {
  to: string;
  variant?: Variant;
  size?: "sm" | "md";
  children: ReactNode;
}) {
  return (
    <Link to={to} className={buttonClass(variant, size)}>
      {children}
    </Link>
  );
}

const statusTone: Record<string, string> = {
  running: "bg-ok/10 text-ok border-ok/30",
  connected: "bg-ok/10 text-ok border-ok/30",
  paused: "bg-warn/10 text-warn border-warn/30",
  reconnecting: "bg-warn/10 text-warn border-warn/30",
  complete: "bg-accent/10 text-accent border-accent/30",
  stopped: "bg-err/10 text-err border-err/30",
};

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const tone = statusTone[status] ?? "bg-panel-2 text-dim border-line";
  return (
    <span className={`inline-flex items-center gap-1.5 h-5 px-2 rounded-full border text-[11px] font-medium capitalize ${tone}`}>
      <span className={`size-1.5 rounded-full bg-current ${status === "running" ? "animate-pulse" : ""}`} />
      {label ?? status}
    </span>
  );
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-6 flex-wrap">
      <div className="min-w-0">
        {eyebrow && <div className="label mb-1.5">{eyebrow}</div>}
        <h1 className="text-xl font-semibold tracking-tight text-fg">{title}</h1>
        {subtitle && <div className="text-[13px] text-dim mt-1">{subtitle}</div>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center gap-2 py-12 px-6">
      <div className="text-[13px] font-medium text-fg">{title}</div>
      {children && <div className="text-xs text-faint max-w-sm">{children}</div>}
    </div>
  );
}

export function Callout({ tone = "warn", title, children }: { tone?: "warn" | "err" | "accent"; title?: string; children: ReactNode }) {
  const cls = {
    warn: "border-warn/30 bg-warn/5 text-warn",
    err: "border-err/30 bg-err/5 text-err",
    accent: "border-accent/30 bg-accent/5 text-accent",
  }[tone];
  return (
    <div className={`rounded-md border px-3 py-2 text-xs ${cls}`}>
      {title && <div className="font-semibold mb-0.5">{title}</div>}
      <div className="text-dim">{children}</div>
    </div>
  );
}

// Recharts styling shared by every chart
export const chartTheme = {
  grid: "#242a35",
  tick: { fill: "#636c7c", fontSize: 10, fontFamily: "JetBrains Mono" },
  tooltip: {
    contentStyle: {
      background: "#181c25",
      border: "1px solid #333a48",
      borderRadius: 6,
      fontSize: 11,
      fontFamily: "JetBrains Mono",
      padding: "6px 10px",
    },
    labelStyle: { color: "#9aa3b2", marginBottom: 2 },
    itemStyle: { padding: 0 },
  },
  colors: {
    accent: "#5b9dff",
    power: "#f59e0b",
    speed: "#34d399",
    elev: "#94a3b8",
    warn: "#fbbf24",
  },
};
