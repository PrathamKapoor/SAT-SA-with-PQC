"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Building2,
  AlertTriangle,
  Database,
  ArrowUpRight,
  ShieldAlert,
  ArrowRight,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Minus,
  FileSearch,
  CheckCircle2,
  HelpCircle,
  ShieldCheck,
  X,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { HeatmapNCIIPC } from "@/components/sites/sat-sa-with-pqc/workbench/ui/HeatmapNCIIPC";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";
import { Entity } from "@/components/sites/sat-sa-with-pqc/workbench/data/entities";

export default function OverviewPage() {
  const { entitiesList, selectedCohort, selectedPeriod } = useWorkbench();
  const [scoreModalEntity, setScoreModalEntity] = useState<Entity | null>(null);

  // Filter entities by cohort if selected
  const filteredEntities =
    selectedCohort === "All Cohorts"
      ? entitiesList
      : entitiesList.filter((e) => e.cohort === selectedCohort);

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
    <div data-workbench-overview="true" className="workbench-overview mx-auto w-full max-w-[1480px] space-y-10">
      {/* 1. Action-Led Header & Assessment Status Banner */}
      <section className="workbench-overview__hero rounded-[20px] border border-[#1b2b48] bg-[#0c1628] p-6 sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2.5">
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
              <span className="size-2 rounded-full bg-blue-400" />
              <span>Supervisory assessment</span>
              <span>&middot;</span>
              <span className="text-slate-300 font-semibold">{selectedPeriod}</span>
              <span>&middot;</span>
              <span className="text-slate-300">{selectedCohort}</span>
            </div>
            <h1 className="text-2xl font-bold tracking-[-0.035em] text-white sm:text-[32px] sm:leading-tight">
              Supervisory Assessment Overview
            </h1>
            {/* Status Summary Banner */}
            <div className="flex flex-wrap items-center gap-2 pt-1 text-sm">
              <span className="text-slate-400 font-medium">Assessment status:</span>
              <span className="inline-flex items-center gap-1 rounded bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-amber-300 font-semibold">
                <AlertTriangle className="size-3" />
                8 CSEs require attention
              </span>
              <span className="text-slate-600">&middot;</span>
              <span className="inline-flex items-center gap-1 rounded bg-blue-500/15 border border-blue-500/30 px-2 py-0.5 text-blue-300 font-semibold">
                <FileSearch className="size-3" />
                23 review samples due
              </span>
              <span className="text-slate-600">&middot;</span>
              <span className="inline-flex items-center gap-1 rounded bg-red-500/15 border border-red-500/30 px-2 py-0.5 text-red-300 font-semibold">
                <ShieldAlert className="size-3" />
                3 critical data/evidence gaps
              </span>
            </div>
          </div>

          {/* Primary Action Button */}
          <div className="flex items-center gap-3 shrink-0">
            <Link
              href="/workbench/review-queue"
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-[0_12px_30px_rgba(37,99,235,0.26)] transition-[background-color,box-shadow,transform] hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow-[0_16px_34px_rgba(37,99,235,0.32)] active:translate-y-0"
            >
              <FileSearch className="size-4" />
              <span>Open Review Queue</span>
              <span className="rounded-md bg-blue-800 px-2 py-0.5 text-xs">23 due</span>
              <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </div>
      </section>

      {/* 2. Four KPI Cards with Clean Semantic Hierarchy */}
      <section className="workbench-overview__metrics grid grid-cols-1 gap-px sm:grid-cols-2 xl:grid-cols-4">
        {/* Card 1: Assessed Entities (Neutral Slate) */}
        <Link
          href="/workbench/entities"
          className="workbench-metric group border border-slate-800 bg-[#0a1222] p-5 focus-visible:ring-2 focus-visible:ring-blue-500 sm:p-6"
        >
          <div className="flex items-center justify-between text-sm text-slate-400">
            <span className="font-semibold">Assessed entities</span>
            <Building2 className="size-4 text-slate-400" />
          </div>
          <div className="mt-2.5">
            <div className="text-4xl font-bold tracking-[-0.05em] text-slate-100">
              {filteredEntities.length}
            </div>
            <div className="mt-1 text-sm font-medium text-slate-200">
              CSEs assessed
            </div>
            <div className="mt-1 text-xs text-slate-400">
              +4 vs previous cycle
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-slate-800/80 pt-3 text-xs font-semibold text-blue-600">
            <span>View entity roster</span>
            <span>&rarr;</span>
          </div>
        </Link>

        {/* Card 2: Attention Required (Amber Warning) */}
        <Link
          href="/workbench/entities?filter=attention"
          className="workbench-metric workbench-metric--attention group border border-amber-500/30 bg-[#14151e] p-5 focus-visible:ring-2 focus-visible:ring-amber-500 sm:p-6"
        >
          <div className="flex items-center justify-between text-sm text-amber-400">
            <span className="font-semibold">Attention required</span>
            <AlertTriangle className="size-4 text-amber-400" />
          </div>
          <div className="mt-2.5">
            <div className="text-4xl font-bold tracking-[-0.05em] text-amber-300">
              8
            </div>
            <div className="mt-1 text-sm font-medium text-amber-200">
              Require attention
            </div>
            <div className="mt-1 text-xs text-slate-400">
              5 execution gaps &middot; 3 peer outliers
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-amber-500/20 pt-3 text-xs font-semibold text-amber-700">
            <span>Inspect flagged CSEs</span>
            <span>&rarr;</span>
          </div>
        </Link>

        {/* Card 3: Review Samples Due (Blue Action) */}
        <Link
          href="/workbench/review-queue"
          className="workbench-metric workbench-metric--review group border border-blue-500/30 bg-[#0c172a] p-5 focus-visible:ring-2 focus-visible:ring-blue-500 sm:p-6"
        >
          <div className="flex items-center justify-between text-sm text-blue-300">
            <span className="font-semibold">Review samples due</span>
            <FileSearch className="size-4 text-blue-400" />
          </div>
          <div className="mt-2.5">
            <div className="text-4xl font-bold tracking-[-0.05em] text-blue-300">
              23
            </div>
            <div className="mt-1 text-sm font-medium text-blue-200">
              Review samples due
            </div>
            <div className="mt-1 text-xs text-slate-400">
              Ranked by priority reason & evidence count
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-blue-500/20 pt-3 text-xs font-semibold text-blue-700">
            <span>Open review queue</span>
            <span>&rarr;</span>
          </div>
        </Link>

        {/* Card 4: Data-Quality Gaps (Red Critical Issue) */}
        <Link
          href="/workbench/submissions"
          className="workbench-metric workbench-metric--data group border border-red-500/30 bg-[#191118] p-5 focus-visible:ring-2 focus-visible:ring-red-500 sm:p-6"
        >
          <div className="flex items-center justify-between text-sm text-red-300">
            <span className="font-semibold">Data-quality gaps</span>
            <ShieldAlert className="size-4 text-red-400" />
          </div>
          <div className="mt-2.5">
            <div className="text-4xl font-bold tracking-[-0.05em] text-red-300">
              3
            </div>
            <div className="mt-1 text-sm font-medium text-red-200">
              Data-quality gaps
            </div>
            <div className="mt-1 text-xs text-slate-400">
              1 quarantined file &middot; 2 stale inventories
            </div>
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-red-500/20 pt-3 text-xs font-semibold text-red-700">
            <span>Inspect submission gaps</span>
            <span>&rarr;</span>
          </div>
        </Link>
      </section>

      {/* 3. Entity Priority Ranking & Capability Overview */}
      <div className="workbench-overview__split grid grid-cols-1 items-start gap-6 xl:grid-cols-12">
        {/* Left: Entity Priority Ranking (Action List, 6 cols) */}
        <section className="workbench-panel space-y-5 rounded-[20px] border border-slate-800 bg-[#0c1424] p-6 sm:p-7 xl:col-span-7">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-[22px] font-semibold tracking-[-0.025em] text-white">
                Entity Priority Ranking
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Prioritized supervisory action list &middot; Cycle {selectedPeriod}
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
            {topPriorityRanking.map((entity, i) => {
              const rankStr = String(i + 1).padStart(2, "0");
              const signalCount = entity.findings || 4;
              const evidenceGaps = entity.topConcerns?.length ? 2 : 1;

              return (
                <div
                  key={entity.slug}
                  className="workbench-entity-row flex flex-col gap-4 rounded-xl px-3 py-5 transition-colors hover:bg-blue-50/70 sm:flex-row sm:items-center sm:justify-between"
                >
                  {/* Entity Metadata & Name */}
                  <div className="flex items-start gap-3 min-w-0">
                    <span className="grid size-8 shrink-0 place-items-center rounded-full bg-slate-100 font-mono text-xs font-bold text-slate-500">
                      {rankStr}
                    </span>
                    <div className="min-w-0 space-y-1">
                      <Link
                        href={`/workbench/entities/${entity.slug}`}
                        className="flex items-center gap-1.5 text-[17px] font-semibold tracking-[-0.015em] text-slate-100 transition-colors hover:text-blue-600"
                      >
                        <span className="truncate">{entity.name}</span>
                        <ArrowUpRight className="size-3 text-slate-500 shrink-0" />
                      </Link>

                      <div className="text-xs text-slate-500">
                        {entity.sector} &middot; <span className="text-slate-500">{entity.cohort}</span>
                      </div>

                      {/* Explicit Score Scale & Badge */}
                      <div className="flex flex-wrap items-center gap-2 pt-0.5">
                        <span className="font-mono text-xs font-semibold text-slate-200">
                          Risk score {entity.score.toFixed(1)} / 100
                        </span>
                        <StatusBadge
                          variant={entity.band === "high" ? "attention" : "neutral"}
                          label={entity.band.toUpperCase()}
                          size="sm"
                        />
                        {/* Why this score? affordance */}
                        <button
                          type="button"
                          onClick={() => setScoreModalEntity(entity)}
                          className="inline-flex items-center gap-1 rounded-md border border-blue-500/25 bg-blue-500/10 px-2 py-1 font-mono text-xs text-blue-300 transition-colors hover:bg-blue-500/20"
                          title="View multi-worker score decomposition"
                        >
                          <HelpCircle className="size-3" />
                          <span>Why this score?</span>
                        </button>
                      </div>

                      {/* Trend & Corroborated Evidence Counts */}
                      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                          {entity.trend === "deteriorating" && (
                            <>
                              <TrendingUp className="size-3 text-red-400" />
                              <span className="text-red-400">↑ {entity.trendDelta} pts vs previous cycle</span>
                            </>
                          )}
                          {entity.trend === "stable" && (
                            <>
                              <Minus className="size-3 text-slate-400" />
                              <span className="text-slate-400">Stable vs previous cycle</span>
                            </>
                          )}
                          {entity.trend === "improving" && (
                            <>
                              <TrendingDown className="size-3 text-emerald-400" />
                              <span className="text-emerald-400">↓ {entity.trendDelta} pts vs previous cycle</span>
                            </>
                          )}
                        </span>
                        <span>&middot;</span>
                        <span className="text-slate-300">
                          {signalCount} corroborated signals &middot; {evidenceGaps} evidence gaps
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Visible Drill-Down Button */}
                  <div className="self-end sm:self-center shrink-0">
                    <Link
                      href={`/workbench/entities/${entity.slug}`}
                      className="inline-flex min-h-10 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-sm transition-[border-color,background-color,color] hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
                    >
                      <span>Review entity</span>
                      <ArrowRight className="size-3" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Right: Capability Overview (Option B: Clean Ranked/Bar Summary) */}
        <section className="workbench-panel space-y-5 rounded-[20px] border border-slate-800 bg-[#0c1424] p-6 sm:p-7 xl:col-span-5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h2 className="text-[22px] font-semibold tracking-[-0.025em] text-white">
                Capability overview
              </h2>
              <p className="mt-1 text-xs text-slate-500">
                Cross-entity performance across 8 NCIIPC statutory dimensions
              </p>
            </div>
            <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
              Ranked Summary
            </span>
          </div>

          <HeatmapNCIIPC dimensions={avgDimensions} />
        </section>
      </div>

      {/* 4. WHY ATTENTION IS NEEDED (Evidence-Backed Supervisory Explanation) */}
      <section className="workbench-panel workbench-findings space-y-6 rounded-[20px] border border-amber-500/30 bg-[#0f1726] p-6 sm:p-7">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="size-4 text-amber-400" />
            <h2 className="text-[22px] font-semibold tracking-[-0.025em] text-white">
              Why attention is needed
            </h2>
          </div>
          <span className="text-xs font-semibold text-amber-700">
            Top corroborated supervisory signals
          </span>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          {/* Finding 1: Execution Gap */}
          <div className="workbench-finding workbench-finding--attention flex flex-col justify-between space-y-4 rounded-2xl border border-slate-800 bg-slate-900/90 p-5 sm:p-6">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <StatusBadge variant="attention" label="EXECUTION GAP" size="sm" />
                <span className="rounded-full bg-emerald-500/10 px-2 py-1 font-mono text-xs font-semibold text-emerald-300">HIGH CONFIDENCE</span>
              </div>
              <h3 className="font-sans text-lg font-semibold leading-snug text-slate-100">
                18 critical alerts closed without escalation
              </h3>

              {/* Observed Record Facts */}
              <div className="space-y-1 pt-1">
                <span className="block font-mono text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Evidence
                </span>
                <ul className="list-inside list-disc space-y-1 text-sm leading-6 text-slate-300">
                  <li>3 CSEs showed the same pattern</li>
                  <li>Average closure duration: under 4 minutes</li>
                  <li>Linked escalation records: 0</li>
                </ul>
              </div>

              {/* Supervisory Inference */}
              <div className="pt-1">
                <span className="block font-mono text-xs font-semibold uppercase tracking-wider text-amber-600">
                  Why it matters
                </span>
                <p className="mt-1 text-sm leading-6 text-slate-300">
                  Rapid closure without escalation may indicate insufficient escalation discipline or queue-clearing pressure.
                </p>
              </div>
            </div>

            {/* Action */}
            <div className="pt-3 border-t border-slate-800">
              <Link
                href="/workbench/findings/critical-alerts-closed-without-escalation"
                className="inline-flex items-center gap-1 font-mono text-xs text-blue-400 hover:text-blue-300 hover:underline"
              >
                <span>View supporting evidence</span>
                <ArrowRight className="size-3" />
              </Link>
            </div>
          </div>

          {/* Finding 2: Missing Evidence (formerly Negative Space) */}
          <div className="workbench-finding workbench-finding--critical flex flex-col justify-between space-y-4 rounded-2xl border border-slate-800 bg-slate-900/90 p-5 sm:p-6">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <StatusBadge variant="confirmed_concern" label="MISSING EVIDENCE" size="sm" />
                <span className="rounded-full bg-emerald-500/10 px-2 py-1 font-mono text-xs font-semibold text-emerald-300">HIGH CONFIDENCE</span>
              </div>
              <h3 className="font-sans text-lg font-semibold leading-snug text-slate-100">
                CSE-X has no telemetry for 7 critical assets
              </h3>

              {/* Observed Record Facts */}
              <div className="space-y-1 pt-1">
                <span className="block font-mono text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Evidence
                </span>
                <ul className="list-inside list-disc space-y-1 text-sm leading-6 text-slate-300">
                  <li>7 Tier-1 payment switchgear nodes registered</li>
                  <li>Active operational log records: 0 in 60-day cycle</li>
                  <li>Negative-space detector signal verified</li>
                </ul>
              </div>

              {/* Supervisory Inference */}
              <div className="pt-1">
                <span className="block font-mono text-xs font-semibold uppercase tracking-wider text-red-600">
                  Why it matters
                </span>
                <p className="mt-1 text-sm leading-6 text-slate-300">
                  Absence of telemetry from core payment switches creates an unmonitored blind spot in critical infrastructure.
                </p>
              </div>
            </div>

            {/* Action */}
            <div className="pt-3 border-t border-slate-800">
              <Link
                href="/workbench/findings/critical-asset-telemetry-absent"
                className="inline-flex items-center gap-1 font-mono text-xs text-blue-400 hover:text-blue-300 hover:underline"
              >
                <span>View supporting evidence</span>
                <ArrowRight className="size-3" />
              </Link>
            </div>
          </div>

          {/* Finding 3: Peer Deviation (Explained clearly) */}
          <div className="workbench-finding workbench-finding--peer flex flex-col justify-between space-y-4 rounded-2xl border border-slate-800 bg-slate-900/90 p-5 sm:p-6">
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <StatusBadge variant="attention" label="PEER DEVIATION" size="sm" />
                <span className="rounded-full bg-emerald-500/10 px-2 py-1 font-mono text-xs font-semibold text-emerald-300">HIGH CONFIDENCE</span>
              </div>
              <h3 className="font-sans text-lg font-semibold leading-snug text-slate-100">
                CSE-Y closure time is 4.8× faster than peer cohort
              </h3>

              {/* Observed Record Facts */}
              <div className="space-y-1 pt-1">
                <span className="block font-mono text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Evidence
                </span>
                <ul className="list-inside list-disc space-y-1 text-sm leading-6 text-slate-300">
                  <li>Entity median closure: 4.8 min vs Cohort median: 24.0 min</li>
                  <li>98.4% of investigation notes contain &lt;15 characters</li>
                  <li>Statistically significant outlier (z = 3.82, p &lt; 0.001)</li>
                </ul>
              </div>

              {/* Supervisory Inference */}
              <div className="pt-1">
                <span className="block font-mono text-xs font-semibold uppercase tracking-wider text-amber-600">
                  Why it matters
                </span>
                <p className="mt-1 text-sm leading-6 text-slate-300">
                  Ultra-fast closure paired with sparse documentation indicates metric gaming or superficial triage rather than operational efficiency.
                </p>
              </div>
            </div>

            {/* Action */}
            <div className="pt-3 border-t border-slate-800">
              <Link
                href="/workbench/findings/closure-time-faster-than-cohort"
                className="inline-flex items-center gap-1 font-mono text-xs text-blue-400 hover:text-blue-300 hover:underline"
              >
                <span>View supporting evidence</span>
                <ArrowRight className="size-3" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 5. DATA AND EVIDENCE HEALTH (Dedicated Trust & Provenance Section) */}
      <section className="workbench-panel workbench-evidence space-y-6 rounded-[20px] border border-slate-800 bg-[#0c1424] p-6 sm:p-7">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <Database className="size-4 text-blue-400" />
              <h2 className="text-[22px] font-semibold tracking-[-0.025em] text-white">
                Data & evidence health
              </h2>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Evidence pipeline integrity &middot; Air-gapped ingestion gate
            </p>
          </div>
          <span className="rounded bg-amber-500/15 border border-amber-500/30 px-2.5 py-1 font-mono text-xs text-amber-300 font-semibold self-start sm:self-center">
            Pipeline: Attention required
          </span>
        </div>

        {/* Health Metrics Strip */}
        <div className="workbench-health-grid grid grid-cols-1 gap-px overflow-hidden rounded-2xl sm:grid-cols-2 lg:grid-cols-4">
          <div className="workbench-health-card bg-slate-900/50 p-5">
            <span className="block text-xs font-semibold text-slate-500">
              Unlinked Feeds
            </span>
            <div className="mt-2 font-mono text-3xl font-bold tracking-tight text-amber-600">
              14
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Target hosts unmapped to known IP subnets
            </p>
          </div>

          <div className="workbench-health-card bg-slate-900/50 p-5">
            <span className="block text-xs font-semibold text-slate-500">
              Quarantined Files
            </span>
            <div className="mt-2 font-mono text-3xl font-bold tracking-tight text-red-600">
              1
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              CSE-NEG syslog truncated at day 12
            </p>
          </div>

          <div className="workbench-health-card bg-slate-900/50 p-5">
            <span className="block text-xs font-semibold text-slate-500">
              Stale Inventories
            </span>
            <div className="mt-2 font-mono text-3xl font-bold tracking-tight text-amber-600">
              2
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              CSE-NEG (&gt;114d), CSE-018 (&gt;96d)
            </p>
          </div>

          <div className="workbench-health-card bg-slate-900/50 p-5">
            <span className="block text-xs font-semibold text-slate-500">
              Verified Submissions
            </span>
            <div className="mt-2 flex items-center gap-1.5 font-mono text-3xl font-bold tracking-tight text-emerald-600">
              <CheckCircle2 className="size-4" />
              <span>41 / 42</span>
            </div>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              1 submission requires signature verification
            </p>
          </div>
        </div>

        {/* Cryptographic Trust & Provenance Context Box */}
        <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/20 p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-start gap-3">
            <ShieldCheck className="size-5 text-emerald-400 mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-emerald-300 font-mono">
                Evidence authenticity: 41 of 42 submissions verified
              </div>
              <p className="text-xs text-slate-300">
                ML-DSA-65 (NIST FIPS 204) post-quantum signatures &middot; SHA3-256 evidence binding &middot; Zero network verification calls
              </p>
            </div>
          </div>
          <Link
            href="/workbench/governance"
            className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 font-mono text-xs text-emerald-300 hover:bg-emerald-500/20 transition-colors self-start sm:self-center shrink-0"
          >
            <span>Verify cryptographic trust</span>
            <ArrowRight className="size-3" />
          </Link>
        </div>
      </section>

      {/* 6. Score Decomposition Modal ("Why this score?") */}
      {scoreModalEntity && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
        >
          <div className="relative w-full max-w-lg rounded-lg border border-slate-700 bg-[#0c1628] p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between border-b border-slate-800 pb-3">
              <div>
                <span className="font-mono text-xs uppercase tracking-wider text-blue-500">
                  Transparent Risk Composition
                </span>
                <h3 className="text-base font-bold text-white">
                  Why Risk Score {scoreModalEntity.score.toFixed(1)} / 100?
                </h3>
                <p className="text-xs font-mono text-slate-400">
                  {scoreModalEntity.name} ({scoreModalEntity.slug})
                </p>
              </div>
              <button
                type="button"
                onClick={() => setScoreModalEntity(null)}
                className="p-1 text-slate-400 hover:text-white"
                aria-label="Close modal"
              >
                <X className="size-5" />
              </button>
            </div>

            <div className="space-y-3 font-mono text-xs">
              <p className="text-slate-300 font-sans">
                SAT-SA risk scores are computed through transparent multi-worker statistical corroboration, not opaque black-box AI:
              </p>

              <div className="rounded border border-slate-800 bg-slate-900/80 p-3 space-y-2">
                <div className="flex justify-between items-center text-slate-200 font-semibold">
                  <span>1. Signal Corroboration Worker</span>
                  <span className="text-amber-400">38.0 / 40 pts</span>
                </div>
                <p className="font-sans text-xs text-slate-500">
                  4 corroborating signals detected across log ingestion, triage records, and asset lists.
                </p>
              </div>

              <div className="rounded border border-slate-800 bg-slate-900/80 p-3 space-y-2">
                <div className="flex justify-between items-center text-slate-200 font-semibold">
                  <span>2. Execution Gap Analysis</span>
                  <span className="text-amber-400">24.4 / 30 pts</span>
                </div>
                <p className="font-sans text-xs text-slate-500">
                  18 critical alerts closed under 4 minutes with zero escalation records attached.
                </p>
              </div>

              <div className="rounded border border-slate-800 bg-slate-900/80 p-3 space-y-2">
                <div className="flex justify-between items-center text-slate-200 font-semibold">
                  <span>3. Peer Outlier Deviation</span>
                  <span className="text-amber-400">16.0 / 30 pts</span>
                </div>
                <p className="font-sans text-xs text-slate-500">
                  Closure velocity 4.8× faster than peer cohort median (z = 3.82).
                </p>
              </div>

              <div className="flex justify-between items-center pt-2 border-t border-slate-800 text-sm font-bold text-white">
                <span>Total Fused Risk Score</span>
                <span className="text-amber-300">{scoreModalEntity.score.toFixed(1)} / 100 ({scoreModalEntity.band.toUpperCase()})</span>
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Link
                href={`/workbench/entities/${scoreModalEntity.slug}`}
                onClick={() => setScoreModalEntity(null)}
                className="rounded bg-blue-600 px-4 py-2 font-mono text-xs font-semibold text-white hover:bg-blue-500"
              >
                Review Full Entity Profile &rarr;
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
