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
  getPredictedHotspots: () => fetchAPI<any>("/api/hotspots/predicted"),

  geocodeSearch: (query: string) =>
    fetchAPI<any>(`/api/geocode?q=${encodeURIComponent(query)}`),

  findRoutes: (origin: { lat: number; lon: number }, dest: { lat: number; lon: number }, k: number = 3, vehicleType: string = "normal") =>
    fetchAPI<any>("/api/routes", {
      method: "POST",
      body: JSON.stringify({
        origin_lat: origin.lat, origin_lon: origin.lon,
        dest_lat: dest.lat, dest_lon: dest.lon,
        k, vehicle_type: vehicleType,
      }),
    }),

  downloadRoutesCsv: () => {
    const url = `${API_URL}/api/routes/csv`;
    const a = document.createElement("a");
    a.href = url;
    a.download = "routes.csv";
    a.click();
  },
  
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

  getSettings: () => fetchAPI<any>("/api/settings"),

  setAutoPost: (enabled: boolean) =>
    fetchAPI<any>("/api/settings/auto-post", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),
};

export { API_URL };
