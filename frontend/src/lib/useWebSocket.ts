/* ── WebSocket Hook ── */
"use client";

import { useEffect, useRef, useCallback } from "react";
import { useTrafficStore } from "./store";

const WS_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .replace("http", "ws") + "/ws/feed";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const store = useTrafficStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      store.setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "tick") {
          store.setFeedData(
            data.segments || [],
            data.risk_map || [],
            data.hour ?? 8.5
          );
        }

        if (data.type === "incident_detected") {
          store.setIncident(data.incident);
          store.setIncidentStartTime(Date.now());
          store.setProcessing(true);
        }

        if (data.type === "agents_complete") {
          store.setAgentOutput(data.output);
          store.setProcessing(false);
          if (data.output?.timeline) {
            store.setTimeline(data.output.timeline);
          }
          if (data.output?.density) {
            store.setDensity(data.output.density);
          }
        }

        if (data.type === "incident_resolved") {
          store.setIncident(null);
          store.setAgentOutput(null);
          store.setProcessing(false);
          store.setIncidentStartTime(null);
          store.setDensity(null);
        }
      } catch {
        // skip malformed messages
      }
    };

    ws.onclose = () => {
      store.setConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [store]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
