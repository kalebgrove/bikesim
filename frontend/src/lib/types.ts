export interface RoutePoint {
  distance: number; // km from start
  elevation: number; // m ASL
  lat: number;
  lon: number;
  grade: number; // % gradient
}

export interface Route {
  id: string;
  name: string;
  distance: number; // km
  elevationGain: number; // m
  elevationLoss: number; // m
  maxElevation: number; // m
  minElevation: number; // m
  uploadedAt: string | null;
  points: RoutePoint[];
  source: "upload" | "demo";
}

export interface RiderConfig {
  mass: number; // kg (rider + bike)
  ftp: number; // W
  cda: number; // m² drag area
  crr: number; // rolling resistance coefficient
}

export interface EnvironmentConfig {
  windSpeed: number; // m/s
  windBearing: number; // deg, 0=headwind
  temperature: number; // °C
  airDensity: number; // kg/m³
}

export interface StrategyConfig {
  type: "constant_power";
  targetPower: number; // W
}

export interface SimSettings {
  timeStepS: number; // simulated seconds per tick
  tickIntervalMs: number; // real ms between ticks
}

export interface SimConfig {
  routeId: string;
  rider: RiderConfig;
  environment: EnvironmentConfig;
  strategy: StrategyConfig;
  simSettings: SimSettings;
}

export interface TelemetryPoint {
  t: number; // elapsed seconds
  dist: number; // km completed
  speed: number; // m/s
  targetPower: number; // W (user/optimizer input)
  realizedPower: number; // W (physics output)
  elevation: number; // m
  grade: number; // %
  gravForce: number; // N
  rollingForce: number; // N
  aeroForce: number; // N
  totalEnergy: number; // kJ
  forceLimited: boolean;
  limitReason: string | null;
}

export type SimStatus = "idle" | "running" | "paused" | "complete" | "stopped";
export type WsStatus = "connected" | "reconnecting" | "disconnected" | "complete";

export interface SegmentResult {
  name: string;
  distStartKm: number;
  distEndKm: number;
  avgSpeedKph: number;
  avgRealizedPower: number;
  avgGrade: number;
  timeS: number;
}

export interface SimSummary {
  totalTimeS: number;
  totalDistKm: number;
  avgSpeedKph: number;
  avgRealizedPower: number;
  maxSpeedKph: number;
  totalEnergyKj: number;
  avgGrade: number;
  normPower: number;
  kcalBurned?: number;
  stopReason?: string | null;
  segments: SegmentResult[];
}

export interface Simulation {
  id: string;
  routeId: string;
  routeName: string;
  config: SimConfig;
  status: SimStatus;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
  history: TelemetryPoint[];
  latest: TelemetryPoint | null;
  summary: SimSummary | null;
}

export interface SimulationCreated {
  simId: string;
  status: string;
  createdAt: string;
  routeName: string;
  totalDistanceKm: number;
}

export type WsServerMessage =
  | { type: "status"; data: { simId: string; status: string } }
  | { type: "tick"; data: TelemetryPoint }
  | { type: "summary"; data: SimSummary }
  | { type: "stopped"; data: { reason: string | null } };

export type WsClientMessage =
  | { type: "pause" }
  | { type: "resume" }
  | { type: "stop"; reason?: string }
  | { type: "restart" };
