import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router";
import { useSimulation, useRoute } from "../hooks/useStore";
import { useSimEngineContext } from "../lib/simEngineContext";
import TelemetryValue from "../components/TelemetryValue";
import RouteSvg from "../components/RouteSvg";
import ElevationProfile from "../components/ElevationProfile";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";

function fmtTime(s: number) {
  if (!isFinite(s)) return "--:--:--";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return [h > 0 ? String(h).padStart(2, "0") : null, String(m).padStart(2, "0"), String(sec).padStart(2, "0")]
    .filter(Boolean)
    .join(":");
}

const WS_COLORS: Record<string, string> = {
  connected: "#22c55e",
  reconnecting: "#f59e0b",
  disconnected: "#526278",
  complete: "#38bdf8",
};
const WS_LABELS: Record<string, string> = {
  connected: "WS Connected",
  reconnecting: "Reconnecting…",
  disconnected: "Disconnected",
  complete: "Stream Complete",
};

export default function LiveSim() {
  const { simId } = useParams<{ simId: string }>();
  const sim = useSimulation(simId);
  const route = useRoute(sim?.config.routeId);
  const { wsStatus, pause, resume, restart, hardStop } = useSimEngineContext();
  const navigate = useNavigate();
  const [hoverDistKm, setHoverDistKm] = useState<number | null>(null);

  if (!sim) {
    return (
      <div className="flex items-center justify-center h-64 text-sm" style={{ color: "var(--muted-foreground)" }}>
        Simulation not found.{" "}
        <Link to="/" className="ml-2 underline" style={{ color: "var(--primary)" }}>
          Dashboard →
        </Link>
      </div>
    );
  }

  const latest = sim.latest;
  const speedKph = latest ? latest.speed * 3.6 : 0;
  const history = sim.history;

  // Full history for live chart (downsample if >600 points for performance)
  const chartStep = Math.max(1, Math.floor(history.length / 600));
  const chartData = history.filter((_, i) => i % chartStep === 0).map((p) => ({
    t: Math.floor(p.t),
    target: Math.round(p.targetPower),
    realized: Math.round(p.realizedPower),
    speed: parseFloat((p.speed * 3.6).toFixed(1)),
    grade: parseFloat(p.grade.toFixed(1)),
  }));

  const complete = sim.status === "complete";
  const stopped = sim.status === "stopped";

  return (
    <div className="flex flex-col h-full overflow-hidden" style={{ minHeight: 0 }}>
      {/* Top status bar */}
      <div className="shrink-0 border-b" style={{ borderColor: "var(--border)", background: "var(--card)" }}>
        <div className="flex items-center gap-6 px-4 py-2">
          {/* WS status */}
          <div className="flex items-center gap-1.5">
            <span
              className="size-2 rounded-full"
              style={{
                background: WS_COLORS[wsStatus] ?? "#526278",
                boxShadow: wsStatus === "connected" ? "0 0 6px #22c55e88" : "none",
              }}
            />
            <span className="text-xs mono" style={{ color: WS_COLORS[wsStatus], fontFamily: "var(--font-mono)" }}>
              {WS_LABELS[wsStatus] ?? wsStatus}
            </span>
          </div>

          <div className="h-4 w-px" style={{ background: "var(--border)" }} />

          {/* Elapsed time */}
          <div className="flex items-baseline gap-1.5">
            <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              Elapsed
            </span>
            <span className="text-xl font-semibold mono" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
              {fmtTime(latest?.t ?? 0)}
            </span>
          </div>

          <div className="h-4 w-px" style={{ background: "var(--border)" }} />

          <div className="flex items-baseline gap-1.5">
            <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              Distance
            </span>
            <span className="text-xl font-semibold mono" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
              {isFinite(latest?.dist ?? NaN) ? (latest!.dist).toFixed(2) : "--"}
            </span>
            <span className="text-xs" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              / {route?.distance.toFixed(1) ?? "--"} km
            </span>
          </div>

          <div className="h-4 w-px" style={{ background: "var(--border)" }} />

          <div className="flex items-baseline gap-1.5">
            <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              Speed
            </span>
            <span className="text-xl font-semibold mono" style={{ color: "var(--primary)", fontFamily: "var(--font-mono)" }}>
              {isFinite(speedKph) ? speedKph.toFixed(1) : "--"}
            </span>
            <span className="text-xs" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              kph
            </span>
          </div>

          {/* Completion / progress */}
          {route && latest && (
            <div className="flex-1 mx-4">
              <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--secondary)" }}>
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, (latest.dist / route.distance) * 100).toFixed(1)}%`,
                    background: complete ? "#22c55e" : "var(--primary)",
                  }}
                />
              </div>
            </div>
          )}

          {complete && (
            <span className="text-xs px-2 py-1 rounded font-semibold" style={{ background: "#22c55e22", color: "#22c55e" }}>
              COMPLETE
            </span>
          )}
          {stopped && (
            <span className="text-xs px-2 py-1 rounded font-semibold" style={{ background: "#ef444422", color: "#ef4444" }}>
              STOPPED
            </span>
          )}

          <div className="ml-auto">
            <Link to={`/routes/${sim.config.routeId}`} className="text-xs" style={{ color: "var(--muted-foreground)" }}>
              {sim.routeName}
            </Link>
          </div>
        </div>
      </div>

      {/* Main area */}
      <div className="flex-1 overflow-hidden flex flex-col" style={{ minHeight: 0 }}>
        <div className="flex flex-1 overflow-hidden" style={{ minHeight: 0 }}>
          {/* Left: Telemetry panel */}
          <aside
            className="w-52 shrink-0 border-r flex flex-col overflow-y-auto"
            style={{ borderColor: "var(--border)", background: "var(--card)" }}
          >
            <div className="px-3 py-2 border-b" style={{ borderColor: "var(--border)" }}>
              <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                Telemetry
              </span>
            </div>
            <div className="p-3 space-y-4 flex-1">
              {/* Power comparison - KEY UI ELEMENT */}
              <div className="border rounded p-3 space-y-2" style={{ border: "1px solid var(--border)", background: "var(--secondary)" }}>
                <div className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                  Power
                </div>
                <div>
                  <div className="text-xs mb-0.5" style={{ color: "var(--muted-foreground)" }}>
                    Target (input)
                  </div>
                  <div className="text-2xl font-semibold mono" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
                    {latest?.targetPower ?? "--"} <span className="text-sm font-normal">W</span>
                  </div>
                </div>
                <div className="h-px" style={{ background: "var(--border)" }} />
                <div>
                  <div className="text-xs mb-0.5" style={{ color: "var(--muted-foreground)" }}>
                    Realized (physics)
                  </div>
                  <div
                    className="text-2xl font-semibold mono"
                    style={{
                      color: latest?.forceLimited ? "var(--accent)" : "var(--primary)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {latest ? Math.round(latest.realizedPower) : "--"} <span className="text-sm font-normal">W</span>
                  </div>
                </div>
                {latest?.forceLimited && (
                  <div
                    className="rounded px-2 py-1.5 text-xs space-y-0.5"
                    style={{ background: "rgba(245,158,11,0.12)", border: "1px solid rgba(245,158,11,0.3)" }}
                  >
                    <div className="font-semibold" style={{ color: "var(--accent)" }}>
                      ⚡ Force-Limited
                    </div>
                    <div style={{ color: "#c4832a" }}>{latest.limitReason}</div>
                  </div>
                )}
              </div>

              <TelemetryValue label="Elevation" value={latest?.elevation ?? 0} unit="m" decimals={0} />
              <TelemetryValue label="Grade" value={latest?.grade ?? 0} unit="%" decimals={1} warn={(latest?.grade ?? 0) > 8} />
              <TelemetryValue label="Grade Force" value={latest?.gravForce ?? 0} unit="N" decimals={0} />
              <TelemetryValue label="Aero Force" value={latest?.aeroForce ?? 0} unit="N" decimals={0} />
              <TelemetryValue label="Rolling Force" value={latest?.rollingForce ?? 0} unit="N" decimals={0} />
              <TelemetryValue label="Total Energy" value={latest?.totalEnergy ?? 0} unit="kJ" decimals={1} highlight />

              {/* Tick count */}
              <div className="pt-2 border-t" style={{ borderColor: "var(--border)" }}>
                <div className="text-xs" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                  Ticks received: {history.length}
                </div>
                <div className="text-xs" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                  Sim time: {fmtTime(latest?.t ?? 0)}
                </div>
              </div>
            </div>
          </aside>

          {/* Center: Route map */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {route ? (
              <>
                <div className="flex-1 overflow-hidden">
                  <RouteSvg
                    route={route}
                    currentDistKm={latest?.dist}
                    hoverDistKm={hoverDistKm}
                    onHoverDistKm={setHoverDistKm}
                    width={700}
                    height={300}
                  />
                </div>
                <div className="border-t px-3 py-2" style={{ borderColor: "var(--border)", background: "var(--muted)" }}>
                  <ElevationProfile route={route} currentDistKm={latest?.dist} hoverDistKm={hoverDistKm} heightPx={90} />
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center h-full text-sm" style={{ color: "var(--muted-foreground)" }}>
                Route not found
              </div>
            )}
          </div>

          {/* Right: Live power chart */}
          <aside
            className="w-64 shrink-0 border-l flex flex-col"
            style={{ borderColor: "var(--border)", background: "var(--card)" }}
          >
            <div className="px-3 py-2 border-b" style={{ borderColor: "var(--border)" }}>
              <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                Live Power
              </span>
            </div>
            <div className="flex-1 p-2">
              {chartData.length > 1 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" vertical={false} />
                    <XAxis
                      dataKey="t"
                      tick={{ fill: "#526278", fontSize: 9, fontFamily: "JetBrains Mono" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={(v) => fmtTime(v)}
                      interval="preserveStartEnd"
                    />
                    <YAxis
                      tick={{ fill: "#526278", fontSize: 9, fontFamily: "JetBrains Mono" }}
                      tickLine={false}
                      axisLine={false}
                      width={36}
                      tickFormatter={(v) => `${v}W`}
                    />
                    <Tooltip
                      contentStyle={{ background: "#0c1018", border: "1px solid #1a2638", borderRadius: 2, fontSize: 10 }}
                      itemStyle={{ fontFamily: "JetBrains Mono" }}
                      labelFormatter={(v) => fmtTime(Number(v))}
                    />
                    <ReferenceLine
                      y={sim.config.strategy.targetPower}
                      stroke="#38bdf855"
                      strokeDasharray="4 2"
                      label={{ value: "Target", fill: "#38bdf8", fontSize: 9 }}
                    />
                    <Line type="monotone" dataKey="target" stroke="#38bdf844" strokeWidth={1} dot={false} name="Target" />
                    <Line type="monotone" dataKey="realized" stroke="#38bdf8" strokeWidth={1.5} dot={false} name="Realized" />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-xs" style={{ color: "var(--muted-foreground)" }}>
                  Waiting for data…
                </div>
              )}
            </div>

            {/* Speed chart */}
            <div className="border-t" style={{ borderColor: "var(--border)" }}>
              <div className="px-3 py-2 border-b" style={{ borderColor: "var(--border)" }}>
                <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                  Speed
                </span>
              </div>
              <div style={{ height: 100 }} className="p-2">
                {chartData.length > 1 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" vertical={false} />
                      <XAxis dataKey="t" hide />
                      <YAxis tick={{ fill: "#526278", fontSize: 9, fontFamily: "JetBrains Mono" }} tickLine={false} axisLine={false} width={30} tickFormatter={(v) => `${v}`} />
                      <Tooltip contentStyle={{ background: "#0c1018", border: "1px solid #1a2638", borderRadius: 2, fontSize: 10 }} itemStyle={{ fontFamily: "JetBrains Mono" }} labelFormatter={(v) => fmtTime(Number(v))} />
                      <Line type="monotone" dataKey="speed" stroke="#22c55e" strokeWidth={1.5} dot={false} name="kph" />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-xs" style={{ color: "var(--muted-foreground)" }}>—</div>
                )}
              </div>
            </div>
          </aside>
        </div>

        {/* Controls */}
        <div
          className="shrink-0 border-t flex items-center gap-3 px-4 py-2"
          style={{ borderColor: "var(--border)", background: "var(--secondary)" }}
        >
          {sim.status === "running" && (
            <button
              onClick={pause}
              className="px-3 py-1.5 text-xs font-semibold rounded border hover:opacity-80 transition-opacity"
              style={{ border: "1px solid var(--border)", color: "var(--foreground)", background: "var(--card)" }}
            >
              ⏸ Pause
            </button>
          )}
          {sim.status === "paused" && (
            <button
              onClick={resume}
              className="px-3 py-1.5 text-xs font-semibold rounded hover:opacity-90 transition-opacity"
              style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
            >
              ▶ Resume
            </button>
          )}
          {(sim.status === "complete" || sim.status === "stopped") && (
            <button
              onClick={() => restart(sim.id)}
              className="px-3 py-1.5 text-xs font-semibold rounded hover:opacity-90 transition-opacity"
              style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
            >
              ↺ Restart
            </button>
          )}
          {(sim.status === "running" || sim.status === "paused") && (
            <button
              onClick={() => hardStop(sim.id)}
              className="px-3 py-1.5 text-xs font-semibold rounded border hover:opacity-80 transition-opacity"
              style={{ border: "1px solid #ef444466", color: "#ef4444", background: "transparent" }}
            >
              ■ Stop
            </button>
          )}
          {sim.status === "complete" && (
            <button
              onClick={() => navigate(`/simulations/${sim.id}/results`)}
              className="px-3 py-1.5 text-xs font-semibold rounded hover:opacity-90"
              style={{ background: "#22c55e22", color: "#22c55e", border: "1px solid #22c55e44" }}
            >
              View Results →
            </button>
          )}
          <Link to={`/routes/${sim.config.routeId}/configure`} className="text-xs hover:underline" style={{ color: "var(--muted-foreground)" }}>
            New config
          </Link>
          <div className="ml-auto text-xs mono" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            {sim.config.simSettings.timeStepS}s/tick · {sim.config.simSettings.tickIntervalMs}ms interval ·{" "}
            {((sim.config.simSettings.timeStepS / sim.config.simSettings.tickIntervalMs) * 1000).toFixed(0)}× realtime
          </div>
        </div>
      </div>
    </div>
  );
}
