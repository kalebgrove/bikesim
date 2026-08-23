import { Link } from "react-router";
import { useRoutes, useSimulations } from "../hooks/useStore";

function fmt(iso: string | null) {
  if (!iso) return "--";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}
function fmtTime(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h > 0 ? `${h}h ${m}m ${sec}s` : `${m}m ${sec}s`;
}

const statusColors: Record<string, string> = {
  running: "#22c55e",
  paused: "#f59e0b",
  complete: "#38bdf8",
  stopped: "#ef4444",
  idle: "#526278",
};

export default function Dashboard() {
  const routes = useRoutes();
  const sims = useSimulations();

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-10">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-sans)", color: "var(--foreground)" }}>
            BikeSim Dashboard
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--muted-foreground)" }}>
            Cycling race simulation — configure, run, and analyze physics-accurate ride models.
          </p>
        </div>
        <Link
          to="/upload"
          className="px-4 py-2 text-sm font-semibold rounded transition-opacity hover:opacity-90 active:opacity-75"
          style={{ background: "var(--primary)", color: "var(--primary-foreground)", fontFamily: "var(--font-sans)" }}
        >
          + Create New Simulation
        </Link>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-4 gap-px" style={{ background: "var(--border)" }}>
        {[
          { label: "Routes Loaded", value: routes.length },
          { label: "Simulations Run", value: sims.length },
          { label: "Completed", value: sims.filter((s) => s.status === "complete").length },
          { label: "Backend", value: "FastAPI" },
        ].map((stat) => (
          <div key={stat.label} className="px-5 py-4" style={{ background: "var(--card)" }}>
            <div className="text-xs uppercase tracking-widest mb-1" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              {stat.label}
            </div>
            <div className="text-2xl font-bold mono" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-5 gap-6">
        {/* Routes */}
        <section className="col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              Routes
            </h2>
            <Link to="/upload" className="text-xs hover:underline" style={{ color: "var(--primary)" }}>
              Upload GPX →
            </Link>
          </div>
          {routes.length === 0 ? (
            <div
              className="border rounded p-6 text-center text-sm"
              style={{ border: "1px dashed var(--border)", color: "var(--muted-foreground)" }}
            >
              No routes yet. Upload a GPX file to start.
            </div>
          ) : (
            <div className="space-y-px">
              {routes.map((r) => (
                <Link
                  key={r.id}
                  to={`/routes/${r.id}`}
                  className="block px-4 py-3 border-b transition-colors hover:bg-secondary"
                  style={{ background: "var(--card)", borderColor: "var(--border)" }}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                        {r.name}
                      </div>
                      <div className="text-xs mt-0.5 mono space-x-3" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                        <span>{r.distance.toFixed(1)} km</span>
                        <span>↑{r.elevationGain} m</span>
                        <span>↓{r.elevationLoss} m</span>
                      </div>
                    </div>
                    <span
                      className="text-xs px-1.5 py-0.5 rounded shrink-0"
                      style={{ background: "var(--secondary)", color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}
                    >
                      {r.source === "demo" ? "demo" : "gpx"}
                    </span>
                  </div>
                  <div className="text-xs mt-1" style={{ color: "var(--muted-foreground)" }}>
                    Loaded {fmt(r.uploadedAt)}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* Simulations */}
        <section className="col-span-3 space-y-3">
          <h2 className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            Recent Simulations
          </h2>
          {sims.length === 0 ? (
            <div
              className="border rounded p-8 text-center"
              style={{ border: "1px dashed var(--border)", color: "var(--muted-foreground)" }}
            >
              <div className="text-3xl mb-3">⚡</div>
              <div className="text-sm font-medium mb-1" style={{ color: "var(--foreground)" }}>
                No simulations yet
              </div>
              <div className="text-xs mb-4">Pick a route, configure the rider and strategy, and run your first simulation.</div>
              <Link
                to="/upload"
                className="inline-block px-4 py-2 text-sm font-medium rounded"
                style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
              >
                Create New Simulation
              </Link>
            </div>
          ) : (
            <div className="space-y-px">
              {sims.map((sim) => (
                <div
                  key={sim.id}
                  className="flex items-center justify-between px-4 py-3 border-b"
                  style={{ background: "var(--card)", borderColor: "var(--border)" }}
                >
                  <div className="space-y-0.5">
                    <div className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                      {sim.routeName}
                    </div>
                    <div className="text-xs mono space-x-3" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                      <span>{sim.config.strategy.targetPower} W target</span>
                      {sim.summary && <span>{fmtTime(sim.summary.totalTimeS)} total</span>}
                      {sim.summary && <span>{sim.summary.avgSpeedKph.toFixed(1)} kph avg</span>}
                    </div>
                    <div className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                      {sim.startedAt ? `Started ${fmt(sim.startedAt)}` : `Created ${fmt(sim.createdAt)}`}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-1.5">
                      <span className="size-2 rounded-full" style={{ background: statusColors[sim.status] ?? "#526278" }} />
                      <span className="text-xs mono capitalize" style={{ color: statusColors[sim.status] ?? "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                        {sim.status}
                      </span>
                    </div>
                    {(sim.status === "running" || sim.status === "paused") && (
                      <Link
                        to={`/simulations/${sim.id}/live`}
                        className="text-xs px-2.5 py-1 rounded hover:opacity-90"
                        style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
                      >
                        Live →
                      </Link>
                    )}
                    {sim.status === "complete" && (
                      <Link
                        to={`/simulations/${sim.id}/results`}
                        className="text-xs px-2.5 py-1 rounded hover:opacity-90"
                        style={{ background: "var(--secondary)", color: "var(--primary)" }}
                      >
                        Results →
                      </Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {/* Future features notice */}
      <div
        className="border rounded px-4 py-3 text-xs"
        style={{ border: "1px solid var(--border)", background: "var(--muted)", color: "var(--muted-foreground)" }}
      >
        <strong style={{ color: "var(--foreground)" }}>Roadmap — not yet available:</strong>{" "}
        CFD aerodynamics visualization, reinforcement-learning pacing optimization, racing-line analysis, multi-rider simulation.
        These features are planned for future versions and are not accessible in this release.
      </div>
    </div>
  );
}
