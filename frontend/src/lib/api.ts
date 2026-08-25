import type { Route, SimConfig, SimulationCreated } from "./types";

const API_BASE: string =
  (import.meta.env.BACKEND_URL as string | undefined) ?? "";

export interface RouteRow {
  id: number | string;
  name: string;
  file_path?: string;
  created_at?: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch (err) {
    throw new Error(`Cannot reach BikeSim backend at ${API_BASE}`);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body
    }
    throw new Error(detail);
  }
  return (await res.json()) as T;
}

export function listRoutes(): Promise<RouteRow[]> {
  return request<RouteRow[]>("/routes");
}

export function fetchRouteGeometry(routeRef: string | number): Promise<Route> {
  return request<Route>(`/routes/${encodeURIComponent(String(routeRef))}/points`);
}

export function uploadRoute(file: File, name: string): Promise<RouteRow> {
  const form = new FormData();
  form.append("name", name);
  form.append("file", file, file.name);
  return request<RouteRow>("/routes", { method: "POST", body: form });
}

export function createSimulation(config: SimConfig): Promise<SimulationCreated> {
  return request<SimulationCreated>("/simulations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  });
}

export function simulationStreamUrl(simId: string): string {
  return `${API_BASE.replace(/^http/, "ws")}/simulations/${encodeURIComponent(simId)}/stream`;
}
