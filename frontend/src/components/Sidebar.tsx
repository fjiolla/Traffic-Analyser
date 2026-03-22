/* ── Sidebar — incident timer, severity badge, density, metrics ── */
"use client";

import { useEffect, useState } from "react";
import {
  Activity, AlertTriangle, Clock, Radio, Gauge,
  Zap, CheckCircle, Circle, CloudRain, Cloud, Sun,
  Snowflake, Wind, CloudFog, CloudLightning, Share2,
} from "lucide-react";
import { useTrafficStore } from "@/lib/store";
import { severityBg, formatHour, cn } from "@/lib/utils";
import { api } from "@/lib/api";

export default function Sidebar() {
  const connected = useTrafficStore((s) => s.connected);
  const incident = useTrafficStore((s) => s.incident);
  const agentOutput = useTrafficStore((s) => s.agentOutput);
  const hour = useTrafficStore((s) => s.hour);
  const segments = useTrafficStore((s) => s.segments);
  const processing = useTrafficStore((s) => s.processing);
  const incidentStartTime = useTrafficStore((s) => s.incidentStartTime);
  const density = useTrafficStore((s) => s.density);
  const weather = useTrafficStore((s) => s.weather);
  const setWeather = useTrafficStore((s) => s.setWeather);
  const autoPost = useTrafficStore((s) => s.autoPost);
  const setAutoPost = useTrafficStore((s) => s.setAutoPost);

  const [elapsed, setElapsed] = useState("00:00");

  // Fetch initial auto-post setting
  useEffect(() => {
    api.getSettings().then((s: { auto_post: boolean }) => setAutoPost(s.auto_post)).catch(() => {});
  }, [setAutoPost]);

  // Poll weather every 5 minutes
  useEffect(() => {
    const fetchWeather = () => {
      api.getWeather().then(setWeather).catch(() => {});
    };
    fetchWeather();
    const interval = setInterval(fetchWeather, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [setWeather]);

  useEffect(() => {
    if (!incidentStartTime) {
      setElapsed("00:00");
      return;
    }
    const interval = setInterval(() => {
      const diff = Math.floor((Date.now() - incidentStartTime) / 1000);
      const min = Math.floor(diff / 60).toString().padStart(2, "0");
      const sec = (diff % 60).toString().padStart(2, "0");
      setElapsed(`${min}:${sec}`);
    }, 1000);
    return () => clearInterval(interval);
  }, [incidentStartTime]);

  const avgSpeed = segments.length
    ? Math.round(
        segments.reduce((a, s) => a + s.speed, 0) / segments.length
      )
    : 0;

  return (
    <div className="w-64 border-r border-border bg-white flex flex-col h-full overflow-y-auto">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <Zap className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-base font-bold text-foreground">TrafficMind</h1>
            <p className="text-[10px] text-muted">AI Co-Pilot</p>
          </div>
        </div>
      </div>

      {/* Connection Status */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-xs">
          <div
            className={cn(
              "w-2 h-2 rounded-full",
              connected ? "bg-success" : "bg-danger"
            )}
          />
          <span className="text-muted">
            {connected ? "Connected — Live Feed" : "Disconnected"}
          </span>
        </div>
      </div>

      {/* Simulated Time */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-xs text-muted mb-1">
          <Clock className="w-3.5 h-3.5" />
          <span>Current Time</span>
        </div>
        <p className="text-lg font-semibold text-foreground pl-5.5">
          {formatHour(hour)}
        </p>
      </div>

      {/* Weather */}
      {weather && (
        <div className="px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 text-xs text-muted mb-1">
            {weather.condition === "snow" || weather.condition === "ice" ? (
              <Snowflake className="w-3.5 h-3.5" />
            ) : weather.condition === "rain" || weather.condition === "heavy_rain" ? (
              <CloudRain className="w-3.5 h-3.5" />
            ) : weather.condition === "fog" ? (
              <CloudFog className="w-3.5 h-3.5" />
            ) : weather.condition === "wind" ? (
              <Wind className="w-3.5 h-3.5" />
            ) : weather.condition === "cloudy" || weather.condition === "partly_cloudy" ? (
              <Cloud className="w-3.5 h-3.5" />
            ) : (
              <Sun className="w-3.5 h-3.5" />
            )}
            <span>Weather</span>
          </div>
          <div className="pl-5.5 space-y-0.5">
            <p className="text-sm font-semibold text-foreground">
              {Math.round(weather.temp_f)}°F — {weather.description}
            </p>
            <div className="flex gap-3 text-[10px] text-muted">
              <span>💧 {weather.precip_pct}%</span>
              <span>💨 {weather.wind_mph} mph</span>
            </div>
            {weather.is_severe && (
              <p className="text-[10px] font-semibold text-danger mt-0.5">
                ⚠ Severe weather — routing affected
              </p>
            )}
          </div>
        </div>
      )}

      {/* Incident Status */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-xs text-muted mb-2">
          <AlertTriangle className="w-3.5 h-3.5" />
          <span>Incident Status</span>
        </div>
        {incident ? (
          <div className="space-y-2 pl-5.5">
            <span
              className={cn(
                "inline-block text-xs font-semibold px-2 py-0.5 rounded-full",
                severityBg(incident.severity)
              )}
            >
              {incident.severity}
            </span>
            <p className="text-xs text-foreground font-medium">
              {incident.street_name}
            </p>
            <div className="flex items-center gap-1.5 text-xs text-muted">
              <Clock className="w-3 h-3" />
              <span>Elapsed: {elapsed}</span>
            </div>
            {incident.duration_estimate_min > 0 && (
              <p className="text-[10px] text-muted">
                Est. duration: {incident.duration_estimate_min} min
              </p>
            )}
            {processing && (
              <div className="flex items-center gap-1.5 text-xs text-primary">
                <Activity className="w-3 h-3 animate-spin" />
                <span>Agents processing…</span>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-1.5 pl-5.5 text-xs text-success">
            <CheckCircle className="w-3.5 h-3.5" />
            <span>No active incidents</span>
          </div>
        )}
      </div>

      {/* Network Stats */}
      <div className="px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2 text-xs text-muted mb-2">
          <Activity className="w-3.5 h-3.5" />
          <span>Network Stats</span>
        </div>
        <div className="space-y-1.5 pl-5.5">
          <div className="flex justify-between text-xs">
            <span className="text-muted">Active Segments</span>
            <span className="font-medium text-foreground">{segments.length}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-muted">Avg Speed</span>
            <span className="font-medium text-foreground">{avgSpeed} mph</span>
          </div>
        </div>
      </div>

      {/* Density */}
      {density && (
        <div className="px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 text-xs text-muted mb-2">
            <Gauge className="w-3.5 h-3.5" />
            <span>Vehicle Density</span>
          </div>
          <div className="space-y-1.5 pl-5.5">
            <p className="text-sm font-semibold text-foreground">
              {density.congestion_level}
            </p>
            <p className="text-xs text-muted">
              ~{density.estimated_vehicles} vehicles
            </p>
          </div>
        </div>
      )}

      {/* Agent Confidence */}
      {agentOutput?.confidence_scores && (
        <div className="px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2 text-xs text-muted mb-2">
            <Radio className="w-3.5 h-3.5" />
            <span>Agent Confidence</span>
          </div>
          <div className="space-y-1.5 pl-5.5">
            {Object.entries(agentOutput.confidence_scores).map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs">
                <span className="text-muted capitalize">{k}</span>
                <span
                  className={cn(
                    "font-medium",
                    Number(v) >= 0.8
                      ? "text-success"
                      : Number(v) >= 0.6
                      ? "text-warning"
                      : "text-danger"
                  )}
                >
                  {(Number(v) * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cascade Risk */}
      {agentOutput && (
        <div className="px-4 py-3">
          <div className="flex items-center gap-2 text-xs text-muted mb-1">
            <Circle className="w-3.5 h-3.5" />
            <span>Cascade Risk</span>
          </div>
          <div className="pl-5.5">
            <div className="w-full bg-slate-100 rounded-full h-2 mt-1">
              <div
                className={cn(
                  "h-2 rounded-full transition-all duration-500",
                  agentOutput.cascade_risk > 0.7
                    ? "bg-danger"
                    : agentOutput.cascade_risk > 0.4
                    ? "bg-warning"
                    : "bg-success"
                )}
                style={{
                  width: `${Math.min(agentOutput.cascade_risk * 100, 100)}%`,
                }}
              />
            </div>
            <p className="text-[10px] text-muted mt-0.5">
              {(agentOutput.cascade_risk * 100).toFixed(0)}% probability
            </p>
          </div>
        </div>
      )}

      {/* Auto-Post Tweets */}
      <div className="px-4 py-3 border-t border-slate-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted">
            <Share2 className="w-3.5 h-3.5" />
            <span>Auto-Post Tweets</span>
          </div>
          <button
            onClick={() => {
              const next = !autoPost;
              setAutoPost(next);
              api.setAutoPost(next).catch(() => setAutoPost(!next));
            }}
            className={cn(
              "relative w-8 h-[18px] rounded-full transition-colors duration-200",
              autoPost ? "bg-blue-500" : "bg-slate-300"
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 left-0.5 w-3.5 h-3.5 rounded-full bg-white transition-transform duration-200",
                autoPost && "translate-x-3.5"
              )}
            />
          </button>
        </div>
        <p className="text-[10px] text-muted mt-1 pl-5.5">
          {autoPost ? "Tweets post when incidents detected" : "Tweet auto-posting disabled"}
        </p>
      </div>
    </div>
  );
}
