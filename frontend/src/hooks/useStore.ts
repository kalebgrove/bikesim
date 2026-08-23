import { useSyncExternalStore } from "react";
import { subscribe, getRoutes, getSimulations, getRoute, getSimulation } from "../lib/store";

export function useRoutes() {
  return useSyncExternalStore(subscribe, getRoutes);
}

export function useRoute(id: string | undefined) {
  return useSyncExternalStore(subscribe, () => (id ? getRoute(id) : undefined));
}

export function useSimulations() {
  return useSyncExternalStore(subscribe, getSimulations);
}

export function useSimulation(id: string | undefined) {
  return useSyncExternalStore(subscribe, () => (id ? getSimulation(id) : undefined));
}
