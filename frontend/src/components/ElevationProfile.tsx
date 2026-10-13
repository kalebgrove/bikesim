import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";
import type { Route } from "../lib/types";
import { chartTheme } from "./ui";

interface Props {
  route: Route;
  currentDistKm?: number;
  hoverDistKm?: number | null;
  heightPx?: number;
  gradientId?: string;
}

export default function ElevationProfile({ route, currentDistKm, hoverDistKm, heightPx = 120, gradientId = "elevGrad" }: Props) {
  const color = chartTheme.colors.elev;
  const step = Math.max(1, Math.floor(route.points.length / 300));
  const data = route.points
    .filter((_, i) => i % step === 0)
    .map((p) => ({
      dist: parseFloat(p.distance.toFixed(2)),
      elev: Math.round(p.elevation),
      grade: parseFloat(p.grade.toFixed(1)),
    }));

  const minElev = Math.max(0, Math.floor((route.minElevation - 20) / 10) * 10);
  const maxElev = Math.ceil((route.maxElevation + 20) / 10) * 10;

  return (
    <div style={{ height: heightPx }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} throttledEvents={[]} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.28} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={chartTheme.grid} vertical={false} />
          <XAxis
            dataKey="dist"
            type="number"
            domain={[0, "dataMax"]}
            tick={chartTheme.tick}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${Number(v).toFixed(1)} km`}
          />
          <YAxis domain={[minElev, maxElev]} tick={chartTheme.tick} tickLine={false} axisLine={false} tickFormatter={(v) => `${v} m`} width={52} />
          <Tooltip
            {...chartTheme.tooltip}
            formatter={(v, name) => [name === "elev" ? `${v} m` : `${v} %`, name === "elev" ? "Elevation" : "Grade"]}
            labelFormatter={(v) => `${Number(v).toFixed(2)} km`}
          />
          {hoverDistKm != null && <ReferenceLine x={hoverDistKm} stroke={chartTheme.colors.warn} strokeDasharray="3 3" />}
          {currentDistKm !== undefined && <ReferenceLine x={currentDistKm} stroke={chartTheme.colors.accent} strokeWidth={1.5} />}
          <Area
            type="monotone"
            dataKey="elev"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#${gradientId})`}
            dot={false}
            isAnimationActive={false}
            activeDot={{ r: 3, fill: chartTheme.colors.accent, stroke: "none" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
