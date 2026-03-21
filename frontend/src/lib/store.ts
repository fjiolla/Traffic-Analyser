/* ── Zustand Store — Real-time traffic state ── */
import { create } from "zustand";
import type {
  SegmentSpeed, RiskEntry, IncidentDetection, AgentOutput,
  ChatMessage, TimelineEntry, Metrics, DensityData,
} from "./types";

interface TrafficStore {
  // Connection
  connected: boolean;
  setConnected: (v: boolean) => void;

  // Feed data
  segments: SegmentSpeed[];
  riskMap: RiskEntry[];
  hour: number;
  setFeedData: (segments: SegmentSpeed[], riskMap: RiskEntry[], hour: number) => void;

  // Incident
  incident: IncidentDetection | null;
  setIncident: (v: IncidentDetection | null) => void;
  processing: boolean;
  setProcessing: (v: boolean) => void;

  // Agent output
  agentOutput: AgentOutput | null;
  setAgentOutput: (v: AgentOutput | null) => void;

  // Chat
  messages: ChatMessage[];
  addMessage: (m: ChatMessage) => void;
  clearMessages: () => void;

  // Timeline
  timeline: TimelineEntry[];
  setTimeline: (t: TimelineEntry[]) => void;

  // Metrics
  metrics: Metrics | null;
  setMetrics: (m: Metrics) => void;

  // Density
  density: DensityData | null;
  setDensity: (d: DensityData | null) => void;

  // UI
  activePanel: string;
  setActivePanel: (p: string) => void;
  incidentStartTime: number | null;
  setIncidentStartTime: (t: number | null) => void;
}

export const useTrafficStore = create<TrafficStore>((set) => ({
  connected: false,
  setConnected: (connected) => set({ connected }),

  segments: [],
  riskMap: [],
  hour: 8.5,
  setFeedData: (segments, riskMap, hour) => set({ segments, riskMap, hour }),

  incident: null,
  setIncident: (incident) => set({ incident }),
  processing: false,
  setProcessing: (processing) => set({ processing }),

  agentOutput: null,
  setAgentOutput: (agentOutput) => set({ agentOutput }),

  messages: [],
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  clearMessages: () => set({ messages: [] }),

  timeline: [],
  setTimeline: (timeline) => set({ timeline }),

  metrics: null,
  setMetrics: (metrics) => set({ metrics }),

  density: null,
  setDensity: (density) => set({ density }),

  activePanel: "signals",
  setActivePanel: (activePanel) => set({ activePanel }),
  incidentStartTime: null,
  setIncidentStartTime: (incidentStartTime) => set({ incidentStartTime }),
}));
