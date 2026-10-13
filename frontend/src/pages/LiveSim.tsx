import { useState } from "react";
import { useParams, Link } from "react-router";
import { useSimulation, useRoute } from "../hooks/useStore";
import { useSimEngineContext } from "../lib/simEngineContext";
import RouteSvg from "../components/RouteSvg";
import ElevationProfile from "../components/ElevationProfile";
import { Button, ButtonLink, Callout, EmptyState, Panel, StatCell, StatStrip, StatusBadge, chartTheme } from "../components/ui";
import { fmtClock, fixed } from "../lib/format";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";

const wsLabel: Record<string, string> = {
  connected: "Stream connected",
  reconnecting: "Connecting…",
  disconnected: "Stream closed",
  complete: "Stream complete",
};

/** Signed horizontal bar centred on zero: resistive forces point right, assisting forces left. */
function ForceBar({ label, value, scale, color }: { label: string; value: number; scale: number; color: string }) {
  const pct = Math.min(50, (Math.abs(value) / scale) * 50);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-dim">{label}</span>
        <span className="num text-fg">{fixed(value, 1)} N</span>
      </div>
      <div className="relative h-2 rounded-full bg-panel-2">
        <div className="absolute inset-y-0 left-1/2 w-px bg-line-strong" />
        <div
          className="absolute inset-y-0 rounded-full transition-all duration-200"
          style={{ background: color, width: `${pct}%`, left: value >= 0 ? "50%" : `${50 - pct}%` }}
        />
      </div>
    </div>
  );
}

function MiniChart({
  data,
  dataKey,
  color,
  unit,
  reference,
}: {
  data: Record<string, number>[];
  dataKey: string;
  color: string;
  unit: string;
  reference?: number;
}) {
  if (data.length < 2) {
    return <div className="h-full grid place-items-center text-xs text-faint">Waiting for telemetry…</div>;
  }
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} throttledEvents={[]} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={chartTheme.grid} vertical={false} />
        <XAxis dataKey="t" tick={chartTheme.tick} tickLine={false} axisLine={false} tickFormatter={(v) => fmtClock(Number(v))} minTickGap={40} />
        <YAxis tick={chartTheme.tick} tickLine={false} axisLine={false} width={40} />
        <Tooltip {...chartTheme.tooltip} labelFormatter={(v) => fmtClock(Number(v))} formatter={(v) => [`${v} ${unit}`]} />
        {reference !== undefined && <ReferenceLine y={reference} stroke={color} strokeOpacity={0.4} strokeDasharray="4 3" />}
        <Line type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export default function LiveSim() {
  const { simId } = useParams<{ simId: string }>();
  const sim = useSimulation(simId);
  const route = useRoute(sim?.config.routeId);
  const { wsStatus, pause, resume, restart, hardStop } = useSimEngineContext();
  const [hoverDistKm, setHoverDistKm] = useState<number | null>(null);

  if (!sim) {
    return (
      <EmptyState title="Simulation not found">
        <Link to="/" className="text-accent hover:underline">
          Back to overview
        </Link>
      </EmptyState>
    );
  }

  const latest = sim.latest;
  const history = sim.history;
  const totalKm = route?.distance ?? NaN;
  const progress = latest && isFinite(totalKm) ? Math.min(100, (latest.dist / totalKm) * 100) : 0;
  const { timeStepS, tickIntervalMs } = sim.config.simSettings;

  // Downsample for chart performance
  const chartStep = Math.max(1, Math.floor(history.length / 600));
  const chartData = history
    .filter((_, i) => i % chartStep === 0)
    .map((p) => ({
      t: Math.floor(p.t),
      realized: Math.round(p.realizedPower),
      speed: parseFloat((p.speed * 3.6).toFixed(1)),
    }));

  const forces = latest ? [latest.gravForce, latest.aeroForce, latest.rollingForce] : [];
  const forceScale = Math.max(50, ...forces.map(Math.abs));
  const active = sim.status === "running" || sim.status === "paused";

  return (
    <div className="max-w-[1600px] mx-auto px-6 py-6 space-y-5">
      {/* Toolbar */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="min-w-0">
          <div className="label mb-1">Live run</div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight truncate">{sim.routeName}</h1>
            <StatusBadge status={sim.status} />
          </div>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-faint mr-2 flex items-center gap-1.5">
            <span className={`size-1.5 rounded-full ${wsStatus === "connected" ? "bg-ok" : wsStatus === "reconnecting" ? "bg-warn animate-pulse" : "bg-faint"}`} />
            {wsLabel[wsStatus] ?? wsStatus}
          </span>
          {sim.status === "running" && <Button onClick={pause}>Pause</Button>}
          {sim.status === "paused" && (
            <Button variant="primary" onClick={resume}>
              Resume
            </Button>
          )}
          {active && (
            <Button variant="danger" onClick={() => hardStop(sim.id)}>
              Stop
            </Button>
          )}
          {!active && <Button onClick={() => restart(sim.id)}>Restart</Button>}
          {sim.status === "complete" ? (
            <ButtonLink to={`/simulations/${sim.id}/results`} variant="primary">
              View results
            </ButtonLink>
          ) : (
            <ButtonLink to={`/routes/${sim.config.routeId}/configure`} variant="ghost">
              New config
            </ButtonLink>
          )}
        </div>
      </div>

      {/* Progress */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs">
          <span className="num text-dim">
            {fixed(latest?.dist, 2)} / {fixed(totalKm, 2)} km
          </span>
          <span className="num text-dim">{progress.toFixed(1)}%</span>
        </div>
        <div className="h-1.5 rounded-full bg-panel-2 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${sim.status === "complete" ? "bg-ok" : sim.status === "stopped" ? "bg-err" : "bg-accent"}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <StatStrip cols="grid-cols-2 md:grid-cols-4 2xl:grid-cols-8">
        <StatCell label="Elapsed" value={fmtClock(latest?.t ?? 0)} size="lg" />
        <StatCell label="Speed" value={fixed(latest ? latest.speed * 3.6 : NaN)} unit="km/h" tone="accent" size="lg" />
        <StatCell
          label="Realized power"
          value={latest ? Math.round(latest.realizedPower) : "--"}
          unit="W"
          tone={latest?.forceLimited ? "warn" : "default"}
          size="lg"
          sub={`target ${sim.config.strategy.targetPower} W`}
        />
        <StatCell label="Grade" value={fixed(latest?.grade)} unit="%" tone={(latest?.grade ?? 0) > 8 ? "warn" : "default"} size="lg" />
        <StatCell label="Elevation" value={fixed(latest?.elevation, 0)} unit="m" size="lg" />
        <StatCell label="Distance" value={fixed(latest?.dist, 2)} unit="km" size="lg" />
        <StatCell label="Mechanical work" value={fixed(latest?.totalEnergy, 1)} unit="kJ" size="lg" />
        <StatCell label="Metabolic" value={fixed(latest?.kcalBurned, 0)} unit="kcal" size="lg" />
      </StatStrip>

      {latest?.forceLimited && latest.limitReason && (
        <Callout tone="warn" title="Power limited">
          {latest.limitReason}
        </Callout>
      )}
      {sim.summary?.stopReason && (
        <Callout tone="err" title="Run stopped">
          {sim.summary.stopReason}
        </Callout>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_380px] gap-5">
        <div className="space-y-5 min-w-0">
          <Panel title="Track" meta="Hover the map or profile to inspect" bodyClassName="h-[420px]">
            {route ? (
              <RouteSvg route={route} currentDistKm={latest?.dist} hoverDistKm={hoverDistKm} onHoverDistKm={setHoverDistKm} width={800} height={420} />
            ) : (
              <EmptyState title="Route geometry not loaded" />
            )}
          </Panel>
          {route && (
            <Panel title="Elevation" bodyClassName="px-2 py-3">
              <ElevationProfile route={route} currentDistKm={latest?.dist} hoverDistKm={hoverDistKm} heightPx={130} gradientId="liveElev" />
            </Panel>
          )}
        </div>

        <div className="space-y-5">
          <Panel title="Force balance" meta="+ resists motion">
            <div className="space-y-4">
              <ForceBar label="Gravity" value={latest?.gravForce ?? 0} scale={forceScale} color="var(--color-grav)" />
              <ForceBar label="Aerodynamic drag" value={latest?.aeroForce ?? 0} scale={forceScale} color="var(--color-aero)" />
              <ForceBar label="Rolling resistance" value={latest?.rollingForce ?? 0} scale={forceScale} color="var(--color-roll)" />
            </div>
          </Panel>
          <Panel title="Power" meta="W" bodyClassName="h-[170px] p-2">
            <MiniChart data={chartData} dataKey="realized" color={chartTheme.colors.power} unit="W" reference={sim.config.strategy.targetPower} />
          </Panel>
          <Panel title="Speed" meta="km/h" bodyClassName="h-[170px] p-2">
            <MiniChart data={chartData} dataKey="speed" color={chartTheme.colors.speed} unit="km/h" />
          </Panel>
        </div>
      </div>

      <div className="num flex flex-wrap gap-x-6 gap-y-1 text-[11px] text-faint border-t border-line pt-3">
        <span>sim {sim.id}</span>
        <span>{history.length} ticks</span>
        <span>dt {timeStepS} s</span>
        <span>tick {tickIntervalMs} ms</span>
        <span>{((timeStepS / tickIntervalMs) * 1000).toFixed(0)}× real time</span>
      </div>
    </div>
  );
}
