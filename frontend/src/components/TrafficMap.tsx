/* ── Traffic Map — Mapbox GL + speed-colored markers ── */
"use client";

import { useMemo, useCallback } from "react";
import Map, { Source, Layer, Marker, NavigationControl } from "react-map-gl/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";
import { useTrafficStore } from "@/lib/store";
import { speedToColor, severityColor } from "@/lib/utils";
import type { SegmentSpeed, RiskEntry } from "@/lib/types";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";
const BROOKLYN_CENTER = { longitude: -73.9442, latitude: 40.6782, zoom: 12.5 };

export default function TrafficMap() {
  const segments = useTrafficStore((s) => s.segments);
  const riskMap = useTrafficStore((s) => s.riskMap);
  const incident = useTrafficStore((s) => s.incident);
  const agentOutput = useTrafficStore((s) => s.agentOutput);

  // Segment Points GeoJSON
  const segmentGeoJSON = useMemo(() => {
    return {
      type: "FeatureCollection" as const,
      features: segments.map((seg: SegmentSpeed) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [seg.lon, seg.lat],
        },
        properties: {
          color: speedToColor(seg.speed, seg.free_flow_speed),
          speed: Math.round(seg.speed),
          name: seg.street_name,
        },
      })),
    };
  }, [segments]);

  // Risk heatmap GeoJSON
  const riskGeoJSON = useMemo(() => {
    return {
      type: "FeatureCollection" as const,
      features: riskMap.map((r: RiskEntry) => ({
        type: "Feature" as const,
        geometry: {
          type: "Point" as const,
          coordinates: [r.lon, r.lat],
        },
        properties: {
          risk: r.score,
        },
      })),
    };
  }, [riskMap]);

  // Diversion route line GeoJSON
  const diversionGeoJSON = useMemo(() => {
    if (!agentOutput?.diversion?.route_coords?.length) return null;
    return {
      type: "Feature" as const,
      geometry: {
        type: "LineString" as const,
        coordinates: agentOutput.diversion.route_coords,
      },
      properties: {},
    };
  }, [agentOutput]);

  return (
    <div className="w-full h-full relative">
      <Map
        initialViewState={BROOKLYN_CENTER}
        style={{ width: "100%", height: "100%" }}
        mapStyle="mapbox://styles/mapbox/light-v11"
        mapboxAccessToken={MAPBOX_TOKEN}
        attributionControl={false}
      >
        <NavigationControl position="top-left" />

        {/* Risk Heatmap Layer */}
        <Source id="risk-heatmap" type="geojson" data={riskGeoJSON}>
          <Layer
            id="risk-heat"
            type="heatmap"
            paint={{
              "heatmap-weight": ["get", "risk"],
              "heatmap-intensity": 1.5,
              "heatmap-radius": 30,
              "heatmap-opacity": 0.4,
              "heatmap-color": [
                "interpolate",
                ["linear"],
                ["heatmap-density"],
                0, "rgba(0,0,0,0)",
                0.2, "rgba(16,185,129,0.4)",
                0.4, "rgba(245,158,11,0.5)",
                0.6, "rgba(249,115,22,0.6)",
                0.8, "rgba(239,68,68,0.7)",
                1, "rgba(220,38,38,0.9)",
              ],
            }}
          />
        </Source>

        {/* Speed points */}
        <Source id="segments" type="geojson" data={segmentGeoJSON}>
          <Layer
            id="segment-circles"
            type="circle"
            paint={{
              "circle-radius": 6,
              "circle-color": ["get", "color"],
              "circle-stroke-width": 1.5,
              "circle-stroke-color": "#ffffff",
              "circle-opacity": 0.9,
            }}
          />
        </Source>

        {/* Diversion Route Line */}
        {diversionGeoJSON && (
          <Source id="diversion-route" type="geojson" data={diversionGeoJSON}>
            <Layer
              id="diversion-line"
              type="line"
              paint={{
                "line-color": "#2563eb",
                "line-width": 4,
                "line-dasharray": [2, 2],
                "line-opacity": 0.8,
              }}
            />
          </Source>
        )}

        {/* Incident Marker */}
        {incident && (
          <Marker
            latitude={incident.lat}
            longitude={incident.lon}
            anchor="center"
          >
            <div className="relative">
              <div
                className="animate-incident-pulse absolute -inset-3 rounded-full opacity-30"
                style={{ backgroundColor: severityColor(incident.severity) }}
              />
              <div
                className="w-6 h-6 rounded-full border-2 border-white shadow-lg flex items-center justify-center"
                style={{ backgroundColor: severityColor(incident.severity) }}
              >
                <span className="text-white text-xs font-bold">!</span>
              </div>
            </div>
          </Marker>
        )}
      </Map>

      {/* Map Legend */}
      <div className="absolute bottom-4 left-4 glass-card rounded-lg p-3 text-xs">
        <div className="font-semibold mb-1.5 text-slate-700">Speed Legend</div>
        <div className="flex items-center gap-1.5 mb-1">
          <div className="w-3 h-3 rounded-full bg-emerald-500" />
          <span className="text-slate-600">&gt; 70% Free-flow</span>
        </div>
        <div className="flex items-center gap-1.5 mb-1">
          <div className="w-3 h-3 rounded-full bg-amber-500" />
          <span className="text-slate-600">40–70%</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <span className="text-slate-600">&lt; 40% (Congested)</span>
        </div>
      </div>
    </div>
  );
}
