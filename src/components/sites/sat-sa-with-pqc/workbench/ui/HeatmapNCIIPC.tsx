"use client";

import React from "react";
import { NciipcDimensionScore } from "../data/entities";
import { StatusBadge } from "./StatusBadge";

interface HeatmapNCIIPCProps {
  dimensions: NciipcDimensionScore[];
  onSelectDimension?: (id: string) => void;
}

export const HeatmapNCIIPC: React.FC<HeatmapNCIIPCProps> = ({
  dimensions,
}) => {
  // Convert 0-100 score to 5-block ASCII-style meter: ███░░
  const getAsciiBlocks = (score: number) => {
    const filled = Math.round((score / 100) * 5);
    return "█".repeat(filled) + "░".repeat(5 - filled);
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2 text-xs font-mono uppercase tracking-wider text-slate-400">
        <span>NCIIPC Dimension (8 Core Pillars)</span>
        <div className="flex items-center gap-6">
          <span>Capacity Index</span>
          <span>Cohort Delta</span>
        </div>
      </div>

      <div className="divide-y divide-slate-800/60">
        {dimensions.map((dim) => {
          const isCritical = dim.status === "critical_gap" || dim.score < 50;
          const isAttention = dim.status === "attention" || (dim.score >= 50 && dim.score < 70);

          return (
            <div
              key={dim.id}
              className="group flex flex-col gap-2 py-2.5 transition-colors hover:bg-slate-800/30 sm:flex-row sm:items-center sm:justify-between px-1.5 rounded"
            >
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-slate-500 w-5">
                  {dim.id === "threat_detection" && "01"}
                  {dim.id === "investigation" && "02"}
                  {dim.id === "escalation" && "03"}
                  {dim.id === "incident_response" && "04"}
                  {dim.id === "secops" && "05"}
                  {dim.id === "governance" && "06"}
                  {dim.id === "discipline" && "07"}
                  {dim.id === "resilience" && "08"}
                </span>

                <div className="flex flex-col">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200 group-hover:text-white">
                      {dim.name}
                    </span>
                    {dim.findingCount > 0 && (
                      <span className="rounded bg-slate-800 px-1.5 py-0.2 font-mono text-[11px] text-slate-400">
                        {dim.findingCount} {dim.findingCount === 1 ? "finding" : "findings"}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 sm:gap-6 self-end sm:self-center">
                {/* Visual Block Meter */}
                <div className="flex items-center gap-2">
                  <span
                    className={`font-mono text-xs tracking-widest ${
                      isCritical
                        ? "text-red-400"
                        : isAttention
                        ? "text-amber-400"
                        : "text-emerald-400"
                    }`}
                  >
                    {getAsciiBlocks(dim.score)}
                  </span>
                  <span className="w-10 text-right font-mono text-xs font-semibold text-slate-300">
                    {dim.score}%
                  </span>
                </div>

                {/* Cohort Delta */}
                <div className="w-16 text-right font-mono text-xs">
                  {dim.benchmarkDelta < 0 ? (
                    <span className="text-amber-400">
                      {dim.benchmarkDelta}%
                    </span>
                  ) : dim.benchmarkDelta > 0 ? (
                    <span className="text-emerald-400">
                      +{dim.benchmarkDelta}%
                    </span>
                  ) : (
                    <span className="text-slate-400">0%</span>
                  )}
                </div>

                {/* Badge */}
                <div className="w-28 text-right">
                  {isCritical ? (
                    <StatusBadge
                      variant="attention"
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
          );
        })}
      </div>
    </div>
  );
};
