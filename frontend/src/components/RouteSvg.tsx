import type { Route } from "../lib/types";

interface Props {
  route: Route;
  currentDistKm?: number;
  hoverDistKm?: number | null;
  onHoverDistKm?: (distKm: number | null) => void;
  width?: number;
  height?: number;
}

function gradeStroke(grade: number): string {
  if (grade > 10) return "#ef4444";
  if (grade > 6) return "#f59e0b";
  if (grade > 2) return "#86efac";
  if (grade < -5) return "#a78bfa";
  return "#475569";
}

export default function RouteSvg({ route, currentDistKm, hoverDistKm, onHoverDistKm, width = 400, height = 300 }: Props) {
  if (route.points.length < 2) return null;

  // Project lat/lon to screen coords
  const lats = route.points.map((p) => p.lat);
  const lons = route.points.map((p) => p.lon);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);

  const pad = 24;
  const scaleX = (width - pad * 2) / (maxLon - minLon || 1);
  const scaleY = (height - pad * 2) / (maxLat - minLat || 1);
  const scale = Math.min(scaleX, scaleY);

  // Center the projected route within the SVG
  const routeW = (maxLon - minLon) * scale;
  const routeH = (maxLat - minLat) * scale;
  const offsetX = (width - routeW) / 2;
  const offsetY = (height - routeH) / 2;

  function project(lat: number, lon: number): [number, number] {
    const x = offsetX + (lon - minLon) * scale;
    const y = height - offsetY - (lat - minLat) * scale;
    return [x, y];
  }

  // Downsample for SVG performance
  const step = Math.max(1, Math.floor(route.points.length / 500));
  const pts = route.points.filter((_, i) => i % step === 0);

  // Build colored segments
  const segments: { x1: number; y1: number; x2: number; y2: number; color: string }[] = [];
  for (let i = 1; i < pts.length; i++) {
    const [x1, y1] = project(pts[i - 1].lat, pts[i - 1].lon);
    const [x2, y2] = project(pts[i].lat, pts[i].lon);
    segments.push({ x1, y1, x2, y2, color: gradeStroke(pts[i].grade) });
  }

  // Completed portion
  let completedUpTo = -1;
  if (currentDistKm !== undefined) {
    for (let i = 0; i < pts.length; i++) {
      if (pts[i].distance <= currentDistKm) completedUpTo = i;
    }
  }

  // Rider position
  let riderX = -100, riderY = -100;
  if (currentDistKm !== undefined && completedUpTo >= 0) {
    const pt = pts[Math.min(completedUpTo, pts.length - 1)];
    [riderX, riderY] = project(pt.lat, pt.lon);
  }

  const [startX, startY] = project(pts[0].lat, pts[0].lon);
  const [endX, endY] = project(pts[pts.length - 1].lat, pts[pts.length - 1].lon);

  // Projected points for nearest-point lookup on hover
  const projected = pts.map((p) => ({ ...p, ...{ px: project(p.lat, p.lon)[0], py: project(p.lat, p.lon)[1] } }));

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    if (!onHoverDistKm) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * width;
    const my = ((e.clientY - rect.top) / rect.height) * height;
    let best = projected[0];
    let bestD = Infinity;
    for (const p of projected) {
      const d = (p.px - mx) ** 2 + (p.py - my) ** 2;
      if (d < bestD) {
        bestD = d;
        best = p;
      }
    }
    onHoverDistKm(best.distance);
  }

  function handleMouseLeave() {
    onHoverDistKm?.(null);
  }

  // Hover marker position
  let hoverX = -100, hoverY = -100;
  if (hoverDistKm != null) {
    for (let i = 0; i < pts.length; i++) {
      if (pts[i].distance <= hoverDistKm) {
        [hoverX, hoverY] = project(pts[i].lat, pts[i].lon);
      }
    }
    if (hoverX < 0 && pts.length > 0) {
      [hoverX, hoverY] = project(pts[0].lat, pts[0].lon);
    }
  }

  return (
    <svg
      width="100%"
      height="100%"
      viewBox={`0 0 ${width} ${height}`}
      style={{ background: "#080b10" }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
    >
      {/* Grid lines */}
      {[1, 2, 3, 4].map((i) => (
        <line
          key={i}
          x1={offsetX}
          y1={offsetY + ((height - offsetY * 2) / 4) * i}
          x2={offsetX + routeW}
          y2={offsetY + ((height - offsetY * 2) / 4) * i}
          stroke="#1a2638"
          strokeWidth={0.5}
        />
      ))}

      {/* Route segments colored by grade */}
      {segments.map((s, i) => (
        <line
          key={i}
          x1={s.x1}
          y1={s.y1}
          x2={s.x2}
          y2={s.y2}
          stroke={s.color}
          strokeWidth={i <= completedUpTo ? 2.5 : 1.5}
          strokeOpacity={i <= completedUpTo ? 1 : 0.4}
        />
      ))}

      {/* Start marker */}
      <circle cx={startX} cy={startY} r={5} fill="#22c55e" />
      <text x={startX + 7} y={startY + 4} fill="#22c55e" fontSize={10} fontFamily="JetBrains Mono">
        START
      </text>

      {/* End marker */}
      <circle cx={endX} cy={endY} r={5} fill="#ef4444" />
      <text x={endX + 7} y={endY + 4} fill="#ef4444" fontSize={10} fontFamily="JetBrains Mono">
        FINISH
      </text>

      {/* Rider marker */}
      {currentDistKm !== undefined && riderX > 0 && (
        <>
          <circle cx={riderX} cy={riderY} r={10} fill="#38bdf8" fillOpacity={0.15} />
          <circle cx={riderX} cy={riderY} r={5} fill="#38bdf8" />
          <circle cx={riderX} cy={riderY} r={3} fill="#fff" />
        </>
      )}

      {/* Hover marker */}
      {hoverDistKm != null && hoverX > 0 && (
        <>
          <circle cx={hoverX} cy={hoverY} r={4} fill="#f59e0b" fillOpacity={0.3} />
          <circle cx={hoverX} cy={hoverY} r={2.5} fill="#f59e0b" />
        </>
      )}

      {/* Grade legend */}
      {[
        { color: "#ef4444", label: ">10%" },
        { color: "#f59e0b", label: "6–10%" },
        { color: "#86efac", label: "2–6%" },
        { color: "#475569", label: "Flat" },
        { color: "#a78bfa", label: "Descent" },
      ].map((item, i) => (
        <g key={i} transform={`translate(${pad}, ${pad + i * 14})`}>
          <rect width={8} height={3} fill={item.color} y={2} rx={1} />
          <text x={12} y={8} fill="#526278" fontSize={9} fontFamily="JetBrains Mono">
            {item.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
