import { useParams, Link } from "react-router";
import { useSimulation, useRoute } from "../hooks/useStore";
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";

function fmtTime(s: number) {
  if (!isFinite(s)) return "--";
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  return h > 0 ? `${h}h ${m}m ${sec}s` : `${m}m ${sec}s`;
}

function safe(n: number, dec = 1): string {
  return isFinite(n) ? n.toFixed(dec) : "--";
}

export default function Results() {
  const { simId } = useParams<{ simId: string }>();
  const sim = useSimulation(simId);
  const route = useRoute(sim?.config.routeId);

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

  if (sim.status !== "complete") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 text-sm">
        <div style={{ color: "var(--muted-foreground)" }}>
          Simulation is <strong style={{ color: "var(--foreground)" }}>{sim.status}</strong> — results not yet available.
        </div>
        <Link
          to={`/simulations/${sim.id}/live`}
          className="px-3 py-1.5 text-xs rounded"
          style={{ background: "var(--primary)", color: "var(--primary-foreground)" }}
        >
          Go to Live View →
        </Link>
      </div>
    );
  }

  const summary = sim.summary!;
  const history = sim.history;

  // Downsample history for chart (max 400 points)
  const step = Math.max(1, Math.floor(history.length / 400));
  const chartData = history.filter((_, i) => i % step === 0).map((p) => ({
    t: Math.round(p.t),
    target: Math.round(p.targetPower),
    realized: Math.round(p.realizedPower),
    speed: parseFloat((p.speed * 3.6).toFixed(1)),
    elev: Math.round(p.elevation),
    grade: parseFloat(p.grade.toFixed(1)),
  }));

  return (
    <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs mb-1" style={{ color: "var(--muted-foreground)" }}>
            <Link to="/" className="hover:underline">Dashboard</Link>
            {" / "}
            <Link to={`/routes/${sim.config.routeId}`} className="hover:underline">Route</Link>
            {" / "}
            Results
          </div>
          <h1 className="text-xl font-bold" style={{ fontFamily: "var(--font-sans)" }}>
            Simulation Results
          </h1>
          <p className="text-xs mt-1 mono" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            {sim.routeName} · {sim.id}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to={`/routes/${sim.config.routeId}/configure`}
            className="px-3 py-1.5 text-xs rounded border"
            style={{ border: "1px solid var(--border)", color: "var(--foreground)" }}
          >
            New simulation →
          </Link>
        </div>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-6 gap-px" style={{ background: "var(--border)" }}>
        {[
          { label: "Finish Time", value: fmtTime(summary.totalTimeS), mono: true },
          { label: "Distance", value: `${safe(summary.totalDistKm)} km`, mono: true },
          { label: "Avg Speed", value: `${safe(summary.avgSpeedKph)} kph`, mono: true },
          { label: "Avg Realized Power", value: `${safe(summary.avgRealizedPower, 0)} W`, mono: true, highlight: true },
          { label: "Norm. Power", value: `${safe(summary.normPower, 0)} W`, mono: true },
          { label: "Total Energy", value: `${safe(summary.totalEnergyKj, 1)} kJ`, mono: true },
        ].map((s) => (
          <div key={s.label} className="px-4 py-3" style={{ background: "var(--card)" }}>
            <div className="text-xs uppercase tracking-widest mb-1" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              {s.label}
            </div>
            <div
              className="text-xl font-semibold mono"
              style={{
                color: s.highlight ? "var(--primary)" : "var(--foreground)",
                fontFamily: s.mono ? "var(--font-mono)" : "var(--font-sans)",
              }}
            >
              {s.value}
            </div>
          </div>
        ))}
      </div>

      {/* Power analysis chart */}
      <div className="border" style={{ border: "1px solid var(--border)", background: "var(--card)" }}>
        <div className="px-4 py-2 border-b flex justify-between items-center" style={{ borderColor: "var(--border)" }}>
          <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            Target vs Realized Power — Full Race
          </span>
          <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
            Force-limited sections show realized below target
          </span>
        </div>
        <div className="p-4" style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" vertical={false} />
              <XAxis
                dataKey="t"
                tick={{ fill: "#526278", fontSize: 10, fontFamily: "JetBrains Mono" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={fmtTime}
                interval="preserveStartEnd"
              />
              <YAxis
                yAxisId="power"
                tick={{ fill: "#526278", fontSize: 10, fontFamily: "JetBrains Mono" }}
                tickLine={false}
                axisLine={false}
                width={40}
                tickFormatter={(v) => `${v}W`}
              />
              <YAxis
                yAxisId="elev"
                orientation="right"
                tick={{ fill: "#526278", fontSize: 10, fontFamily: "JetBrains Mono" }}
                tickLine={false}
                axisLine={false}
                width={44}
                tickFormatter={(v) => `${v}m`}
              />
              <Tooltip
                contentStyle={{ background: "#0c1018", border: "1px solid #1a2638", borderRadius: 2, fontSize: 10 }}
                itemStyle={{ fontFamily: "JetBrains Mono" }}
                labelFormatter={(v) => fmtTime(Number(v))}
              />
              <Legend wrapperStyle={{ fontSize: 10, fontFamily: "JetBrains Mono", color: "#526278" }} />
              <Area yAxisId="elev" type="monotone" dataKey="elev" fill="#ffffff10" stroke="#ffffff40" strokeWidth={1.5} dot={false} name="Elevation (m)" />
              <Line yAxisId="power" type="monotone" dataKey="target" stroke="#38bdf844" strokeWidth={1} dot={false} name="Target (W)" strokeDasharray="4 2" />
              <Line yAxisId="power" type="monotone" dataKey="realized" stroke="#38bdf8" strokeWidth={1.5} dot={false} name="Realized (W)" />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Speed chart */}
        <div className="border" style={{ border: "1px solid var(--border)", background: "var(--card)" }}>
          <div className="px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
            <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              Speed Profile
            </span>
          </div>
          <div className="p-4" style={{ height: 160 }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" vertical={false} />
                <XAxis dataKey="t" tick={{ fill: "#526278", fontSize: 9, fontFamily: "JetBrains Mono" }} tickLine={false} axisLine={false} tickFormatter={fmtTime} interval="preserveStartEnd" />
                <YAxis tick={{ fill: "#526278", fontSize: 9, fontFamily: "JetBrains Mono" }} tickLine={false} axisLine={false} width={34} tickFormatter={(v) => `${v}`} />
                <Tooltip contentStyle={{ background: "#0c1018", border: "1px solid #1a2638", borderRadius: 2, fontSize: 10 }} itemStyle={{ fontFamily: "JetBrains Mono" }} labelFormatter={(v) => fmtTime(Number(v))} />
                <Line type="monotone" dataKey="speed" stroke="#22c55e" strokeWidth={1.5} dot={false} name="kph" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Segment analysis */}
        <div className="border" style={{ border: "1px solid var(--border)", background: "var(--card)" }}>
          <div className="px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
            <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
              Segment Analysis
            </span>
          </div>
          <div className="divide-y" style={{ borderColor: "var(--border)" }}>
            {summary.segments.map((seg) => (
              <div key={seg.name} className="px-4 py-3">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-sm font-medium" style={{ color: "var(--foreground)" }}>
                    {seg.name}
                  </span>
                  <span className="text-xs mono" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                    {safe(seg.distStartKm)}–{safe(seg.distEndKm)} km
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { label: "Time", value: fmtTime(seg.timeS) },
                    { label: "Avg Power", value: `${safe(seg.avgRealizedPower, 0)} W` },
                    { label: "Avg Speed", value: `${safe(seg.avgSpeedKph)} kph` },
                  ].map((s) => (
                    <div key={s.label}>
                      <div className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                        {s.label}
                      </div>
                      <div className="text-sm mono font-medium" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
                        {s.value}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Config recap */}
      <div className="border" style={{ border: "1px solid var(--border)", background: "var(--card)" }}>
        <div className="px-4 py-2 border-b" style={{ borderColor: "var(--border)" }}>
          <span className="text-xs uppercase tracking-widest" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
            Simulation Parameters
          </span>
        </div>
        <div className="grid grid-cols-4 gap-px" style={{ background: "var(--border)" }}>
          {[
            { label: "Rider Mass", value: `${sim.config.rider.mass} kg` },
            { label: "FTP", value: `${sim.config.rider.ftp} W` },
            { label: "CdA", value: `${sim.config.rider.cda} m²` },
            { label: "Crr", value: String(sim.config.rider.crr) },
            { label: "Wind Speed", value: `${sim.config.environment.windSpeed} m/s` },
            { label: "Wind Bearing", value: `${sim.config.environment.windBearing}°` },
            { label: "Target Power", value: `${sim.config.strategy.targetPower} W` },
            { label: "Strategy", value: sim.config.strategy.type.replace("_", " ") },
          ].map((s) => (
            <div key={s.label} className="px-4 py-3" style={{ background: "var(--card)" }}>
              <div className="text-xs uppercase tracking-widest mb-0.5" style={{ color: "var(--muted-foreground)", fontFamily: "var(--font-mono)" }}>
                {s.label}
              </div>
              <div className="text-sm mono font-medium" style={{ color: "var(--foreground)", fontFamily: "var(--font-mono)" }}>
                {s.value}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
