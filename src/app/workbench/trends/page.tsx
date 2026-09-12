"use client";

import React, { useState } from "react";
import { Building2 } from "lucide-react";
import {
  cohorts,
  closureTimeTrend,
  escalationRateTrend,
  telemetryCompletenessByAssetClass,
  riskDecompositionTrend,
} from "@/components/sites/sat-sa-with-pqc/workbench/data/trends";
import {
  OfflineLineChart,
  OfflineBarChart,
} from "@/components/sites/sat-sa-with-pqc/workbench/ui/OfflineChart";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";

export default function TrendsPage() {
  const [selectedCohortId, setSelectedCohortId] = useState<string>("cohort-fin-large");
  const currentCohort =
    cohorts.find((c) => c.cohortId === selectedCohortId) || cohorts[0];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Trends & Cohort Benchmarks
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Statistical multi-cycle comparisons · Explaining comparability to prevent misleading league tables
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-slate-400">Cohort:</span>
          <select
            aria-label="Select Cohort"
            value={selectedCohortId}
            onChange={(e) => setSelectedCohortId(e.target.value)}
            className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 font-mono text-xs text-white focus:outline-none"
          >
            {cohorts.map((c) => (
              <option key={c.cohortId} value={c.cohortId}>
                {c.name} ({c.memberCount} CSEs)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Cohort Membership & Comparability Context Box (Crucial for preventing misleading league tables!) */}
      <div className="rounded-lg border border-blue-500/30 bg-[#0c1628] p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Building2 className="size-4 text-blue-400" />
            <h2 className="text-sm font-bold uppercase font-mono text-white">
              Why Entities in &ldquo;{currentCohort.name}&rdquo; Are Comparable
            </h2>
          </div>
          <span className="rounded bg-blue-500/15 border border-blue-500/30 px-2 py-0.5 font-mono text-[10px] text-blue-300 uppercase">
            {currentCohort.memberCount} Standard Peers
          </span>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5 text-xs font-mono pt-1">
          <div className="rounded border border-slate-800 bg-slate-900/60 p-2.5">
            <span className="text-slate-500 text-[10px] uppercase block">Sector Scope</span>
            <span className="text-slate-200 mt-0.5 block font-sans">{currentCohort.comparabilityCriteria.sectorScope}</span>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/60 p-2.5">
            <span className="text-slate-500 text-[10px] uppercase block">Asset Scale</span>
            <span className="text-slate-200 mt-0.5 block font-sans">{currentCohort.comparabilityCriteria.assetScale}</span>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/60 p-2.5">
            <span className="text-slate-500 text-[10px] uppercase block">Criticality Mix</span>
            <span className="text-slate-200 mt-0.5 block font-sans">{currentCohort.comparabilityCriteria.criticalityMix}</span>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/60 p-2.5">
            <span className="text-slate-500 text-[10px] uppercase block">Architecture Type</span>
            <span className="text-slate-200 mt-0.5 block font-sans">{currentCohort.comparabilityCriteria.architectureType}</span>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/60 p-2.5">
            <span className="text-slate-500 text-[10px] uppercase block">Reporting Period</span>
            <span className="text-slate-200 mt-0.5 block font-sans">{currentCohort.comparabilityCriteria.reportingPeriod}</span>
          </div>
        </div>
      </div>

      {/* Two-Column Time-Series Charts */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Chart 1: Closure-Time Distribution over Time */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div>
              <h3 className="text-sm font-bold uppercase font-mono text-white">
                Alert Closure-Time Velocity (Mar – Sep 2026)
              </h3>
              <p className="text-[11px] font-mono text-slate-400">
                CSE-X & CSE-Y velocity divergence from 24m cohort median
              </p>
            </div>
            <StatusBadge variant="attention" label="VELOCITY ANOMALY" size="sm" />
          </div>

          <OfflineLineChart
            data={closureTimeTrend}
            metricKey1="csexValue"
            metricLabel1="CSE-X Velocity (5.0m)"
            metricColor1="#f59e0b"
            metricKey2="cohortMedian"
            metricLabel2="Cohort Median (24.0m)"
            metricColor2="#3b82f6"
            baselineKey="sectorBaseline"
            baselineLabel="Sector Baseline (25m)"
            yUnit="m"
            height={220}
          />
        </div>

        {/* Chart 2: Critical-Alert Escalation Rate */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div>
              <h3 className="text-sm font-bold uppercase font-mono text-white">
                Critical-Alert Escalation Compliance
              </h3>
              <p className="text-[11px] font-mono text-slate-400">
                CSE-X dropping to 68.8% vs statutory cohort standard of 98.0%
              </p>
            </div>
            <StatusBadge variant="confirmed_concern" label="EXECUTION GAP" size="sm" />
          </div>

          <OfflineLineChart
            data={escalationRateTrend}
            metricKey1="csexValue"
            metricLabel1="CSE-X Escalation %"
            metricColor1="#ef4444"
            metricKey2="cohortMedian"
            metricLabel2="Cohort Median (98%)"
            metricColor2="#3b82f6"
            baselineKey="sectorBaseline"
            baselineLabel="Statutory Min (95%)"
            yUnit="%"
            height={220}
          />
        </div>
      </div>

      {/* Row 2: Telemetry Completeness by Critical Asset Class & Risk Decomposition */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Telemetry Completeness */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div>
              <h3 className="text-sm font-bold uppercase font-mono text-white">
                Telemetry Coverage Completeness by Asset Class
              </h3>
              <p className="text-[11px] font-mono text-slate-400">
                Identifies negative-space voids where expected audit records are absent
              </p>
            </div>
            <StatusBadge variant="attention" label="TELEMETRY VOID" size="sm" />
          </div>

          <OfflineBarChart
            data={telemetryCompletenessByAssetClass.map((c) => ({
              label: c.assetClass,
              value: c.csexPct,
              benchmark: c.cohortPct,
              status: c.status,
            }))}
            yUnit="%"
          />
        </div>

        {/* Risk Score Decomposition Trend */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div>
              <h3 className="text-sm font-bold uppercase text-white">
                Supervisory Risk Dimension Evolution (CSE-X)
              </h3>
              <p className="text-[11px] text-slate-400">
                Decomposition of monthly increases across 4 detector families
              </p>
            </div>
            <span className="text-amber-400 font-bold text-sm">
              Current: 78.4 / 100
            </span>
          </div>

          <div className="space-y-2">
            {riskDecompositionTrend.slice(-4).map((row, i) => (
              <div key={i} className="rounded border border-slate-800 bg-slate-900/60 p-3 space-y-1.5">
                <div className="flex items-center justify-between font-bold text-slate-200">
                  <span>{row.period} Cycle Assessment</span>
                  <span className="text-amber-300">Total Score: {row.total}</span>
                </div>
                <div className="grid grid-cols-4 gap-2 text-[11px] text-slate-400 pt-1">
                  <div>
                    <span className="text-slate-500 block text-[9px] uppercase">Execution Gap</span>
                    <strong className="text-slate-300">+{row.executionGap}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[9px] uppercase">Negative Space</span>
                    <strong className="text-red-400">+{row.negativeSpace}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[9px] uppercase">Peer Deviation</span>
                    <strong className="text-blue-300">+{row.peerDeviation}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[9px] uppercase">Anomaly</span>
                    <strong className="text-slate-300">+{row.anomaly}</strong>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
