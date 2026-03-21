/* ── WebSocket Hook ── */
"use client";

import { useEffect, useRef, useCallback } from "react";
import { useTrafficStore } from "./store";

const WS_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .replace("http", "ws") + "/ws/feed";

const RECONNECT_BASE_MS = 3000;
const RECONNECT_MAX_MS = 30000;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const didUnmount = useRef(false);
  const retryCount = useRef(0);

  // Access store actions via getState() so this callback never needs to
  // re-create due to store subscription changes.
  const connect = useCallback(() => {
    const rs = wsRef.current?.readyState;
    if (rs === WebSocket.OPEN || rs === WebSocket.CONNECTING) return;
    if (didUnmount.current) return;

    const {
      setConnected,
      setFeedData,
      setIncident,
      setIncidentStartTime,
      setProcessing,
      setAgentOutput,
      setTimeline,
      setDensity,
    } = useTrafficStore.getState();

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      retryCount.current = 0;
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "tick") {
          setFeedData(
            data.segments || [],
            data.risk_map || [],
            data.hour ?? 8.5
          );
        }

        if (data.type === "incident_detected") {
          setIncident(data.incident);
          setIncidentStartTime(Date.now());
          setProcessing(true);
        }

        if (data.type === "agents_complete") {
          setAgentOutput(data.output);
          setProcessing(false);
          if (data.output?.timeline) setTimeline(data.output.timeline);
          if (data.output?.density) setDensity(data.output.density);
        }

        if (data.type === "incident_resolved") {
          setIncident(null);
          setAgentOutput(null);
          setProcessing(false);
          setIncidentStartTime(null);
          setDensity(null);
        }
      } catch {
        // skip malformed messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (!didUnmount.current) {
        // Exponential backoff capped at RECONNECT_MAX_MS
        const delay = Math.min(
          RECONNECT_BASE_MS * 2 ** retryCount.current,
          RECONNECT_MAX_MS
        );
        retryCount.current += 1;
        reconnectTimer.current = setTimeout(connect, delay);
      }
    };

    ws.onerror = () => {
      // Only close if not already closing/closed to avoid the
      // "WebSocket closed before connection established" browser warning.
      if (
        ws.readyState !== WebSocket.CLOSING &&
        ws.readyState !== WebSocket.CLOSED
      ) {
        ws.close();
      }
    };
  }, []); // stable — reads store via getState(), no subscriptions

  useEffect(() => {
    didUnmount.current = false;
    connect();
    return () => {
      didUnmount.current = true;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
