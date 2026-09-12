"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, Info } from "lucide-react";
import { NciipcDimensionScore } from "../data/entities";
import { StatusBadge } from "./StatusBadge";

interface HeatmapNCIIPCProps {
  dimensions: NciipcDimensionScore[];
}

const dimensionDescriptions: Record<string, string> = {
  threat_detection: "Real-time threat surface monitoring, sensor coverage, and rule-firing fidelity.",
  investigation: "Triage depth, query rigor, evidence attachment, and analytical note completeness.",
  escalation: "Escalation discipline, threshold fidelity, and handoff integrity to Tier-2 / CERT-In.",
  incident_response: "Containment latency, playbook adherence, forensic isolation, and post-mortem closure.",
  secops: "Toolchain health, agent uptime, signature freshness, and SIEM pipeline latency.",
  governance: "Compliance tracking, audit trail immutability, and supervisory mandate alignment.",
  discipline: "Shift handoff rigor, alert closure hygiene, note verbosity, and queue pacing.",
  resilience: "Redundancy failover, backup verification, air-gap retention, and disaster recovery posture.",
};

export const HeatmapNCIIPC: React.FC<HeatmapNCIIPCProps> = ({ dimensions }) => {
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  return (
    <div>
      <div className="grid grid-cols-[minmax(0,1fr)_64px_128px] gap-3 border-b border-slate-800 px-2 pb-2 font-mono text-xs uppercase tracking-wide text-slate-400">
        <span>Dimension</span>
        <span className="text-center">Index</span>
        <span className="text-right">Status</span>
      </div>

      <div className="divide-y divide-slate-800/60">
        {dimensions.map((dim, idx) => {
          const isCritical = dim.status === "critical_gap" || dim.score < 50;
          const isAttention = dim.status === "attention" || (dim.score >= 50 && dim.score < 70);
          const isExpanded = expandedDim === dim.id;

          return (
            <div key={dim.id} className="py-1">
              <button
                type="button"
                onClick={() => setExpandedDim(isExpanded ? null : dim.id)}
                className="grid min-h-12 w-full grid-cols-[minmax(0,1fr)_64px_128px] items-center gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-slate-800/40"
                aria-expanded={isExpanded}
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  <span className="shrink-0 font-mono text-xs text-slate-500">{String(idx + 1).padStart(2, "0")}</span>
                  <span className="min-w-0 text-sm font-medium leading-snug text-slate-200">{dim.name}</span>
                  {isExpanded ? (
                    <ChevronUp className="size-4 shrink-0 text-slate-500" aria-hidden="true" />
                  ) : (
                    <ChevronDown className="size-4 shrink-0 text-slate-500" aria-hidden="true" />
                  )}
                </span>

                <span className="text-center font-mono text-sm font-bold tabular-nums text-slate-100">{dim.score}</span>

                <span className="flex justify-end">
                  {isCritical ? (
                    <StatusBadge variant="confirmed_concern" label="CRITICAL GAP" size="sm" icon="alert-triangle" />
                  ) : isAttention ? (
                    <StatusBadge variant="attention" label="WATCH" size="sm" icon="alert-triangle" />
                  ) : (
                    <StatusBadge variant="verified" label="SATISFACTORY" size="sm" icon="check" />
                  )}
                </span>
              </button>

              {isExpanded && (
                <div className="mx-2 mb-2 rounded-md bg-slate-900/80 p-3 text-sm leading-6 text-slate-300">
                  <div className="flex items-start gap-2">
                    <Info className="mt-1 size-4 shrink-0 text-blue-400" aria-hidden="true" />
                    <div>
                      <p>{dimensionDescriptions[dim.id] || "Assessed through automated correlation and examiner inspection."}</p>
                      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 font-mono text-xs text-slate-400">
                        <span>Cohort baseline: <strong>{dim.score - dim.benchmarkDelta}</strong></span>
                        <span>Cycle deviation: <strong>{dim.benchmarkDelta > 0 ? `+${dim.benchmarkDelta}` : dim.benchmarkDelta}</strong></span>
                        <span>{dim.findingCount} {dim.findingCount === 1 ? "finding" : "findings"}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
