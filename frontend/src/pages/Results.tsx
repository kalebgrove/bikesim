import { useParams, Link } from "react-router";
import { useSimulation } from "../hooks/useStore";
import { ComposedChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from "recharts";
import { ButtonLink, Callout, EmptyState, PageHeader, Panel, StatCell, StatStrip, StatusBadge, chartTheme } from "../components/ui";
import { fmtClock, fmtDuration, fixed } from "../lib/format";

const th = "label text-left font-medium px-4 h-9 border-b border-line";
const td = "num px-4 h-11 border-b border-line";

export default function Results() {
  const { simId } = useParams<{ simId: string }>();
  const sim = useSimulation(simId);

  if (!sim) {
    return (
      <EmptyState title="Simulation not found">
        <Link to="/" className="text-accent hover:underline">
          Back to overview
        </Link>
      </EmptyState>
    );
  }

  if (sim.status !== "complete" || !sim.summary) {
    return (
      <EmptyState title={`Results not available — run is ${sim.status}`}>
        <Link to={`/simulations/${sim.id}/live`} className="text-accent hover:underline">
          Open live view
        </Link>
      </EmptyState>
    );
  }

  const summary = sim.summary;
  const { rider, environment, strategy, simSettings } = sim.config;

  // Downsample history for charts (max ~400 points), plotted against distance
  const step = Math.max(1, Math.floor(sim.history.length / 400));
  const chartData = sim.history
    .filter((_, i) => i % step === 0)
    .map((p) => ({
      dist: parseFloat(p.dist.toFixed(2)),
      t: p.t,
      realized: Math.round(p.realizedPower),
      speed: parseFloat((p.speed * 3.6).toFixed(1)),
      elev: Math.round(p.elevation),
    }));

  const xAxis = (
    <XAxis
      dataKey="dist"
      type="number"
      domain={[0, "dataMax"]}
      tick={chartTheme.tick}
      tickLine={false}
      axisLine={false}
      tickFormatter={(v) => `${Number(v).toFixed(1)} km`}
    />
  );
  const tooltip = <Tooltip {...chartTheme.tooltip} labelFormatter={(v) => `${Number(v).toFixed(2)} km`} />;

  const params: [string, string][] = [
    ["System mass", `${rider.mass} kg`],
    ["FTP", `${rider.ftp} W`],
    ["CdA", `${rider.cda} m²`],
    ["Crr", String(rider.crr)],
    ["Wind speed", `${environment.windSpeed} m/s`],
    ["Wind from", `${environment.windBearing}°`],
    ["Temperature", `${environment.temperature} °C`],
    ["Air density ρ₀", `${environment.airDensity} kg/m³`],
    ["Strategy", strategy.type.replace("_", " ")],
    ["Target power", `${strategy.targetPower} W`],
    ["Time step", `${simSettings.timeStepS} s`],
    ["Tick interval", `${simSettings.tickIntervalMs} ms`],
  ];

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-6 space-y-6">
      <PageHeader
        eyebrow={<span className="num normal-case tracking-normal">Results · {sim.id}</span>}
        title={
          <span className="flex items-center gap-3">
            {sim.routeName} <StatusBadge status={sim.status} />
          </span>
        }
        subtitle={`Constant ${strategy.targetPower} W · ${rider.mass} kg · CdA ${rider.cda} m²`}
        actions={
          <>
            <ButtonLink to={`/simulations/${sim.id}/live`} variant="ghost">
              Live view
            </ButtonLink>
            <ButtonLink to={`/routes/${sim.config.routeId}/configure`} variant="primary">
              New run
            </ButtonLink>
          </>
        }
      />

      {summary.stopReason && (
        <Callout tone="warn" title="Stop reason">
          {summary.stopReason}
        </Callout>
      )}

      <StatStrip cols="grid-cols-2 md:grid-cols-4 xl:grid-cols-8">
        <StatCell label="Finish time" value={fmtClock(summary.totalTimeS)} tone="accent" size="lg" />
        <StatCell label="Distance" value={fixed(summary.totalDistKm, 2)} unit="km" />
        <StatCell label="Avg speed" value={fixed(summary.avgSpeedKph)} unit="km/h" />
        <StatCell label="Max speed" value={fixed(summary.maxSpeedKph)} unit="km/h" />
        <StatCell label="Avg power" value={fixed(summary.avgRealizedPower, 0)} unit="W" />
        <StatCell label="Norm. power" value={fixed(summary.normPower, 0)} unit="W" />
        <StatCell label="Mechanical work" value={fixed(summary.totalEnergyKj, 1)} unit="kJ" />
        <StatCell label="Metabolic" value={fixed(summary.kcalBurned, 0)} unit="kcal" />
      </StatStrip>

      <Panel title="Power vs elevation" meta="Realized pedal power against distance" bodyClassName="h-[280px] p-3">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} throttledEvents={[]} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={chartTheme.grid} vertical={false} />
            {xAxis}
            <YAxis yAxisId="power" tick={chartTheme.tick} tickLine={false} axisLine={false} width={48} tickFormatter={(v) => `${v} W`} />
            <YAxis yAxisId="elev" orientation="right" tick={chartTheme.tick} tickLine={false} axisLine={false} width={52} tickFormatter={(v) => `${v} m`} />
            {tooltip}
            <Legend wrapperStyle={{ fontSize: 11, fontFamily: "JetBrains Mono" }} iconType="plainline" />
            <Area yAxisId="elev" type="monotone" dataKey="elev" fill={chartTheme.colors.elev} fillOpacity={0.1} stroke={chartTheme.colors.elev} strokeOpacity={0.5} strokeWidth={1} dot={false} name="Elevation (m)" isAnimationActive={false} />
            <Line yAxisId="power" type="monotone" dataKey="realized" stroke={chartTheme.colors.power} strokeWidth={1.5} dot={false} name="Realized (W)" isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </Panel>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Panel title="Speed profile" meta="km/h" bodyClassName="h-[240px] p-3">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} throttledEvents={[]} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke={chartTheme.grid} vertical={false} />
              {xAxis}
              <YAxis tick={chartTheme.tick} tickLine={false} axisLine={false} width={40} />
              {tooltip}
              <Line type="monotone" dataKey="speed" stroke={chartTheme.colors.speed} strokeWidth={1.5} dot={false} name="Speed (km/h)" isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Segments" bodyClassName="overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead>
              <tr>
                <th className={th}>Segment</th>
                <th className={`${th} text-right`}>Range</th>
                <th className={`${th} text-right`}>Time</th>
                <th className={`${th} text-right`}>Power</th>
                <th className={`${th} text-right`}>Speed</th>
                <th className={`${th} text-right`}>Grade</th>
              </tr>
            </thead>
            <tbody>
              {summary.segments.map((seg) => (
                <tr key={seg.name} className="[&:last-child>td]:border-b-0">
                  <td className={`${td} font-sans font-medium`}>{seg.name}</td>
                  <td className={`${td} text-right text-dim`}>
                    {fixed(seg.distStartKm)}–{fixed(seg.distEndKm)} km
                  </td>
                  <td className={`${td} text-right`}>{fmtDuration(seg.timeS)}</td>
                  <td className={`${td} text-right`}>{fixed(seg.avgRealizedPower, 0)} W</td>
                  <td className={`${td} text-right`}>{fixed(seg.avgSpeedKph)} km/h</td>
                  <td className={`${td} text-right`}>{fixed(seg.avgGrade)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          {summary.segments.length === 0 && <EmptyState title="No segment data" />}
        </Panel>
      </div>

      <Panel title="Run parameters" bodyClassName="">
        <dl className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-6 gap-px bg-line">
          {params.map(([k, v]) => (
            <div key={k} className="bg-panel px-4 py-3">
              <dt className="label">{k}</dt>
              <dd className="num text-[13px] text-fg mt-1 capitalize">{v}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </div>
  );
}
