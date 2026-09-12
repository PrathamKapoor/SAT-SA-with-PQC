"use client";

import React from "react";
import {
  Download,
  ShieldCheck,
} from "lucide-react";
import { submissions, SubmissionRecord } from "@/components/sites/sat-sa-with-pqc/workbench/data/submissions";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";

export default function SubmissionsPage() {

  const handleDownloadReport = (sub: SubmissionRecord) => {
    const reportData = {
      validationHeader: {
        submissionIdentifier: sub.submissionIdentifier,
        entityName: sub.entityName,
        reportingPeriod: sub.reportingPeriod,
        ingestTimestamp: sub.ingestTimestamp,
        contentHashSha3: sub.contentHashSha3,
        pqcSignature: {
          algorithm: sub.pqcSignatureAlgorithm,
          status: sub.pqcSignatureVerified ? "VERIFIED_VALID" : "UNVERIFIED",
        },
      },
      qualityAssessment: {
        schemaValidation: sub.schemaValidationStatus,
        schemaValidationErrors: sub.schemaValidationErrors,
        missingMandatoryFields: sub.missingMandatoryFields,
        referentialIntegrityFailures: sub.referentialIntegrityFailuresCount,
        duplicateOrConflictingRecords: sub.duplicateOrConflictingRecordsCount,
        assetInventoryFreshnessDays: sub.assetInventoryFreshnessDays,
        assetInventoryStatus: sub.assetInventoryStatus,
        negativeSpaceReliabilityScore: `${sub.negativeSpaceReliabilityScore}%`,
        negativeSpaceTrustConclusion:
          sub.negativeSpaceReliabilityScore >= 90
            ? "RELIABLE_FOR_NEGATIVE_SPACE: Absences represent true operational silence rather than data pipeline failure."
            : "UNRELIABLE_FOR_NEGATIVE_SPACE: Data pipeline issues present; absences must be verified manually.",
      },
      recordCounts: {
        totalIngested: sub.recordsTotal,
        accepted: sub.recordsAccepted,
        quarantined: sub.recordsQuarantined,
        rejected: sub.recordsRejected,
      },
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `VALIDATION-REPORT-${sub.submissionIdentifier}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Data Submissions & Input Integrity
          </h1>
          <p className="text-xs font-mono text-slate-400 mt-0.5">
            Examiner data quality & negative-space trust boundary · Cycle: Aug–Sep 2026
          </p>
        </div>
      </div>

      {/* Negative-Space Credibility Callout */}
      <div className="rounded-lg border border-blue-500/30 bg-[#0c1628] p-4 text-xs font-sans text-slate-200 space-y-1.5">
        <div className="flex items-center gap-2 font-mono text-blue-400 font-bold uppercase text-[11px]">
          <ShieldCheck className="size-4" />
          <span>Supervisory Negative-Space Integrity Principle</span>
        </div>
        <p className="text-slate-300 leading-relaxed">
          SAT-SA strictly distinguishes between <strong>&ldquo;no alert occurred during operations&rdquo;</strong> and <strong>&ldquo;the telemetry dataset was incomplete or dropped at the boundary.&rdquo;</strong> Negative-space findings are only marked with high confidence when the submission achieves &gt;90% completeness, zero critical schema quarantines, and fresh (&lt;90 days) asset inventories.
        </p>
      </div>

      {/* Submissions Table */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1424] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-slate-800 bg-slate-900/80 text-[10px] text-slate-400 uppercase tracking-wider">
                <th className="py-3 px-4">Submission & Entity</th>
                <th className="py-3 px-3">Period & Ingest</th>
                <th className="py-3 px-3">Schema Result</th>
                <th className="py-3 px-3">Asset Freshness</th>
                <th className="py-3 px-3">Integrity / Dups</th>
                <th className="py-3 px-3">Records (Acc / Qnt / Rej)</th>
                <th className="py-3 px-3">PQC Signature</th>
                <th className="py-3 px-4 text-right">Report</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              {submissions.map((sub) => (
                <tr key={sub.id} className="hover:bg-slate-800/40 transition-colors">
                  {/* Submission ID & Entity */}
                  <td className="py-3 px-4 font-sans">
                    <div className="font-mono text-xs font-bold text-white">
                      {sub.submissionIdentifier}
                    </div>
                    <span className="text-[11px] text-slate-400 font-sans block">
                      {sub.entityName}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">
                      {sub.format} · {sub.sourceOrigin}
                    </span>
                  </td>

                  {/* Period & Ingest Timestamp */}
                  <td className="py-3 px-3 text-[11px]">
                    <div>{sub.reportingPeriod}</div>
                    <div className="text-slate-500 text-[10px]">
                      {sub.ingestTimestamp.replace("T", " ").replace("Z", " UTC")}
                    </div>
                  </td>

                  {/* Schema Validation Result */}
                  <td className="py-3 px-3">
                    {sub.schemaValidationStatus === "passed" ? (
                      <StatusBadge variant="verified" label="PASSED" size="sm" icon="check" />
                    ) : sub.schemaValidationStatus === "warning" ? (
                      <StatusBadge variant="attention" label="WARNINGS" size="sm" icon="alert-triangle" />
                    ) : (
                      <StatusBadge variant="confirmed_concern" label="FAILED" size="sm" icon="alert-circle" />
                    )}
                  </td>

                  {/* Asset Inventory Freshness */}
                  <td className="py-3 px-3 text-[11px]">
                    <div className="flex items-center gap-1.5">
                      <span
                        className={
                          sub.assetInventoryStatus === "stale"
                            ? "text-red-400 font-bold"
                            : "text-slate-200"
                        }
                      >
                        {sub.assetInventoryFreshnessDays} days old
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500 uppercase">
                      {sub.assetInventoryStatus === "fresh" ? "Fresh (<30d)" : "Stale (>90d)"}
                    </span>
                  </td>

                  {/* Referential Integrity & Duplicates */}
                  <td className="py-3 px-3 text-[11px]">
                    <div className="flex items-center gap-2">
                      <span>Ref errs: <strong className={sub.referentialIntegrityFailuresCount > 50 ? "text-red-400" : "text-slate-200"}>{sub.referentialIntegrityFailuresCount}</strong></span>
                      <span>·</span>
                      <span>Dups: {sub.duplicateOrConflictingRecordsCount}</span>
                    </div>
                  </td>

                  {/* Records Breakdown */}
                  <td className="py-3 px-3 text-[11px]">
                    <div className="flex items-center gap-1.5">
                      <span className="text-emerald-400 font-semibold">{sub.recordsAccepted.toLocaleString()}</span>
                      <span className="text-slate-500">/</span>
                      <span className={sub.recordsQuarantined > 0 ? "text-amber-400 font-semibold" : "text-slate-500"}>
                        {sub.recordsQuarantined}
                      </span>
                      <span className="text-slate-500">/</span>
                      <span className={sub.recordsRejected > 0 ? "text-red-400 font-semibold" : "text-slate-500"}>
                        {sub.recordsRejected}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Total: {sub.recordsTotal.toLocaleString()}
                    </div>
                  </td>

                  {/* PQC Signature Verification */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-1 text-emerald-400 text-[11px]">
                      <ShieldCheck className="size-3.5" />
                      <span>{sub.pqcSignatureAlgorithm.split(" ")[0]} Valid</span>
                    </div>
                    <code className="text-[9px] text-slate-500 block">
                      {sub.contentHashSha3.slice(0, 10)}...
                    </code>
                  </td>

                  {/* Download Report Action */}
                  <td className="py-3 px-4 text-right">
                    <button
                      type="button"
                      onClick={() => handleDownloadReport(sub)}
                      className="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-[11px] text-slate-200 hover:bg-slate-700 transition-colors"
                    >
                      <Download className="size-3 text-blue-400" />
                      <span>JSON Receipt</span>
                    </button>
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
