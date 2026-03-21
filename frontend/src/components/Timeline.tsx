/* ── Timeline — auto-generated timestamped event log ── */
"use client";

import { Clock, AlertTriangle, Navigation, TrafficCone, Bell, Brain, Download } from "lucide-react";
import { useTrafficStore } from "@/lib/store";
import { formatTime } from "@/lib/utils";

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  incident: <AlertTriangle className="w-3 h-3 text-danger" />,
  signal: <TrafficCone className="w-3 h-3 text-amber-600" />,
  routing: <Navigation className="w-3 h-3 text-primary" />,
  alert: <Bell className="w-3 h-3 text-sky-500" />,
  supervisor: <Brain className="w-3 h-3 text-purple-600" />,
  system: <Clock className="w-3 h-3 text-muted" />,
};

export default function Timeline() {
  const timeline = useTrafficStore((s) => s.timeline);

  const exportCSV = () => {
    const csv = [
      "Timestamp,Event,Category",
      ...timeline.map(
        (t) => `"${t.timestamp}","${t.event}","${t.category}"`
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "traffic_timeline.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!timeline.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted py-12">
        <Clock className="w-10 h-10 mb-3 text-slate-300" />
        <p className="text-sm font-medium">No timeline events</p>
        <p className="text-xs mt-1">Events appear as agents process incidents</p>
      </div>
    );
  }

  return (
    <div className="p-1">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            Event Timeline ({timeline.length})
          </h3>
        </div>
        <button
          onClick={exportCSV}
          className="flex items-center gap-1 text-[10px] text-primary hover:text-primary/80 transition-colors"
        >
          <Download className="w-3 h-3" />
          Export CSV
        </button>
      </div>

      <div className="space-y-0">
        {timeline.map((entry, i) => (
          <div key={i} className="flex gap-3 group">
            {/* Timeline line */}
            <div className="flex flex-col items-center">
              <div className="w-5 h-5 rounded-full border-2 border-border bg-white flex items-center justify-center z-10 group-hover:border-primary transition-colors">
                {CATEGORY_ICONS[entry.category] || CATEGORY_ICONS.system}
              </div>
              {i < timeline.length - 1 && (
                <div className="w-px flex-1 bg-border" />
              )}
            </div>
            {/* Content */}
            <div className="pb-4 flex-1">
              <p className="text-xs text-foreground leading-relaxed">
                {entry.event}
              </p>
              <p className="text-[10px] text-muted mt-0.5">
                {formatTime(entry.timestamp)}
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
