"use client";

import React, { useState } from "react";
import { AlertTriangle, ChevronDown, OctagonAlert } from "lucide-react";
import { NciipcDimensionScore } from "../data/entities";

interface HeatmapNCIIPCProps {
  dimensions: NciipcDimensionScore[];
  compact?: boolean;
}

const dimensionDescriptions: Record<string, string> = {
  threat_detection: "Sensor coverage and rule-firing fidelity.",
  investigation: "Triage depth, evidence attachment and note completeness.",
  escalation: "Escalation thresholds and handoff integrity to Tier-2 and CERT-In.",
  incident_response: "Containment latency, playbook adherence and post-incident closure.",
  secops: "Toolchain health, agent uptime and SIEM pipeline latency.",
  governance: "Compliance tracking and audit-trail immutability.",
  discipline: "Shift handoff rigor, closure hygiene and queue pacing.",
  resilience: "Failover, backup verification and recovery posture.",
};

export function capabilityTone(dim: NciipcDimensionScore) {
  if (dim.status === "critical_gap" || dim.score < 50) {
    return { fill: "bg-red-600", text: "text-red-700", label: "Critical gap", Icon: OctagonAlert };
  }
  if (dim.status === "attention" || dim.score < 70) {
    return { fill: "bg-orange-500", text: "text-orange-700", label: "Needs attention", Icon: AlertTriangle };
  }
  return { fill: "bg-violet-600", text: "text-slate-950", label: "Satisfactory", Icon: null };
}

export function CapabilityBar({ dim }: { dim: NciipcDimensionScore }) {
  const tone = capabilityTone(dim);
  const StatusIcon = tone.Icon;
  return (
    <>
      <span className="min-w-0 truncate text-sm text-slate-700">{dim.name}</span>
      <span className="relative h-1.5 overflow-hidden rounded-full bg-slate-200/80" aria-hidden="true">
        <span
          className={`absolute inset-y-0 left-0 rounded-full ${tone.fill}`}
          style={{ width: `${Math.max(0, Math.min(100, dim.score))}%` }}
        />
      </span>
      <span className={`flex items-center justify-end gap-1 font-mono text-sm font-semibold tabular-nums ${tone.text}`}>
        {StatusIcon && <StatusIcon className="size-3.5" strokeWidth={2} aria-hidden="true" />}
        {dim.score}
        <span className="sr-only">out of 100, {tone.label}</span>
      </span>
    </>
  );
}

export const HeatmapNCIIPC: React.FC<HeatmapNCIIPCProps> = ({ dimensions }) => {
  const [expandedDim, setExpandedDim] = useState<string | null>(null);

  return (
    <ul className="divide-y divide-slate-200/80">
      {dimensions.map((dim) => {
        const isExpanded = expandedDim === dim.id;
        return (
          <li key={dim.id}>
            <button
              type="button"
              onClick={() => setExpandedDim(isExpanded ? null : dim.id)}
              aria-expanded={isExpanded}
              title={dimensionDescriptions[dim.id]}
              className="grid min-h-11 w-full grid-cols-[minmax(0,11rem)_minmax(0,1fr)_4rem_1rem] items-center gap-4 rounded-md px-2 text-left transition-colors hover:bg-violet-50/60"
            >
              <CapabilityBar dim={dim} />
              <ChevronDown
                className={`size-4 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                aria-hidden="true"
              />
            </button>

            {isExpanded && (
              <div className="mx-2 mb-3 grid gap-2 rounded-lg bg-slate-50 px-3 py-2.5 text-sm text-slate-600 sm:grid-cols-[1fr_auto]">
                <p>{dimensionDescriptions[dim.id] ?? "Assessed through automated correlation and examiner inspection."}</p>
                <dl className="flex gap-4 font-mono text-xs text-slate-500">
                  <div>
                    <dt className="sr-only">Cohort baseline</dt>
                    <dd title="Cohort baseline">
                      Baseline <strong className="text-slate-900">{dim.score - dim.benchmarkDelta}</strong>
                    </dd>
                  </div>
                  <div>
                    <dt className="sr-only">Deviation from cohort</dt>
                    <dd title="Deviation from cohort" className={dim.benchmarkDelta < 0 ? "text-orange-700" : "text-blue-700"}>
                      {dim.benchmarkDelta > 0 ? `+${dim.benchmarkDelta}` : dim.benchmarkDelta}
                    </dd>
                  </div>
                  <div>
                    <dt className="sr-only">Findings</dt>
                    <dd title="Findings">{dim.findingCount} findings</dd>
                  </div>
                </dl>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
};
