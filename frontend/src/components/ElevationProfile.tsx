import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine } from "recharts";
import type { Route } from "../lib/types";

function gradeColor(grade: number): string {
  if (grade > 10) return "#ef4444";
  if (grade > 6) return "#f59e0b";
  if (grade > 2) return "#22c55e";
  if (grade < -6) return "#a78bfa";
  return "#38bdf8";
}

interface Props {
  route: Route;
  currentDistKm?: number;
  heightPx?: number;
}

export default function ElevationProfile({ route, currentDistKm, heightPx = 120 }: Props) {
  const step = Math.max(1, Math.floor(route.points.length / 300));
  const data = route.points.filter((_, i) => i % step === 0).map((p) => ({
    dist: parseFloat(p.distance.toFixed(1)),
    elev: Math.round(p.elevation),
    grade: parseFloat(p.grade.toFixed(1)),
  }));

  const minElev = Math.max(0, route.minElevation - 50);
  const maxElev = route.maxElevation + 80;

  return (
    <div style={{ height: heightPx }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="elevGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a2638" vertical={false} />
          <XAxis
            dataKey="dist"
            tick={{ fill: "#526278", fontSize: 10, fontFamily: "JetBrains Mono" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}km`}
            interval="preserveStartEnd"
          />
          <YAxis
            domain={[minElev, maxElev]}
            tick={{ fill: "#526278", fontSize: 10, fontFamily: "JetBrains Mono" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}m`}
            width={44}
          />
          <Tooltip
            contentStyle={{ background: "#0c1018", border: "1px solid #1a2638", borderRadius: 2, fontSize: 11 }}
            labelStyle={{ color: "#8fa5bf", fontFamily: "JetBrains Mono" }}
            itemStyle={{ color: "#dce6f4", fontFamily: "JetBrains Mono" }}
            formatter={(v, name) => [name === "elev" ? `${v} m` : `${v}%`, name === "elev" ? "Elevation" : "Grade"]}
            labelFormatter={(v) => `${v} km`}
          />
          {currentDistKm !== undefined && (
            <ReferenceLine x={parseFloat(currentDistKm.toFixed(1))} stroke="#38bdf8" strokeWidth={1.5} strokeDasharray="4 2" />
          )}
          <Area
            type="monotone"
            dataKey="elev"
            stroke="#38bdf8"
            strokeWidth={1.5}
            fill="url(#elevGrad)"
            dot={false}
            activeDot={{ r: 3, fill: "#38bdf8", stroke: "none" }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
