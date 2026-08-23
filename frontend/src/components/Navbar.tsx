import { Link, useLocation } from "react-router";
import { useSimEngineContext } from "../lib/simEngineContext";

function WsIndicator() {
  const { wsStatus } = useSimEngineContext();
  const colors: Record<string, string> = {
    connected: "bg-green-500",
    reconnecting: "bg-yellow-500 animate-pulse",
    disconnected: "bg-zinc-600",
    complete: "bg-sky-500",
  };
  const labels: Record<string, string> = {
    connected: "Connected",
    reconnecting: "Reconnecting",
    disconnected: "Disconnected",
    complete: "Complete",
  };
  return (
    <div className="flex items-center gap-1.5 text-xs mono" style={{ color: "var(--muted-foreground)" }}>
      <span className={`size-1.5 rounded-full ${colors[wsStatus] ?? "bg-zinc-600"}`} />
      <span>{labels[wsStatus] ?? wsStatus}</span>
    </div>
  );
}

export default function Navbar() {
  const loc = useLocation();
  const segments = loc.pathname.split("/").filter(Boolean);

  return (
    <header
      className="flex items-center justify-between px-4 h-11 shrink-0 border-b"
      style={{ borderColor: "var(--border)", background: "var(--card)" }}
    >
      <div className="flex items-center gap-4">
        <Link to="/" className="flex items-center gap-2 group">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="5.5" cy="17.5" r="3.5" />
            <circle cx="18.5" cy="17.5" r="3.5" />
            <path d="M5.5 17.5L10 5.5h4l4 8.5" />
            <path d="M10 5.5l4 8.5" />
            <circle cx="12" cy="5.5" r="1" />
          </svg>
          <span className="text-sm font-bold tracking-tight" style={{ fontFamily: "var(--font-sans)", color: "var(--foreground)" }}>
            BikeSim
          </span>
        </Link>
        {segments.length > 0 && (
          <nav className="flex items-center gap-1 text-xs" style={{ color: "var(--muted-foreground)" }}>
            <span>/</span>
            {segments.map((seg, i) => (
              <span key={i} className="flex items-center gap-1">
                <span className="capitalize">{decodeURIComponent(seg).replace(/-/g, " ")}</span>
                {i < segments.length - 1 && <span>/</span>}
              </span>
            ))}
          </nav>
        )}
      </div>
      <div className="flex items-center gap-4">
        <WsIndicator />
        <span className="text-xs mono px-1.5 py-0.5 rounded" style={{ background: "var(--secondary)", color: "var(--muted-foreground)" }}>
          Mock Mode
        </span>
      </div>
    </header>
  );
}
