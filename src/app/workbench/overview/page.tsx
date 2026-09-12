"use client";

import React from "react";
import Link from "next/link";
import {
  Building2,
  AlertTriangle,
  FileCheck2,
  Database,
  ArrowUpRight,
  ShieldAlert,
  ArrowRight,
  Layers,
  ChevronRight,
  TrendingUp,
  FileSearch,
  CheckCircle2,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { HeatmapNCIIPC } from "@/components/sites/sat-sa-with-pqc/workbench/ui/HeatmapNCIIPC";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";

export default function OverviewPage() {
  const { entitiesList, selectedCohort, selectedPeriod } = useWorkbench();

  // Filter entities by cohort if selected
  const filteredEntities =
    selectedCohort === "All Cohorts"
      ? entitiesList
      : entitiesList.filter((e) => e.cohort === selectedCohort);

  // Entities requiring attention
  const attentionEntities = filteredEntities.filter(
    (e) => e.band === "high" || e.score > 50
  );

  // Top 5 entity priority ranking
  const topPriorityRanking = [...filteredEntities]
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);

  // Average NCIIPC dimension score across entities
  const avgDimensions = entitiesList[0].nciipcDimensions.map((dim, idx) => {
    const totalScore = entitiesList.reduce(
      (sum, e) => sum + (e.nciipcDimensions[idx]?.score || 0),
      0
    );
    const avgScore = Math.round(totalScore / entitiesList.length);
    return {
      ...dim,
      score: avgScore,
      status: avgScore < 50 ? ("critical_gap" as const) : avgScore < 70 ? ("attention" as const) : ("satisfactory" as const),
    };
  });

  return (
    <div className="space-y-6">
      {/* Page Header / Sub-banner */}
      <div className="flex flex-col gap-1 border-b border-slate-800 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Supervisory Assessment Overview
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Deciding where NCIIPC human review time should go · Period: {selectedPeriod}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/workbench/review-queue"
            className="inline-flex items-center gap-1.5 rounded bg-blue-600 px-3 py-1.5 font-mono text-xs font-semibold text-white shadow hover:bg-blue-500 transition-colors"
          >
            <span>Open Review Queue</span>
            <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </div>

      {/* 4 Top Supervisory Metric Cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {/* Card 1: Assessed Entities */}
        <Link
          href="/workbench/entities"
          className="group relative rounded-lg border border-[#1d2f50] bg-[#0c1628] p-4 transition-all hover:border-blue-500/50 hover:bg-[#0f1d35]"
        >
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="uppercase font-semibold">Assessed Entities</span>
            <Building2 className="size-4 text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-white">
              {filteredEntities.length} CSEs
            </span>
            <span className="text-xs font-mono text-emerald-400">+4 vs Jul</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            All 42 submissions ingested & PQC signature verified
          </p>
          <div className="mt-3 flex items-center text-[11px] font-mono text-blue-400 group-hover:underline">
            <span>View entity table &rarr;</span>
          </div>
        </Link>

        {/* Card 2: Attention Required */}
        <Link
          href="/workbench/entities?filter=attention"
          className="group relative rounded-lg border border-amber-500/30 bg-[#16171f] p-4 transition-all hover:border-amber-500/60 hover:bg-[#1a1b26]"
        >
          <div className="flex items-center justify-between text-xs font-mono text-amber-300">
            <span className="uppercase font-semibold">Attention Required</span>
            <AlertTriangle className="size-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-amber-300">
              8 CSEs
            </span>
            <StatusBadge variant="attention" label="HIGH RISK" size="sm" />
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            5 execution gaps, 3 statistical peer outliers
          </p>
          <div className="mt-3 flex items-center text-[11px] font-mono text-amber-300 group-hover:underline">
            <span>Inspect flagged entities &rarr;</span>
          </div>
        </Link>

        {/* Card 3: Review Samples Due */}
        <Link
          href="/workbench/review-queue"
          className="group relative rounded-lg border border-blue-500/30 bg-[#0c1628] p-4 transition-all hover:border-blue-500/60 hover:bg-[#0f1d35]"
        >
          <div className="flex items-center justify-between text-xs font-mono text-blue-300">
            <span className="uppercase font-semibold">Review Samples Due</span>
            <FileSearch className="size-4 text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-blue-300">
              23 Samples
            </span>
            <span className="text-xs font-mono text-slate-400">due this cycle</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            Ranked by priority reason & evidence count
          </p>
          <div className="mt-3 flex items-center text-[11px] font-mono text-blue-400 group-hover:underline">
            <span>Open manual review queue &rarr;</span>
          </div>
        </Link>

        {/* Card 4: Critical Data-Quality Gaps */}
        <Link
          href="/workbench/submissions"
          className="group relative rounded-lg border border-red-500/30 bg-[#191016] p-4 transition-all hover:border-red-500/60 hover:bg-[#20141c]"
        >
          <div className="flex items-center justify-between text-xs font-mono text-red-300">
            <span className="uppercase font-semibold">Data-Quality Gaps</span>
            <ShieldAlert className="size-4 text-red-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-red-300">
              3 Critical Gaps
            </span>
            <StatusBadge variant="confirmed_concern" label="NEGATIVE SPACE" size="sm" />
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            1 quarantined file, 2 stale inventories (&gt;90d)
          </p>
          <div className="mt-3 flex items-center text-[11px] font-mono text-red-400 group-hover:underline">
            <span>Inspect input verification &rarr;</span>
          </div>
        </Link>
      </div>

      {/* Main Two-Column Analytical Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: Entity Priority Ranking (5 cols) */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 lg:col-span-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-sm font-bold text-white uppercase font-mono">
                Entity Priority Ranking
              </h2>
              <p className="text-[11px] text-slate-400 font-mono">
                Ranked by multi-worker risk fusion · Cycle {selectedPeriod}
              </p>
            </div>
            <Link
              href="/workbench/entities"
              className="text-xs font-mono text-blue-400 hover:underline flex items-center gap-1"
            >
              <span>All 42 CSEs</span>
              <ChevronRight className="size-3" />
            </Link>
          </div>

          <div className="divide-y divide-slate-800/60">
            {topPriorityRanking.map((entity, i) => (
              <div
                key={entity.slug}
                className="py-3 flex flex-col gap-2 transition-colors hover:bg-slate-800/30 px-2 rounded sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex items-start gap-3">
                  <span className="w-5 font-mono text-sm font-bold text-amber-400">
                    {i + 1}.
                  </span>
                  <div>
                    <Link
                      href={`/workbench/entities/${entity.slug}`}
                      className="font-medium text-sm text-slate-200 hover:text-blue-400 transition-colors flex items-center gap-1.5"
                    >
                      <span>{entity.name}</span>
                      <ArrowUpRight className="size-3 text-slate-500" />
                    </Link>
                    <div className="mt-0.5 flex items-center gap-2 text-[11px] font-mono text-slate-400">
                      <span>{entity.sector}</span>
                      <span>·</span>
                      <span className="text-slate-500">{entity.cohort}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3 self-end sm:self-center">
                  <div className="text-right">
                    <div className="font-mono text-xs font-bold text-white">
                      Risk: {entity.score.toFixed(1)}
                    </div>
                    <div className="text-[10px] font-mono text-amber-400 flex items-center gap-0.5 justify-end">
                      {entity.trend === "deteriorating" && (
                        <>
                          <TrendingUp className="size-3 text-red-400" />
                          <span className="text-red-400">+{entity.trendDelta} pts</span>
                        </>
                      )}
                      {entity.trend === "stable" && (
                        <span className="text-slate-400">Stable</span>
                      )}
                      {entity.trend === "improving" && (
                        <span className="text-emerald-400">{entity.trendDelta} pts</span>
                      )}
                    </div>
                  </div>

                  <StatusBadge
                    variant={entity.band === "high" ? "attention" : "neutral"}
                    label={entity.band.toUpperCase()}
                    size="sm"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: NCIIPC Capability Heatmap (6 cols) */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 lg:col-span-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-sm font-bold text-white uppercase font-mono">
                Cohort Capability Heatmap
              </h2>
              <p className="text-[11px] text-slate-400 font-mono">
                Cross-entity performance across 8 NCIIPC statutory dimensions
              </p>
            </div>
            <span className="rounded bg-blue-500/10 border border-blue-500/30 px-2 py-0.5 font-mono text-[10px] text-blue-300 uppercase">
              Benchmark Standard
            </span>
          </div>

          <HeatmapNCIIPC dimensions={avgDimensions} />
        </div>
      </div>

      {/* "Why attention is needed" — Top Corroborated Supervisory Signals */}
      <div className="rounded-lg border border-amber-500/30 bg-[#0f1726] p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-4 text-amber-400" />
            <h2 className="text-sm font-bold uppercase font-mono text-white">
              “Why attention is needed” — Top Corroborated Supervisory Signals
            </h2>
          </div>
          <span className="font-mono text-xs text-amber-300">
            3 High-Confidence Findings
          </span>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {/* Signal 1 */}
          <div className="rounded border border-slate-800 bg-slate-900/80 p-3.5 space-y-2">
            <div className="flex items-center justify-between">
              <StatusBadge variant="attention" label="EXECUTION GAP" size="sm" />
              <span className="font-mono text-[10px] text-slate-400">Confidence: HIGH</span>
            </div>
            <h3 className="font-sans text-sm font-semibold text-slate-100">
              18 critical alerts closed without escalation
            </h3>
            <p className="text-xs text-slate-400">
              Identified across 3 financial entities (CSE-X, ACME-BANK, CSE-011). Average closure duration &lt;4 minutes with zero linked escalation records.
            </p>
            <Link
              href="/workbench/findings/critical-alerts-closed-without-escalation"
              className="inline-block pt-1 font-mono text-xs text-blue-400 hover:underline"
            >
              Drill down to evidence narrative &rarr;
            </Link>
          </div>

          {/* Signal 2 */}
          <div className="rounded border border-slate-800 bg-slate-900/80 p-3.5 space-y-2">
            <div className="flex items-center justify-between">
              <StatusBadge variant="confirmed_concern" label="NEGATIVE SPACE" size="sm" />
              <span className="font-mono text-[10px] text-slate-400">Confidence: HIGH</span>
            </div>
            <h3 className="font-sans text-sm font-semibold text-slate-100">
              CSE-X has no telemetry for 7 critical assets
            </h3>
            <p className="text-xs text-slate-400">
              Registered Tier-1 payment switchgear nodes (SWITCH-PRD-01..06) in active inventory had zero operational audit logs submitted across the 60-day window.
            </p>
            <Link
              href="/workbench/findings/critical-asset-telemetry-absent"
              className="inline-block pt-1 font-mono text-xs text-blue-400 hover:underline"
            >
              Drill down to evidence narrative &rarr;
            </Link>
          </div>

          {/* Signal 3 */}
          <div className="rounded border border-slate-800 bg-slate-900/80 p-3.5 space-y-2">
            <div className="flex items-center justify-between">
              <StatusBadge variant="attention" label="PEER DEVIATION" size="sm" />
              <span className="font-mono text-[10px] text-slate-400">Confidence: HIGH</span>
            </div>
            <h3 className="font-sans text-sm font-semibold text-slate-100">
              CSE-Y closure time is 4.8× faster than peer cohort
            </h3>
            <p className="text-xs text-slate-400">
              SCADA command alerts closed in median 4.8 minutes versus cohort median of 24.0 minutes. 98.4% of notes contain fewer than 15 characters (metric gaming signal).
            </p>
            <Link
              href="/workbench/findings/closure-time-faster-than-cohort"
              className="inline-block pt-1 font-mono text-xs text-blue-400 hover:underline"
            >
              Drill down to evidence narrative &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Assessment-Data Health Panel */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Database className="size-4 text-blue-400" />
            <h2 className="text-sm font-bold uppercase font-mono text-white">
              Assessment-Data Health & Provenance
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            Air-Gapped Ingestion Gate
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 pt-1">
          <div className="rounded border border-slate-800/80 bg-slate-900/50 p-3">
            <span className="text-slate-500 font-mono text-[10px] uppercase block">
              Missing Records
            </span>
            <div className="mt-1 font-mono text-lg font-bold text-amber-300">
              14 unlinked feeds
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Target hosts unmapped to known IP subnets
            </p>
          </div>

          <div className="rounded border border-slate-800/80 bg-slate-900/50 p-3">
            <span className="text-slate-500 font-mono text-[10px] uppercase block">
              Invalid Format Files
            </span>
            <div className="mt-1 font-mono text-lg font-bold text-red-400">
              1 Quarantined
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              CSE-NEG syslog truncated at day 12
            </p>
          </div>

          <div className="rounded border border-slate-800/80 bg-slate-900/50 p-3">
            <span className="text-slate-500 font-mono text-[10px] uppercase block">
              Asset Inventory Freshness
            </span>
            <div className="mt-1 font-mono text-lg font-bold text-amber-300">
              2 Stale (&gt;90d)
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              CSE-NEG (114d), CSE-018 (96d)
            </p>
          </div>

          <div className="rounded border border-slate-800/80 bg-slate-900/50 p-3">
            <span className="text-slate-500 font-mono text-[10px] uppercase block">
              PQC Signature Status
            </span>
            <div className="mt-1 font-mono text-lg font-bold text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 className="size-4" />
              <span>41 / 42 Verified</span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              ML-DSA-65 NIST FIPS 204 Valid
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
