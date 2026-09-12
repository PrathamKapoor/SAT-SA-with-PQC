"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  FileSearch,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
  Filter,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { findings } from "@/components/sites/sat-sa-with-pqc/workbench/data/findings";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";

export default function FindingsListPage() {
  const [familyFilter, setFamilyFilter] = useState("All");

  const filteredFindings = findings.filter((f) => {
    if (familyFilter !== "All" && f.findingFamily !== familyFilter) return false;
    return true;
  });

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Supervisory Findings Repository
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Readable evidence narratives with statistical peer context · Cycle: Aug–Sep 2026
          </p>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="flex items-center gap-3 rounded-lg border border-slate-800 bg-[#0c1424] p-3 text-xs font-mono">
        <div className="flex items-center gap-2">
          <Filter className="size-3.5 text-slate-400" />
          <span className="text-slate-400 uppercase text-[10px]">Family:</span>
          <select
            aria-label="Filter by Finding Family"
            value={familyFilter}
            onChange={(e) => setFamilyFilter(e.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200 focus:outline-none"
          >
            <option value="All">All Finding Families</option>
            <option value="execution_gap">Execution Gap</option>
            <option value="negative_space">Negative Space</option>
            <option value="peer_deviation">Peer Deviation</option>
            <option value="anomaly">Anomaly</option>
          </select>
        </div>
      </div>

      {/* Findings List */}
      <div className="space-y-4">
        {filteredFindings.map((finding) => (
          <div
            key={finding.id}
            className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3 hover:border-slate-700 transition-colors"
          >
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800/80 pb-3">
              <div className="flex items-center gap-2.5">
                <StatusBadge
                  variant={finding.severity === "critical" ? "confirmed_concern" : "attention"}
                  label={finding.findingFamilyLabel.toUpperCase()}
                  size="sm"
                />
                <Link
                  href={`/workbench/findings/${finding.findingSlug}`}
                  className="font-bold text-base text-white hover:text-blue-400 transition-colors"
                >
                  {finding.title}
                </Link>
              </div>

              <span className="font-mono text-xs text-slate-400">
                Confidence: <strong className="text-emerald-400 uppercase">{finding.confidence}</strong>
              </span>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-12 text-xs">
              <div className="md:col-span-8 space-y-2">
                <p className="text-slate-300 font-sans leading-relaxed">
                  <strong className="text-amber-400 font-mono text-[11px] uppercase block mb-0.5">
                    Observed Pattern:
                  </strong>
                  {finding.observedPattern}
                </p>
                <div className="rounded bg-slate-900/60 p-2.5 border border-slate-800/60 text-slate-400 text-[11px] font-sans">
                  <strong className="text-slate-300 font-mono uppercase text-[10px] block">
                    Why this matters:
                  </strong>
                  {finding.whyThisMatters}
                </div>
              </div>

              <div className="md:col-span-4 flex flex-col justify-between border-t border-slate-800/80 pt-3 md:border-t-0 md:border-l md:pl-4 space-y-2 font-mono text-[11px]">
                <div className="space-y-1 text-slate-400">
                  <div>Entity: <strong className="text-white">{finding.entityName}</strong></div>
                  <div>Cohort: <span className="text-blue-300">{finding.peerContext.cohortName}</span></div>
                  <div>Evidence: <strong className="text-slate-200">{finding.evidenceRecords.length} records</strong></div>
                </div>

                <Link
                  href={`/workbench/findings/${finding.findingSlug}`}
                  className="inline-flex items-center justify-between rounded bg-blue-600 px-3 py-1.5 font-semibold text-white hover:bg-blue-500 transition-colors"
                >
                  <span>Open Finding Detail</span>
                  <ArrowRight className="size-3.5" />
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
