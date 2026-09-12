"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";
import { HeatmapNCIIPC } from "@/components/sites/sat-sa-with-pqc/workbench/ui/HeatmapNCIIPC";
import { OfflineLineChart } from "@/components/sites/sat-sa-with-pqc/workbench/ui/OfflineChart";
import { EvidenceViewer } from "@/components/sites/sat-sa-with-pqc/workbench/ui/EvidenceViewer";
import { findings } from "@/components/sites/sat-sa-with-pqc/workbench/data/findings";
import { closureTimeTrend } from "@/components/sites/sat-sa-with-pqc/workbench/data/trends";

export default function EntityProfilePage() {
  const params = useParams();
  const slug = (params.id as string)?.toLowerCase();
  const { entitiesList, selectedPeriod } = useWorkbench();

  const entity = entitiesList.find((e) => e.slug === slug) || entitiesList[0];
  const entityFindings = findings.filter((f) => f.entitySlug === entity.slug);

  const [activeTab, setActiveTab] = useState<
    "scorecard" | "trend" | "findings" | "evidence" | "history"
  >("scorecard");

  return (
    <div className="space-y-6">
      {/* Back Link */}
      <div className="flex items-center justify-between">
        <Link
          href="/workbench/entities"
          className="inline-flex items-center gap-1.5 font-mono text-xs text-blue-400 hover:underline"
        >
          <ArrowLeft className="size-3.5" />
          <span>Back to All Entities</span>
        </Link>
        <span className="font-mono text-xs text-slate-400">
          NCIIPC Statutory Profile · Cycle: {selectedPeriod}
        </span>
      </div>

      {/* Entity Profile Header Card */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold tracking-tight text-white">
                {entity.name}
              </h1>
              <StatusBadge
                variant={entity.band === "high" ? "attention" : "verified"}
                label={`${entity.band.toUpperCase()} PRIORITY`}
                size="md"
              />
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs font-mono text-slate-300">
              <div>
                <span className="text-slate-500 uppercase">Sector:</span>{" "}
                <strong className="text-slate-200">{entity.sector}</strong>
              </div>
              <div>
                <span className="text-slate-500 uppercase">Environment:</span>{" "}
                <strong className="text-slate-200">{entity.environment}</strong>
              </div>
              <div>
                <span className="text-slate-500 uppercase">Peer Cohort:</span>{" "}
                <strong className="text-blue-300">{entity.cohort}</strong>
              </div>
              <div>
                <span className="text-slate-500 uppercase">Confidence:</span>{" "}
                <strong className="text-slate-200 capitalize">{entity.confidence}</strong>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start">
            <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 font-mono text-xs text-emerald-300 flex items-center gap-1">
              <ShieldCheck className="size-3.5" />
              <span>PQC Signature Verified</span>
            </span>
          </div>
        </div>

        {/* Top Concerns & Decomposable Risk Score Highlights */}
        <div className="grid grid-cols-1 gap-4 pt-2 md:grid-cols-12 border-t border-slate-800/80">
          {/* Top Concerns List (7 cols) */}
          <div className="md:col-span-7 space-y-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-amber-400 font-semibold block">
              Top Supervisory Concerns ({entity.topConcerns.length})
            </span>
            <ul className="space-y-1.5 text-xs text-slate-200">
              {entity.topConcerns.map((concern, idx) => (
                <li key={idx} className="flex items-start gap-2 bg-slate-900/60 p-2 rounded border border-slate-800/60">
                  <span className="font-mono text-amber-400 font-bold">{idx + 1}.</span>
                  <span>{concern}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Why This Score Summary (5 cols) */}
          <div className="md:col-span-5 rounded border border-slate-800 bg-slate-900/60 p-3 space-y-2 font-mono text-xs">
            <span className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block">
              Why this score? (Risk: {entity.score.toFixed(1)} / 100)
            </span>
            <div className="space-y-1 text-slate-300 text-[11px]">
              {entity.scoreDecomposition.slice(0, 3).map((item, i) => (
                <div key={i} className="flex items-center justify-between border-b border-slate-800/50 pb-1">
                  <span className="text-slate-400 truncate max-w-[210px]">{item.factor.split(":")[0]}</span>
                  <span className="text-amber-300 font-semibold">+{item.subscore.toFixed(1)} pts</span>
                </div>
              ))}
            </div>
            <p className="text-[10px] text-slate-500 pt-1">
              Decomposable formula: weights, corroborated cases, and source verification listed below.
            </p>
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-slate-800">
        <div className="flex gap-2 font-mono text-xs">
          {[
            { id: "scorecard" as const, label: "Capability Scorecard" },
            { id: "trend" as const, label: "Historical Trend" },
            { id: "findings" as const, label: `Findings (${entityFindings.length})` },
            { id: "evidence" as const, label: "Raw Normalized Evidence" },
            { id: "history" as const, label: "Review History Ledger" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`border-b-2 px-3.5 py-2.5 font-medium transition-colors ${
                activeTab === tab.id
                  ? "border-blue-500 text-blue-400 bg-blue-500/10 font-bold"
                  : "border-transparent text-slate-400 hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content 1: Capability Scorecard & Decomposable Score Breakdown */}
      {activeTab === "scorecard" && (
        <div className="space-y-6">
          <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4">
            <h2 className="text-sm font-bold uppercase font-mono text-white">
              NCIIPC 8-Dimension Statutory Evaluation
            </h2>
            <HeatmapNCIIPC dimensions={entity.nciipcDimensions} />
          </div>

          {/* Explicit Decomposable Risk Model Table */}
          <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white uppercase">
                  Decomposable Risk Model Factors
                </h3>
                <p className="text-slate-400 text-[11px]">
                  Every risk factor is bounded, explainable, and bound to verified source records
                </p>
              </div>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-300">
                Formula: &Sigma; (Weight &times; Raw Subscore) = {entity.score.toFixed(1)}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 bg-slate-900/80 text-[10px] uppercase text-slate-400">
                    <th className="py-2.5 px-3">Risk Factor</th>
                    <th className="py-2.5 px-3">Weight</th>
                    <th className="py-2.5 px-3">Subscore</th>
                    <th className="py-2.5 px-3">Corroborated Records</th>
                    <th className="py-2.5 px-3">Confidence</th>
                    <th className="py-2.5 px-3">Limitation Boundary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {entity.scoreDecomposition.map((f, i) => (
                    <tr key={i} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-semibold text-slate-200">
                        {f.factor}
                      </td>
                      <td className="py-2.5 px-3">{f.weightPct}%</td>
                      <td className="py-2.5 px-3 text-amber-300 font-bold">
                        {f.subscore.toFixed(1)}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 font-sans text-[11px]">
                        {f.sourceRecords}
                      </td>
                      <td className="py-2.5 px-3">
                        <StatusBadge
                          variant={f.confidence === "high" ? "verified" : "neutral"}
                          label={f.confidence.toUpperCase()}
                          size="sm"
                        />
                      </td>
                      <td className="py-2.5 px-3 text-[11px] text-slate-400 font-sans">
                        {f.limitations}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Tab Content 2: Historical Trend */}
      {activeTab === "trend" && (
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-sm font-bold uppercase font-mono text-white">
                Multi-Cycle Risk Trajectory (March – September 2026)
              </h2>
              <p className="text-xs font-mono text-slate-400">
                Tracking closure times and escalation discipline versus cohort median
              </p>
            </div>
          </div>

          <OfflineLineChart
            data={closureTimeTrend}
            metricKey1={entity.slug === "cse-y" ? "cseyValue" : "csexValue"}
            metricLabel1={`${entity.slug.toUpperCase()} Closure Velocity`}
            metricColor1="#f59e0b"
            metricKey2="cohortMedian"
            metricLabel2="Cohort Median"
            metricColor2="#3b82f6"
            baselineKey="sectorBaseline"
            baselineLabel="Sector Baseline"
            yUnit=" min"
            height={280}
          />
        </div>
      )}

      {/* Tab Content 3: Findings */}
      {activeTab === "findings" && (
        <div className="space-y-4">
          {entityFindings.length === 0 ? (
            <div className="rounded border border-slate-800 p-8 text-center font-mono text-slate-400 text-xs">
              No open high-severity findings registered for this entity in cycle {selectedPeriod}.
            </div>
          ) : (
            entityFindings.map((finding) => (
              <div
                key={finding.id}
                className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StatusBadge
                      variant={finding.severity === "critical" ? "confirmed_concern" : "attention"}
                      label={finding.findingFamilyLabel.toUpperCase()}
                      size="sm"
                    />
                    <h3 className="font-sans text-base font-bold text-white">
                      {finding.title}
                    </h3>
                  </div>
                  <Link
                    href={`/workbench/findings/${finding.findingSlug}`}
                    className="font-mono text-xs text-blue-400 hover:underline"
                  >
                    Open Evidence Narrative &rarr;
                  </Link>
                </div>

                <p className="text-xs text-slate-300 font-sans">
                  {finding.observedPattern}
                </p>

                <div className="flex flex-wrap items-center gap-4 text-xs font-mono text-slate-400 border-t border-slate-800/60 pt-2">
                  <span>Confidence: <strong className="text-white">{finding.confidence.toUpperCase()}</strong></span>
                  <span>·</span>
                  <span>Rule: <code>{finding.ruleOrCategory}</code></span>
                  <span>·</span>
                  <span>Evidence: {finding.evidenceRecords.length} records</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab Content 4: Raw Normalized Evidence */}
      {activeTab === "evidence" && (
        <EvidenceViewer
          records={entityFindings[0]?.evidenceRecords || []}
          submissionId={entityFindings[0]?.submissionId || "SUB-2026-08-001"}
          contentHashSha3={entityFindings[0]?.contentHashSha3}
        />
      )}

      {/* Tab Content 5: Review History Ledger */}
      {activeTab === "history" && (
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h2 className="text-sm font-bold uppercase text-white">
              Supervisory Review Ledger for {entity.name}
            </h2>
            <span className="text-emerald-400 text-[11px] flex items-center gap-1">
              <CheckCircle2 className="size-3.5" />
              <span>Immutable Chain Verified</span>
            </span>
          </div>

          <div className="space-y-3">
            <div className="rounded border border-slate-800 bg-slate-900/60 p-3 space-y-1 text-slate-300">
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Block #100 · 2026-08-31 23:59:12 UTC</span>
                <span className="text-emerald-400">PQC Signed</span>
              </div>
              <p className="font-semibold text-white">Periodic Submission Ingested (1,428,912 records)</p>
              <p className="text-slate-400 text-[11px]">
                Actor: INGEST_DAEMON_AIRGAP · Digest: e3b0c44298fc1c14...
              </p>
            </div>

            <div className="rounded border border-slate-800 bg-slate-900/60 p-3 space-y-1 text-slate-300">
              <div className="flex items-center justify-between text-[11px] text-slate-400">
                <span>Block #101 · 2026-09-01 02:15:30 UTC</span>
                <span className="text-emerald-400">PQC Signed</span>
              </div>
              <p className="font-semibold text-white">Analysis Run Completed (16 analytical workers)</p>
              <p className="text-slate-400 text-[11px]">
                Actor: SYSTEM_SUPERVISOR_RUNNER · Generated 24 findings. Risk score evaluated: 78.4.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
