"use client";

import React, { useState } from "react";
import { NciipcDimensionScore } from "../data/entities";
import { StatusBadge } from "./StatusBadge";
import { Info, ChevronDown, ChevronUp } from "lucide-react";

interface HeatmapNCIIPCProps {
  dimensions: NciipcDimensionScore[];
}

export const HeatmapNCIIPC: React.FC<HeatmapNCIIPCProps> = ({
  dimensions,
}) => {
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

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

  return (
    <div className="space-y-2">
      {/* Column Headers */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2 text-[11px] font-mono uppercase tracking-wider text-slate-400">
        <span className="min-w-0">NCIIPC Dimension (8 Core Pillars)</span>
        <div className="flex items-center gap-4 sm:gap-6 shrink-0">
          <span className="w-32 text-left hidden sm:inline-block">Capacity Index</span>
          <span className="w-14 text-right">Delta</span>
          <span className="w-28 text-right">Status</span>
        </div>
      </div>

      {/* Dimension Rows */}
      <div className="divide-y divide-slate-800/60">
        {dimensions.map((dim, idx) => {
          const isCritical = dim.status === "critical_gap" || dim.score < 50;
          const isAttention = dim.status === "attention" || (dim.score >= 50 && dim.score < 70);
          const isExpanded = expandedDim === dim.id;

          const barColor = isCritical
            ? "bg-red-500"
            : isAttention
            ? "bg-amber-400"
            : "bg-emerald-400";

          return (
            <div key={dim.id} className="py-2.5 transition-colors hover:bg-slate-800/30 px-1.5 rounded">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                {/* Dimension Name + Index */}
                <button
                  type="button"
                  onClick={() => setExpandedDim(isExpanded ? null : dim.id)}
                  className="flex items-center gap-2.5 text-left min-w-0 group"
                  aria-expanded={isExpanded}
                >
                  <span className="font-mono text-xs text-slate-500 w-5 shrink-0">
                    {String(idx + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-semibold text-slate-200 group-hover:text-blue-300 transition-colors">
                        {dim.name}
                      </span>
                      {dim.findingCount > 0 && (
                        <span className="rounded bg-slate-800 px-1.5 py-0.2 font-mono text-[10px] text-slate-400 shrink-0">
                          {dim.findingCount} {dim.findingCount === 1 ? "finding" : "findings"}
                        </span>
                      )}
                      {isExpanded ? (
                        <ChevronUp className="size-3 text-slate-500" />
                      ) : (
                        <ChevronDown className="size-3 text-slate-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                      )}
                    </div>
                  </div>
                </button>

                {/* Quantitative Capacity + Delta + Status */}
                <div className="flex items-center gap-4 sm:gap-6 shrink-0 self-end sm:self-center">
                  {/* Capacity Bar + Score */}
                  <div className="flex items-center gap-2 w-32 justify-end sm:justify-start">
                    <div className="h-2 w-20 rounded-full bg-slate-800 overflow-hidden shrink-0">
                      <div
                        className={`h-full rounded-full ${barColor}`}
                        style={{ width: `${Math.max(5, Math.min(100, dim.score))}%` }}
                      />
                    </div>
                    <span className="w-9 text-right font-mono text-xs font-bold text-slate-200">
                      {dim.score}%
                    </span>
                  </div>

                  {/* Cohort Delta */}
                  <div className="w-14 text-right font-mono text-xs font-medium">
                    {dim.benchmarkDelta < 0 ? (
                      <span className="text-amber-400">
                        {dim.benchmarkDelta}%
                      </span>
                    ) : dim.benchmarkDelta > 0 ? (
                      <span className="text-emerald-400">
                        +{dim.benchmarkDelta}%
                      </span>
                    ) : (
                      <span className="text-slate-500">0%</span>
                    )}
                  </div>

                  {/* Status Badge without truncation */}
                  <div className="w-28 shrink-0 flex justify-end">
                    {isCritical ? (
                      <StatusBadge
                        variant="confirmed_concern"
                        label="CRITICAL GAP"
                        size="sm"
                        icon="alert-triangle"
                      />
                    ) : isAttention ? (
                      <StatusBadge
                        variant="attention"
                        label="ATTENTION"
                        size="sm"
                        icon="alert-triangle"
                      />
                    ) : (
                      <StatusBadge
                        variant="verified"
                        label="SATISFACTORY"
                        size="sm"
                        icon="check"
                      />
                    )}
                  </div>
                </div>
              </div>

              {/* Progressive Disclosure: Dimension details & supervisory context */}
              {isExpanded && (
                <div className="mt-2.5 rounded bg-slate-900/90 border border-slate-800 p-3 text-xs text-slate-300 space-y-1.5 animate-in fade-in duration-150">
                  <div className="flex items-start gap-2">
                    <Info className="size-3.5 text-blue-400 mt-0.5 shrink-0" />
                    <div>
                      <p className="text-slate-300">
                        {dimensionDescriptions[dim.id] || "Assessed through automated correlation and examiner inspection."}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-4 text-[11px] font-mono text-slate-400">
                        <span>Cohort Baseline: <strong>{dim.score - dim.benchmarkDelta}%</strong></span>
                        <span>Cycle Deviation: <strong className={dim.benchmarkDelta < 0 ? "text-amber-400" : "text-emerald-400"}>{dim.benchmarkDelta > 0 ? `+${dim.benchmarkDelta}` : dim.benchmarkDelta}%</strong></span>
                        <span>Examiner Action: <strong>{isCritical ? "Mandatory manual sample review" : isAttention ? "Secondary verification recommended" : "No supervisory intervention required"}</strong></span>
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
