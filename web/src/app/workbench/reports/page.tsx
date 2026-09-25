"use client";

import React, { useState } from "react";
import {
  FileSpreadsheet,
  Download,
  CheckCircle2,
  Printer,
  ShieldCheck,
  Calendar,
  Building2,
  FileText,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { governanceConfig } from "@/components/sites/sat-sa-with-pqc/workbench/data/governance";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";

export default function ReportsPage() {
  const { selectedPeriod, queueItems, entitiesList } = useWorkbench();
  const [downloading, setDownloading] = useState<string | null>(null);

  const handleDownload = (reportType: string) => {
    setDownloading(reportType);
    setTimeout(() => {
      const sampleReport = {
        title: `NCIIPC Supervisory Assessment Report - ${reportType}`,
        period: selectedPeriod,
        generatedAt: new Date().toISOString(),
        assessedEntitiesCount: entitiesList.length,
        attentionEntitiesCount: entitiesList.filter((e) => e.band === "high").length,
        reviewedSamplesCount: queueItems.filter((q) => q.currentDisposition !== "open").length,
        cryptographicProof: "ML-DSA-65 (NIST FIPS 204) Verified Ledger",
      };
      const blob = new Blob([JSON.stringify(sampleReport, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `NCIIPC-SUPERVISORY-${reportType.toUpperCase()}-${selectedPeriod.replace(/[^a-zA-Z0-9]/g, "_")}.json`;
      a.click();
      URL.revokeObjectURL(url);
      setDownloading(null);
    }, 500);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Reports
          </h1>
          <p className="mt-0.5 text-sm text-slate-400">
            Supervisory packets and assessment summaries
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {/* Report 1 */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <StatusBadge variant="verified" label="OFFICIAL" size="sm" />
              <span className="font-mono text-xs text-slate-400">{selectedPeriod}</span>
            </div>
            <h3 className="font-sans text-base font-bold text-white">
              Cycle Supervisory Executive Summary
            </h3>
            <p className="text-xs text-slate-300 font-sans">
              Comprehensive overview of 42 CSE assessments, 8 attention entities, capability heatmaps, and top corroborated execution gaps.
            </p>
          </div>

          <button
            type="button"
            onClick={() => handleDownload("Executive-Summary")}
            className="w-full flex items-center justify-center gap-2 rounded bg-violet-600 py-2 font-mono text-xs font-semibold text-white hover:bg-violet-500 transition-colors shadow"
          >
            <Download className="size-3.5" />
            <span>{downloading === "Executive-Summary" ? "Generating..." : "Download Executive Summary"}</span>
          </button>
        </div>

        {/* Report 2 */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <StatusBadge variant="attention" label="CONFIDENTIAL" size="sm" />
              <span className="font-mono text-xs text-slate-400">P1 Samples</span>
            </div>
            <h3 className="font-sans text-base font-bold text-white">
              Review Queue Disposition Packet
            </h3>
            <p className="text-xs text-slate-300 font-sans">
              Complete dossier of examined samples, examiner structured rationales, and recorded dispositions with PQC signature attestations.
            </p>
          </div>

          <button
            type="button"
            onClick={() => handleDownload("Disposition-Packet")}
            className="w-full flex items-center justify-center gap-2 rounded border border-slate-700 bg-slate-800 py-2 font-mono text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-colors shadow"
          >
            <Download className="size-3.5 text-violet-400" />
            <span>{downloading === "Disposition-Packet" ? "Generating..." : "Download Disposition Dossier"}</span>
          </button>
        </div>

        {/* Report 3 */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-3 flex flex-col justify-between">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-slate-400">7-Year Retention</span>
            </div>
            <h3 className="font-sans text-base font-bold text-white">
              Statutory Defense & Provenance Bundle
            </h3>
            <p className="text-xs text-slate-300 font-sans">
              Cryptographically bound evidence bundle containing raw submissions hashes, detector calibration weights, and {governanceConfig.hashChainedBlocksTotal} hash-chained ledger blocks.
            </p>
          </div>

          <button
            type="button"
            onClick={() => handleDownload("Statutory-Bundle")}
            className="w-full flex items-center justify-center gap-2 rounded border border-slate-700 bg-slate-800 py-2 font-mono text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-colors shadow"
          >
            <Download className="size-3.5 text-violet-400" />
            <span>{downloading === "Statutory-Bundle" ? "Generating..." : "Download Statutory Bundle"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
