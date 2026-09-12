"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  CheckCircle2,
  Lock,
  Download,
  FileSpreadsheet,
  Layers,
  RotateCcw,
  Clock,
  KeyRound,
  FileCode2,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { governanceConfig } from "@/components/sites/sat-sa-with-pqc/workbench/data/governance";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";

export default function GovernancePage() {
  const { auditEntries, selectedPeriod, resetToBaseline, undoLastAction } = useWorkbench();
  const [downloadSuccess, setDownloadSuccess] = useState(false);

  const handleExportAuditBundle = () => {
    const bundle = {
      auditBundleMetadata: {
        assessmentCycle: selectedPeriod,
        exportedAt: new Date().toISOString(),
        auditorStation: "EXAM-DEL-04",
        statutoryRetentionStandard: governanceConfig.statutoryRetentionPolicy,
        cryptographicProof: {
          algorithm: governanceConfig.cryptographicStandard,
          totalChainBlocks: auditEntries.length + 100,
          ledgerStatus: governanceConfig.ledgerIntegrityStatus,
          tamperCount: governanceConfig.tamperCount,
        },
      },
      engineLineage: {
        engineVersion: governanceConfig.engineVersion,
        rulesetVersion: governanceConfig.rulesetVersion,
        thresholdCalibration: governanceConfig.thresholdCalibrationVersion,
      },
      ledgerBlocks: auditEntries,
    };

    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `NCIIPC-AUDIT-BUNDLE-${selectedPeriod.replace(/[^a-zA-Z0-9]/g, "_")}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setDownloadSuccess(true);
    setTimeout(() => setDownloadSuccess(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Governance, Audit & Cryptographic Verification
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Defending supervisory conclusions with NIST FIPS 204 post-quantum evidence ledgers
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleExportAuditBundle}
            className="inline-flex items-center gap-1.5 rounded bg-blue-600 px-3 py-1.5 font-mono text-xs font-semibold text-white shadow hover:bg-blue-500 transition-colors"
          >
            <Download className="size-3.5" />
            <span>{downloadSuccess ? "Bundle Exported!" : "Export Cryptographic Audit Bundle"}</span>
          </button>
        </div>
      </div>

      {/* Trust & Lineage Top Metric Panel */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 font-mono text-xs">
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-4 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase block">Engine & Ruleset</span>
          <div className="text-sm font-bold text-white">v{governanceConfig.engineVersion}</div>
          <p className="text-slate-400 text-[11px]">Rules: {governanceConfig.rulesetVersion}</p>
        </div>

        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-4 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase block">PQC Cryptographic Posture</span>
          <div className="text-sm font-bold text-emerald-400 flex items-center gap-1.5">
            <ShieldCheck className="size-4" />
            <span>ML-DSA-65 Valid</span>
          </div>
          <p className="text-slate-400 text-[11px]">NIST FIPS 204 + SHA3-256</p>
        </div>

        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-4 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase block">Evidence Ledger Status</span>
          <div className="text-sm font-bold text-slate-200">
            {auditEntries.length + 100} Hash-Chained Blocks
          </div>
          <p className="text-emerald-400 text-[11px] font-semibold">0 Tamper Events Detected</p>
        </div>

        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-4 space-y-1">
          <span className="text-slate-500 text-[10px] uppercase block">Statutory Audit Retention</span>
          <div className="text-sm font-bold text-slate-200">7-Year Compliance</div>
          <p className="text-slate-400 text-[11px]">Air-Gapped Local Storage</p>
        </div>
      </div>

      {/* Visual Data Lineage Graph */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3 font-mono text-xs">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Layers className="size-4 text-blue-400" />
            <h2 className="text-sm font-bold uppercase text-white">
              Data Lineage & Verification Architecture
            </h2>
          </div>
          <span className="text-[11px] text-slate-400">
            Periodic CSE Submission &rarr; Examiner Recorded Disposition
          </span>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-5 text-center pt-2">
          <div className="rounded border border-slate-800 bg-slate-900/80 p-3">
            <span className="text-blue-400 font-bold block text-[11px]">1. Submission</span>
            <span className="text-slate-300 text-xs mt-1 block">Raw Logs & Telemetry</span>
            <span className="text-slate-500 text-[10px] mt-1 block">Hashed via SHA3-256</span>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/80 p-3">
            <span className="text-blue-400 font-bold block text-[11px]">2. Normalization</span>
            <span className="text-slate-300 text-xs mt-1 block">Canonical Entities</span>
            <span className="text-slate-500 text-[10px] mt-1 block">Alerts, Cases, Assets</span>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/80 p-3">
            <span className="text-blue-400 font-bold block text-[11px]">3. Analytics</span>
            <span className="text-slate-300 text-xs mt-1 block">16 Workers Fusion</span>
            <span className="text-slate-500 text-[10px] mt-1 block">Negative Space & Gaps</span>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/80 p-3">
            <span className="text-amber-400 font-bold block text-[11px]">4. Human Review</span>
            <span className="text-slate-300 text-xs mt-1 block">Examiner Decision</span>
            <span className="text-slate-500 text-[10px] mt-1 block">Structured Rationale</span>
          </div>

          <div className="rounded border border-emerald-500/30 bg-emerald-950/20 p-3">
            <span className="text-emerald-400 font-bold block text-[11px]">5. TRUST-SAT</span>
            <span className="text-slate-200 text-xs mt-1 block">Immutable Chain</span>
            <span className="text-emerald-400 text-[10px] mt-1 block">Signed with ML-DSA-65</span>
          </div>
        </div>
      </div>

      {/* Review-Decision Audit Ledger Table */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1424] overflow-hidden space-y-3 p-5 font-mono text-xs">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-sm font-bold uppercase text-white">
              Supervisory Review-Decision Ledger ({auditEntries.length} entries)
            </h2>
            <p className="text-[11px] text-slate-400 mt-0.5">
              Append-only audit trail · Correction handled via explicit subsequent reversal records
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={undoLastAction}
              className="inline-flex items-center gap-1.5 rounded border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-amber-300 hover:bg-amber-500/20 transition-colors"
            >
              <RotateCcw className="size-3" />
              <span>Undo Last Action</span>
            </button>
            <button
              type="button"
              onClick={resetToBaseline}
              className="rounded border border-slate-700 bg-slate-800 px-2.5 py-1 text-slate-400 hover:text-white"
            >
              Reset Baseline
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/80 text-[10px] uppercase text-slate-400">
                <th className="py-2.5 px-3">Block #</th>
                <th className="py-2.5 px-3">Timestamp (UTC)</th>
                <th className="py-2.5 px-3">Principal & Role</th>
                <th className="py-2.5 px-3">Action Recorded</th>
                <th className="py-2.5 px-3">Subject Identifier</th>
                <th className="py-2.5 px-3">Ledger Digest</th>
                <th className="py-2.5 px-3">Notes & Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {auditEntries.map((entry) => (
                <tr key={entry.id} className="hover:bg-slate-800/40">
                  <td className="py-2.5 px-3 font-bold text-blue-400">
                    #{entry.blockHeight}
                  </td>
                  <td className="py-2.5 px-3 text-slate-400">
                    {entry.occurredAt.replace("T", " ").replace("Z", "")}
                  </td>
                  <td className="py-2.5 px-3">
                    <span className="font-semibold text-slate-200">{entry.principalIdentity}</span>
                    <span className="text-[10px] text-slate-500 block">{entry.role}</span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`inline-block rounded px-2 py-0.5 text-[10px] uppercase font-bold ${
                        entry.action === "DISPOSITION_RECORD"
                          ? "bg-blue-500/15 text-blue-300 border border-blue-500/30"
                          : entry.action === "DISPOSITION_REVERSAL"
                          ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                          : "bg-slate-800 text-slate-400"
                      }`}
                    >
                      {entry.action.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-sans text-[11px] text-slate-200">
                    {entry.subjectIdentifier}
                  </td>
                  <td className="py-2.5 px-3 font-mono text-[10px] text-slate-400">
                    <code>{entry.currentBlockDigestSha3.slice(0, 12)}...</code>
                  </td>
                  <td className="py-2.5 px-3 font-sans text-[11px] text-slate-300 max-w-xs truncate">
                    {entry.notes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
