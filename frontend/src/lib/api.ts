/* ── API Client ── */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getState: () => fetchAPI<any>("/api/state"),
  getAgentOutput: () => fetchAPI<any>("/api/agents"),
  getSignals: () => fetchAPI<any>("/api/signals"),
  getDiversion: () => fetchAPI<any>("/api/diversion"),
  getAlerts: () => fetchAPI<any>("/api/alerts"),
  getDensity: () => fetchAPI<any>("/api/density"),
  getTimeline: () => fetchAPI<any>("/api/timeline"),
  getHotspots: () => fetchAPI<any>("/api/hotspots"),
  getMetrics: () => fetchAPI<any>("/api/metrics"),
  getTwinData: () => fetchAPI<any>("/api/twin"),
  getChatHistory: () => fetchAPI<any>("/api/chat/history"),
  getDocuments: () => fetchAPI<any>("/api/documents"),
  getWeather: () => fetchAPI<any>("/api/weather"),
  
  triggerIncident: (severity: string = "HIGH") =>
    fetchAPI<any>("/api/trigger-incident", {
      method: "POST",
      body: JSON.stringify({ severity }),
    }),

  resolveIncident: () =>
    fetchAPI<any>("/api/resolve-incident", { method: "POST" }),

  sendChat: (message: string) =>
    fetchAPI<any>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
};

export { API_URL };
