import { createContext, useContext } from "react";
import type { SimConfig, WsStatus } from "./types";

interface SimEngineContextValue {
  wsStatus: WsStatus;
  start: (config: SimConfig) => Promise<string>;
  pause: () => void;
  resume: () => void;
  restart: (simId: string) => void;
  hardStop: (simId: string) => void;
}

export const SimEngineContext = createContext<SimEngineContextValue | null>(null);

export function useSimEngineContext(): SimEngineContextValue {
  const ctx = useContext(SimEngineContext);
  if (!ctx) throw new Error("useSimEngineContext must be used within SimEngineContext.Provider");
  return ctx;
}
