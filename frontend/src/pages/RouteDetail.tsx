import { useParams, Link, useNavigate } from "react-router";
import { useRoute, useSimulations } from "../hooks/useStore";
import ElevationProfile from "../components/ElevationProfile";
import RouteSvg from "../components/RouteSvg";

function fmt(iso: string | null) {
  if (!iso) return "--";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

const statusColors: Record<string, string> = {
  running: "#22c55e",
  paused: "#f59e0b",
  complete: "#38bdf8",
  stopped: "#ef4444",
  idle: "#526278",
};

export default function RouteDetail() {
  const { routeId } = useParams<{ routeId: string }>();
  const route = useRoute(routeId);
  const allSims = useSimulations();
  const navigate = useNavigate();

  if (!route) {
    return (
      <div className="flex items-center justify-center h-64 text-sm" style={{ color: "var(--muted-foreground)" }}>
        Route not found.{" "}
        <Link to="/upload" className="ml-2 underline" style={{ color: "var(--primary)" }}>
          Upload a GPX →
        </Link>
      </div>
    );
  }

  const routeSims = allSims.filter((s) => s.routeId === route.id);

  return (
    <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs mb-1" style={{ color: "var(--muted-foreground)" }}>
            <Link to="/" className="hover:underline">Dashboard</Link>
            {" / "}
            <span>Routes</span>
          </div>
          <h1 className="text-xl font-bold" style={{ fontFamily: "var(--font-sans)" }}>
            {route.name}
          </h1>
          <div className="text-xs mt-1 mono space-x-3" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            <span>Loaded {fmt(route.uploadedAt)}</span>
            <span className="uppercase px-1 py-0.5 rounded" style={{ background: "var(--secondary)" }}>
              {route.source}
            </span>
          </div>
        </div>
        <Link
          to={`/routes/${route.id}/configure`}
          className="px-4 py-2 text-sm font-semibold rounded hover:opacity-90 transition-opacity"
          style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
        >
          Configure Simulation →
        </Link>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Map */}
        <div className="col-span-2 space-y-4">
          <div
            className="border overflow-hidden"
            style={{ border: "1px solid var(--border)", background: "var(--card)", height: 340 }}
          >
            <div className="px-3 py-2 border-b flex items-center justify-between" style={{ borderColor: "var(--border)" }}>
              <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                Route Map
              </span>
              <span className="text-xs mono" style={{ color: "var(--muted-foreground)" }}>
                {route.points.length} track points
              </span>
            </div>
            <div style={{ height: 300 }}>
              <RouteSvg route={route} width={700} height={300} />
            </div>
          </div>

          {/* Elevation profile */}
          <div className="border" style={{ border: "1px solid var(--border)", background: "var(--card)" }}>
            <div className="px-3 py-2 border-b" style={{ borderColor: "var(--border)" }}>
              <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                Elevation Profile
              </span>
            </div>
            <div className="p-3">
              <ElevationProfile route={route} heightPx={140} />
            </div>
          </div>
        </div>

        {/* Stats panel */}
        <div className="space-y-4">
          <div className="border" style={{ border: "1px solid var(--border)", background: "var(--card)" }}>
            <div className="px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
              <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                Route Statistics
              </span>
            </div>
            <div className="divide-y" style={{ borderColor: "var(--border)" }}>
              {[
                { label: "Distance", value: `${route.distance.toFixed(1)} km` },
                { label: "Elevation Gain", value: `${route.elevationGain.toLocaleString()} m` },
                { label: "Elevation Loss", value: `${route.elevationLoss.toLocaleString()} m` },
                { label: "Max Elevation", value: `${route.maxElevation.toLocaleString()} m` },
                { label: "Min Elevation", value: `${route.minElevation.toLocaleString()} m` },
                {
                  label: "Avg Gradient",
                  value: `${((route.elevationGain / (route.distance * 1000)) * 100).toFixed(2)}%`,
                },
              ].map((stat) => (
                <div key={stat.label} className="flex items-center justify-between px-4 py-2.5">
                  <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                    {stat.label}
                  </span>
                  <span className="text-sm mono font-medium" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
                    {stat.value}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Grade distribution */}
          <div className="border px-4 py-3 space-y-2" style={{ border: "1px solid var(--border)", background: "var(--card)" }}>
            <div className="text-xs uppercase tracking-widest mb-3" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              Grade Distribution
            </div>
            {[
              { label: ">10%", color: "#ef4444" },
              { label: "6–10%", color: "#f59e0b" },
              { label: "2–6%", color: "#86efac" },
              { label: "-2–2%", color: "#475569" },
              { label: "Descent", color: "#a78bfa" },
            ].map((b) => {
              const countFn = (g: number) => {
                if (b.label === ">10%") return g > 10;
                if (b.label === "6–10%") return g >= 6 && g <= 10;
                if (b.label === "2–6%") return g >= 2 && g < 6;
                if (b.label === "-2–2%") return g >= -2 && g < 2;
                return g < -2;
              };
              const count = route.points.filter((p) => countFn(p.grade)).length;
              const pct = (count / route.points.length) * 100;
              return (
                <div key={b.label} className="space-y-1">
                  <div className="flex justify-between text-xs" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                    <span>{b.label}</span>
                    <span>{pct.toFixed(0)}%</span>
                  </div>
                  <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--secondary)" }}>
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: b.color }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Previous simulations */}
      {routeSims.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs uppercase tracking-widest font-semibold" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            Previous Simulations on This Route
          </h2>
          <div className="space-y-px">
            {routeSims.map((sim) => (
              <div key={sim.id} className="flex items-center justify-between px-4 py-3 border-b" style={{ background: "var(--card)", borderColor: "var(--border)" }}>
                <div>
                  <div className="text-sm font-medium mono" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
                    {sim.id}
                  </div>
                  <div className="text-xs mono space-x-3 mt-0.5" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                    <span>{sim.config.strategy.targetPower} W target</span>
                    <span>{sim.config.rider.mass} kg rider</span>
                    {sim.summary && <span>{sim.summary.avgSpeedKph.toFixed(1)} kph avg</span>}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full" style={{ background: statusColors[sim.status] ?? "#526278" }} />
                    <span className="text-xs capitalize" style={{ color: "var(--muted-foreground)" }}>
                      {sim.status}
                    </span>
                  </div>
                  {sim.status === "complete" && (
                    <Link to={`/simulations/${sim.id}/results`} className="text-xs px-2.5 py-1 rounded" style={{ background: "var(--secondary)", color: "var(--primary)" }}>
                      Results →
                    </Link>
                  )}
                  {(sim.status === "running" || sim.status === "paused") && (
                    <Link to={`/simulations/${sim.id}/live`} className="text-xs px-2.5 py-1 rounded" style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}>
                      Live →
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
