import { NavLink } from "react-router";
import type { ReactNode } from "react";
import { useRoutes, useSimulations } from "../hooks/useStore";
import { useSimEngineContext } from "../lib/simEngineContext";

const navItem = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2.5 h-8 px-2.5 rounded-md text-[13px] transition-colors ${
    isActive ? "bg-panel-2 text-fg" : "text-dim hover:text-fg hover:bg-panel-2/60"
  }`;

const dotColor: Record<string, string> = {
  running: "bg-ok",
  paused: "bg-warn",
  complete: "bg-accent",
  stopped: "bg-err",
};

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-0.5">
      <div className="label px-2.5 pb-1.5 pt-4">{title}</div>
      {children}
    </div>
  );
}

function Icon({ d }: { d: string }) {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
      <path d={d} />
    </svg>
  );
}

export default function Sidebar() {
  const routes = useRoutes();
  const sims = useSimulations();
  const { wsStatus } = useSimEngineContext();

  const engineLabel: Record<string, string> = {
    connected: "Streaming",
    reconnecting: "Connecting…",
    disconnected: "Idle",
    complete: "Run complete",
  };
  const engineDot: Record<string, string> = {
    connected: "bg-ok",
    reconnecting: "bg-warn animate-pulse",
    disconnected: "bg-faint",
    complete: "bg-accent",
  };

  return (
    <aside className="w-60 shrink-0 bg-panel border-r border-line flex flex-col">
      <NavLink to="/" className="flex items-center gap-2.5 h-14 px-4 border-b border-line">
        <div className="size-7 rounded-md bg-accent-strong grid place-items-center">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="5.5" cy="17" r="3.5" />
            <circle cx="18.5" cy="17" r="3.5" />
            <path d="M5.5 17l4-9h5l4 9M9.5 8l5 9M8 5h3" />
          </svg>
        </div>
        <div className="leading-tight">
          <div className="text-[14px] font-semibold text-fg">BikeSim</div>
          <div className="text-[11px] text-faint">Simulation Engine</div>
        </div>
      </NavLink>

      <nav className="flex-1 overflow-y-auto px-2 py-2">
        <div className="space-y-0.5">
          <NavLink to="/" end className={navItem}>
            <Icon d="M3 12l9-8 9 8M5 10v10h14V10" />
            Overview
          </NavLink>
          <NavLink to="/upload" className={navItem}>
            <Icon d="M12 16V4m0 0l-4 4m4-4l4 4M4 16v4h16v-4" />
            Import GPX
          </NavLink>
        </div>

        <Section title="Routes">
          {routes.length === 0 && <div className="px-2.5 text-xs text-faint">No routes loaded</div>}
          {routes.map((r) => (
            <NavLink key={r.id} to={`/routes/${r.id}`} className={navItem}>
              <Icon d="M4 19c4 0 4-6 8-6s4-8 8-8" />
              <span className="truncate flex-1">{r.name}</span>
              <span className="num text-[11px] text-faint">{r.distance.toFixed(1)}</span>
            </NavLink>
          ))}
        </Section>

        {sims.length > 0 && (
          <Section title="Recent runs">
            {sims.slice(0, 6).map((s) => (
              <NavLink
                key={s.id}
                to={s.status === "complete" ? `/simulations/${s.id}/results` : `/simulations/${s.id}/live`}
                className={navItem}
              >
                <span className={`size-1.5 rounded-full shrink-0 ml-1 mr-1 ${dotColor[s.status] ?? "bg-faint"}`} />
                <span className="truncate flex-1">{s.routeName}</span>
                <span className="num text-[11px] text-faint">{s.config.strategy.targetPower} W</span>
              </NavLink>
            ))}
          </Section>
        )}
      </nav>

      <div className="border-t border-line px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`size-2 rounded-full ${engineDot[wsStatus] ?? "bg-faint"}`} />
          <span className="text-xs text-dim">Engine · {engineLabel[wsStatus] ?? wsStatus}</span>
        </div>
        <span className="num text-[11px] text-faint">v1.0</span>
      </div>
    </aside>
  );
}
