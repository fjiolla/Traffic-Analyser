/* ── Routing Panel — diversion route display ── */
"use client";

import { Navigation, ArrowRight, Shield, TrendingDown, Clock } from "lucide-react";
import { useTrafficStore } from "@/lib/store";
import { cn, confidenceColor } from "@/lib/utils";

export default function RoutingPanel() {
  const agentOutput = useTrafficStore((s) => s.agentOutput);
  const diversion = agentOutput?.diversion;

  if (!diversion) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted py-12">
        <Navigation className="w-10 h-10 mb-3 text-slate-300" />
        <p className="text-sm font-medium">No diversion route</p>
        <p className="text-xs mt-1">Diversion will appear when incident is detected</p>
      </div>
    );
  }

  return (
    <div className="p-1">
      <div className="flex items-center gap-2 mb-3">
        <Navigation className="w-4 h-4 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">Dynamic Diversion Route</h3>
      </div>

      <div className="border border-border rounded-lg p-4 bg-white">
        {/* Route Streets */}
        <div className="mb-4">
          <span className="text-xs text-muted font-medium">Recommended Path</span>
          <div className="flex flex-wrap items-center gap-1 mt-1.5">
            {diversion.route_street_names.map((street, i) => (
              <span key={i} className="flex items-center gap-1">
                <span className="text-xs font-medium text-foreground bg-primary/5 px-2 py-0.5 rounded">
                  {street}
                </span>
                {i < diversion.route_street_names.length - 1 && (
                  <ArrowRight className="w-3 h-3 text-muted" />
                )}
              </span>
            ))}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="text-center p-2 bg-emerald-50 rounded-lg">
            <TrendingDown className="w-4 h-4 text-success mx-auto mb-1" />
            <p className="text-xs text-muted">Risk Reduction</p>
            <p className="text-sm font-bold text-success">
              {diversion.risk_delta_pct.toFixed(0)}%
            </p>
          </div>
          <div className="text-center p-2 bg-blue-50 rounded-lg">
            <Clock className="w-4 h-4 text-primary mx-auto mb-1" />
            <p className="text-xs text-muted">Time Delta</p>
            <p className="text-sm font-bold text-primary">
              +{diversion.time_delta_min.toFixed(1)} min
            </p>
          </div>
          <div className="text-center p-2 bg-amber-50 rounded-lg">
            <Shield className="w-4 h-4 text-warning mx-auto mb-1" />
            <p className="text-xs text-muted">Vol. Redirect</p>
            <p className="text-sm font-bold text-warning">
              {diversion.diversion_volume_pct.toFixed(0)}%
            </p>
          </div>
        </div>

        {/* Narrative */}
        <div className="space-y-2">
          <div>
            <span className="text-xs text-muted font-medium">Diversion Narrative</span>
            <p className="text-xs text-foreground leading-relaxed mt-1">
              {diversion.diversion_text}
            </p>
          </div>
          <div>
            <span className="text-xs text-muted font-medium">Why Safer</span>
            <p className="text-xs text-foreground leading-relaxed mt-1">
              {diversion.why_safer}
            </p>
          </div>
        </div>

        {/* Confidence */}
        <div className="flex justify-end mt-3">
          <span className={cn("text-xs font-semibold", confidenceColor(diversion.confidence))}>
            Confidence: {(diversion.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}
