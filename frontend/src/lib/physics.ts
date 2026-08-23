import type { Route, SimConfig, TelemetryPoint, SimSummary, SegmentResult } from "./types";

function interpolate(route: Route, distKm: number, key: "elevation" | "grade"): number {
  const pts = route.points;
  if (pts.length === 0) return 0;
  if (distKm <= pts[0].distance) return pts[0][key];
  if (distKm >= pts[pts.length - 1].distance) return pts[pts.length - 1][key];
  let lo = 0;
  let hi = pts.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (pts[mid].distance <= distKm) lo = mid;
    else hi = mid;
  }
  const t = (distKm - pts[lo].distance) / (pts[hi].distance - pts[lo].distance + 1e-9);
  return pts[lo][key] + t * (pts[hi][key] - pts[lo][key]);
}

export function tick(prev: TelemetryPoint, config: SimConfig, route: Route, dtS: number): TelemetryPoint {
  const { mass, cda, crr } = config.rider;
  const { airDensity, windSpeed, windBearing } = config.environment;
  const targetPower = config.strategy.targetPower;
  const g = 9.81;

  const grade = interpolate(route, prev.dist, "grade");
  const elevation = interpolate(route, prev.dist, "elevation");
  const gradeRad = Math.atan(grade / 100);

  const v = Math.max(1.0, prev.speed);

  // Wind component: simplified — assume rider heading is mixed, so use fraction of wind as headwind
  const headwindFrac = Math.cos((windBearing * Math.PI) / 180);
  const windComp = windSpeed * headwindFrac;
  const vRel = v + windComp;

  const gravForce = mass * g * Math.sin(gradeRad);
  const rollingForce = mass * g * Math.cos(gradeRad) * crr;
  const aeroForce = 0.5 * airDensity * cda * Math.sign(vRel) * vRel * vRel;
  const resistanceForce = gravForce + rollingForce + aeroForce;

  // Drive force from target power
  const driveForce = targetPower / v;
  const netForce = driveForce - resistanceForce;
  const accel = netForce / mass;

  let newV = v + accel * dtS;
  newV = Math.max(0.8, Math.min(28, newV));

  // Realized power = what physics actually absorbs
  // When going downhill fast, rider coasts — realized < target
  const physPower = resistanceForce * newV;
  const forceLimited = physPower < targetPower * 0.75 && grade < -2.5;
  const realizedPower = forceLimited ? Math.max(0, physPower) : Math.min(targetPower * 1.05, Math.max(0, physPower));

  const newDist = prev.dist + (newV * dtS) / 1000;
  const energyDelta = (realizedPower * dtS) / 1000;
  const totalEnergy = prev.totalEnergy + energyDelta;

  const limitReason = forceLimited ? `Descent grade ${grade.toFixed(1)}% — gravity provides propulsion` : null;

  return {
    t: prev.t + dtS,
    dist: Math.min(newDist, route.distance),
    speed: isFinite(newV) ? newV : 5,
    targetPower: isFinite(targetPower) ? targetPower : 0,
    realizedPower: isFinite(realizedPower) ? realizedPower : 0,
    elevation: isFinite(elevation) ? elevation : 0,
    grade: isFinite(grade) ? grade : 0,
    gravForce: isFinite(gravForce) ? gravForce : 0,
    rollingForce: isFinite(rollingForce) ? rollingForce : 0,
    aeroForce: isFinite(aeroForce) ? aeroForce : 0,
    totalEnergy: isFinite(totalEnergy) ? totalEnergy : 0,
    forceLimited,
    limitReason,
  };
}

export function initialTelemetry(route: Route, targetPower: number): TelemetryPoint {
  const elevation = route.points[0]?.elevation ?? 0;
  return {
    t: 0,
    dist: 0,
    speed: 5,
    targetPower,
    realizedPower: 0,
    elevation,
    grade: 0,
    gravForce: 0,
    rollingForce: 0,
    aeroForce: 0,
    totalEnergy: 0,
    forceLimited: false,
    limitReason: null,
  };
}

export function computeSummary(history: TelemetryPoint[], config: SimConfig): SimSummary {
  if (history.length < 2) {
    return {
      totalTimeS: 0,
      totalDistKm: 0,
      avgSpeedKph: 0,
      avgRealizedPower: 0,
      maxSpeedKph: 0,
      totalEnergyKj: 0,
      avgGrade: 0,
      normPower: 0,
      segments: [],
    };
  }

  const last = history[history.length - 1];
  const totalTimeS = last.t;
  const totalDistKm = last.dist;
  const avgSpeedKph = totalDistKm / (totalTimeS / 3600);
  const avgRealizedPower = history.reduce((s, p) => s + p.realizedPower, 0) / history.length;
  const maxSpeedKph = Math.max(...history.map((p) => p.speed)) * 3.6;
  const totalEnergyKj = last.totalEnergy;
  const avgGrade = history.reduce((s, p) => s + p.grade, 0) / history.length;

  // Normalized power (4th power average, simplified)
  const np = Math.pow(history.reduce((s, p) => s + Math.pow(p.realizedPower, 4), 0) / history.length, 0.25);

  // Segments: split route into 3 parts
  const segCount = 3;
  const segSize = Math.floor(history.length / segCount);
  const segNames = ["Opening Sector", "Climb / Mid-Race", "Final Sector"];
  const segments: SegmentResult[] = [];

  for (let s = 0; s < segCount; s++) {
    const slice = history.slice(s * segSize, (s + 1) * segSize);
    if (slice.length < 2) continue;
    const avgSpd = (slice.reduce((a, p) => a + p.speed, 0) / slice.length) * 3.6;
    const avgPwr = slice.reduce((a, p) => a + p.realizedPower, 0) / slice.length;
    const avgGr = slice.reduce((a, p) => a + p.grade, 0) / slice.length;
    segments.push({
      name: segNames[s] ?? `Segment ${s + 1}`,
      distStartKm: slice[0].dist,
      distEndKm: slice[slice.length - 1].dist,
      avgSpeedKph: avgSpd,
      avgRealizedPower: avgPwr,
      avgGrade: avgGr,
      timeS: slice[slice.length - 1].t - slice[0].t,
    });
  }

  return {
    totalTimeS,
    totalDistKm,
    avgSpeedKph: isFinite(avgSpeedKph) ? avgSpeedKph : 0,
    avgRealizedPower,
    maxSpeedKph,
    totalEnergyKj,
    avgGrade,
    normPower: isFinite(np) ? np : avgRealizedPower,
    segments,
  };
}
