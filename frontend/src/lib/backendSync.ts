import { fetchRouteGeometry, listRoutes, type RouteRow } from "./api";
import { setRoutes, upsertRoute } from "./store";
import type { Route } from "./types";

function placeholderRoute(row: RouteRow): Route {
  return {
    id: String(row.id),
    name: row.name,
    distance: 0,
    elevationGain: 0,
    elevationLoss: 0,
    maxElevation: 0,
    minElevation: 0,
    uploadedAt: row.created_at ?? null,
    points: [],
    source: "upload",
  };
}

let syncStarted = false;

export function loadRoutesFromBackend(): void {
  if (syncStarted) return;
  syncStarted = true;

  void (async () => {
    let rows: RouteRow[];
    try {
      rows = await listRoutes();
    } catch (err) {
      syncStarted = false;
      console.error("[bikesim] Could not load routes from backend:", err);
      return;
    }

    setRoutes(rows.map(placeholderRoute));

    for (const row of rows) {
      try {
        const geometry = await fetchRouteGeometry(String(row.id));
        upsertRoute(geometry);
      } catch (err) {
        console.warn(`[bikesim] Could not load geometry for route "${row.name}":`, err);
      }
    }
  })();
}
