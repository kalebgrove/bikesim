import type { Route, Simulation } from "./types";

// Module-level store — survives navigation, triggers re-render via listeners
let routes: Route[] = [];
let simulations: Simulation[] = [];
const listeners = new Set<() => void>();

function notify() {
  listeners.forEach((fn) => fn());
}

export function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export function getRoutes(): Route[] {
  return routes;
}

export function getRoute(id: string): Route | undefined {
  return routes.find((r) => r.id === id);
}

export function setRoutes(list: Route[]) {
  routes = [...list];
  notify();
}

export function upsertRoute(route: Route) {
  const idx = routes.findIndex((r) => r.id === route.id);
  if (idx >= 0) {
    routes = routes.map((r) => (r.id === route.id ? route : r));
  } else {
    routes = [route, ...routes];
  }
  notify();
}

export function getSimulations(): Simulation[] {
  return simulations;
}

export function getSimulation(id: string): Simulation | undefined {
  return simulations.find((s) => s.id === id);
}

export function upsertSimulation(sim: Simulation) {
  const idx = simulations.findIndex((s) => s.id === sim.id);
  if (idx >= 0) {
    simulations = simulations.map((s) => (s.id === sim.id ? sim : s));
  } else {
    simulations = [sim, ...simulations];
  }
  notify();
}
