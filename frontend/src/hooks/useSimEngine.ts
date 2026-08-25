import { useCallback, useRef, useState } from "react";
import type { Simulation, SimConfig, TelemetryPoint, WsServerMessage, WsStatus } from "../lib/types";
import { getSimulation, upsertSimulation } from "../lib/store";
import { createSimulation, simulationStreamUrl } from "../lib/api";

let lastRenderTime = 0;
const HIDDEN_THROTTLE_MS = 500;

export function useSimEngine() {
  const [wsStatus, setWsStatus] = useState<WsStatus>("disconnected");
  const socketRef = useRef<WebSocket | null>(null);
  const simIdRef = useRef<string | null>(null);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const closeSocket = useCallback(() => {
    if (closeTimerRef.current !== null) {
      clearTimeout(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    const sock = socketRef.current;
    socketRef.current = null;
    if (sock && (sock.readyState === WebSocket.OPEN || sock.readyState === WebSocket.CONNECTING)) {
      sock.onclose = null;
      sock.close();
    }
  }, []);

  const sendControl = useCallback((message: Record<string, unknown>) => {
    const sock = socketRef.current;
    if (sock && sock.readyState === WebSocket.OPEN) {
      sock.send(JSON.stringify(message));
    }
  }, []);

  const handleMessage = useCallback((simId: string, event: MessageEvent) => {
    let msg: WsServerMessage;
    try {
      msg = JSON.parse(event.data as string) as WsServerMessage;
    } catch {
      return;
    }

    const sim = getSimulation(simId);
    if (!sim) return;

    switch (msg.type) {
      case "status": {
        const status = msg.data.status;
        if ((status === "running" || status === "paused") && sim.status !== status) {
          upsertSimulation({ ...sim, status });
        }
        break;
      }
      case "tick": {
        const point = msg.data as TelemetryPoint;
        // When the tab is hidden, throttle store updates to avoid a backlog
        // that lags the UI on return. Status/summary/stopped always go through.
        if (document.hidden) {
          const now = Date.now();
          if (now - lastRenderTime < HIDDEN_THROTTLE_MS) return;
          lastRenderTime = now;
        }
        // A tick whose clock went backwards means the backend session was restarted
        const history =
          sim.latest && point.t <= sim.latest.t ? [point] : [...sim.history, point];
        upsertSimulation({ ...sim, latest: point, history });
        break;
      }
      case "summary": {
        upsertSimulation({
          ...sim,
          status: "complete",
          summary: msg.data,
          completedAt: new Date().toISOString(),
        });
        setWsStatus("complete");
        break;
      }
      case "stopped": {
        upsertSimulation({
          ...sim,
          status: "stopped",
          completedAt: new Date().toISOString(),
        });
        setWsStatus("disconnected");
        break;
      }
    }
  }, []);

  const connect = useCallback(
    (simId: string) => {
      closeSocket();
      setWsStatus("reconnecting");

      const sock = new WebSocket(simulationStreamUrl(simId));
      socketRef.current = sock;

      sock.onopen = () => setWsStatus("connected");
      sock.onmessage = (event) => handleMessage(simId, event);
      sock.onclose = () => {
        if (socketRef.current !== sock) return;
        socketRef.current = null;
        setWsStatus((cur) => (cur === "complete" ? cur : "disconnected"));
        const sim = getSimulation(simId);
        if (sim && sim.status === "running") {
          upsertSimulation({ ...sim, status: "stopped", completedAt: new Date().toISOString() });
        }
      };
    },
    [closeSocket, handleMessage]
  );

  const start = useCallback(
    async (config: SimConfig): Promise<string> => {
      closeSocket();
      const created = await createSimulation(config);
      const id = created.simId;
      simIdRef.current = id;

      const now = new Date().toISOString();
      const sim: Simulation = {
        id,
        routeId: config.routeId,
        routeName: created.routeName,
        config,
        status: "running",
        createdAt: now,
        startedAt: now,
        completedAt: null,
        history: [],
        latest: null,
        summary: null,
      };
      upsertSimulation(sim);

      connect(id);
      return id;
    },
    [closeSocket, connect]
  );

  const pause = useCallback(() => {
    sendControl({ type: "pause" });
    const id = simIdRef.current;
    const sim = id ? getSimulation(id) : undefined;
    if (sim && sim.status === "running") {
      upsertSimulation({ ...sim, status: "paused" });
    }
  }, [sendControl]);

  const resume = useCallback(() => {
    sendControl({ type: "resume" });
    const id = simIdRef.current;
    const sim = id ? getSimulation(id) : undefined;
    if (sim && sim.status === "paused") {
      upsertSimulation({ ...sim, status: "running" });
    }
  }, [sendControl]);

  const restart = useCallback(
    (restartId: string) => {
      const sim = getSimulation(restartId);
      if (!sim) return;
      simIdRef.current = restartId;

      if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN) {
        connect(restartId);
      }
      sendControl({ type: "restart" });

      upsertSimulation({
        ...sim,
        status: "running",
        startedAt: new Date().toISOString(),
        completedAt: null,
        history: [],
        latest: null,
        summary: null,
      });
      setWsStatus("reconnecting");
    },
    [connect, sendControl]
  );

  const hardStop = useCallback(
    (stopId: string) => {
      const sim = getSimulation(stopId);
      if (!sim) return;
      simIdRef.current = stopId;

      sendControl({ type: "stop", reason: "Stopped by user" });
      upsertSimulation({ ...sim, status: "stopped", completedAt: new Date().toISOString() });
      setWsStatus("disconnected");
      closeTimerRef.current = setTimeout(() => closeSocket(), 400);
    },
    [sendControl, closeSocket]
  );

  return { wsStatus, start, pause, resume, restart, hardStop };
}
