import type { Route } from "../lib/types";
import { GRADE_BANDS, gradeBand } from "../lib/grade";

interface Props {
  route: Route;
  currentDistKm?: number;
  hoverDistKm?: number | null;
  onHoverDistKm?: (distKm: number | null) => void;
  width?: number;
  height?: number;
}

export default function RouteSvg({ route, currentDistKm, hoverDistKm, onHoverDistKm, width = 400, height = 300 }: Props) {
  if (route.points.length < 2) return null;

  // Equirectangular projection: a degree of longitude is cos(lat) times shorter than a degree of latitude
  const lats = route.points.map((p) => p.lat);
  const lons = route.points.map((p) => p.lon);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);
  const kx = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);

  const pad = 28;
  const scale = Math.min((width - pad * 2) / ((maxLon - minLon) * kx || 1), (height - pad * 2) / (maxLat - minLat || 1));
  const offsetX = (width - (maxLon - minLon) * kx * scale) / 2;
  const offsetY = (height - (maxLat - minLat) * scale) / 2;

  const project = (lat: number, lon: number): [number, number] => [
    offsetX + (lon - minLon) * kx * scale,
    height - offsetY - (lat - minLat) * scale,
  ];

  // Downsample for SVG performance
  const step = Math.max(1, Math.floor(route.points.length / 500));
  const pts = route.points.filter((_, i) => i % step === 0).map((p) => {
    const [x, y] = project(p.lat, p.lon);
    return { ...p, x, y };
  });

  /** Index of the last point at or before `distKm`. */
  const indexAt = (distKm: number) => {
    let idx = 0;
    for (let i = 0; i < pts.length; i++) if (pts[i].distance <= distKm) idx = i;
    return idx;
  };

  const riderIdx = currentDistKm !== undefined ? indexAt(currentDistKm) : -1;
  const hoverIdx = hoverDistKm != null ? indexAt(hoverDistKm) : -1;
  const start = pts[0];
  const end = pts[pts.length - 1];

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    if (!onHoverDistKm) return;
    const rect = e.currentTarget.getBoundingClientRect();
    // viewBox is scaled with preserveAspectRatio "meet": undo that scaling and centering
    const s = Math.min(rect.width / width, rect.height / height);
    const mx = (e.clientX - rect.left - (rect.width - width * s) / 2) / s;
    const my = (e.clientY - rect.top - (rect.height - height * s) / 2) / s;
    let best = pts[0];
    let bestD = Infinity;
    for (const p of pts) {
      const d = (p.x - mx) ** 2 + (p.y - my) ** 2;
      if (d < bestD) {
        bestD = d;
        best = p;
      }
    }
    onHoverDistKm(best.distance);
  }

  return (
    <svg
      width="100%"
      height="100%"
      viewBox={`0 0 ${width} ${height}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => onHoverDistKm?.(null)}
      className="block"
    >
      <defs>
        <pattern id="mapgrid" width="24" height="24" patternUnits="userSpaceOnUse">
          <path d="M24 0H0V24" fill="none" stroke="#1c212b" strokeWidth="1" />
        </pattern>
      </defs>
      <rect width={width} height={height} fill="url(#mapgrid)" />

      {/* Casing under the route for contrast */}
      <polyline points={pts.map((p) => `${p.x},${p.y}`).join(" ")} fill="none" stroke="#0b0d12" strokeWidth={6} strokeLinejoin="round" />

      {pts.slice(1).map((p, i) => (
        <line
          key={i}
          x1={pts[i].x}
          y1={pts[i].y}
          x2={p.x}
          y2={p.y}
          stroke={gradeBand(p.grade).color}
          strokeWidth={riderIdx >= 0 && i < riderIdx ? 3.5 : 2.5}
          strokeOpacity={riderIdx >= 0 && i >= riderIdx ? 0.35 : 1}
          strokeLinecap="round"
        />
      ))}

      <g fontSize={10} fontFamily="JetBrains Mono" fontWeight={600}>
        <circle cx={start.x} cy={start.y} r={5} fill="#34d399" stroke="#0b0d12" strokeWidth={2} />
        <text x={start.x + 9} y={start.y + 4} fill="#34d399">START</text>
        <rect x={end.x - 5} y={end.y - 5} width={10} height={10} fill="#f87171" stroke="#0b0d12" strokeWidth={2} />
        <text x={end.x + 9} y={end.y + 4} fill="#f87171">FINISH</text>
      </g>

      {riderIdx >= 0 && (
        <g>
          <circle cx={pts[riderIdx].x} cy={pts[riderIdx].y} r={12} fill="#5b9dff" fillOpacity={0.18} />
          <circle cx={pts[riderIdx].x} cy={pts[riderIdx].y} r={5.5} fill="#5b9dff" stroke="white" strokeWidth={2} />
        </g>
      )}

      {hoverIdx >= 0 && (
        <circle cx={pts[hoverIdx].x} cy={pts[hoverIdx].y} r={4} fill="#fbbf24" stroke="#0b0d12" strokeWidth={1.5} />
      )}

      <g transform={`translate(12, ${height - 12 - GRADE_BANDS.length * 14})`} fontSize={9} fontFamily="JetBrains Mono">
        {GRADE_BANDS.map((b, i) => (
          <g key={b.label} transform={`translate(0, ${i * 14})`}>
            <rect width={10} height={3} y={4} rx={1.5} fill={b.color} />
            <text x={15} y={9} fill="#9aa3b2">{b.label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
