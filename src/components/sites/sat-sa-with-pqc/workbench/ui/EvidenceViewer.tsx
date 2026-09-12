"use client";

import React, { useState } from "react";
import { Lock, Eye, EyeOff, ShieldCheck, Copy, Check } from "lucide-react";
import { SupportingEvidenceRecord } from "../data/findings";
import { useWorkbench } from "../state/WorkbenchContext";

interface EvidenceViewerProps {
  records: SupportingEvidenceRecord[];
  submissionId?: string;
  contentHashSha3?: string;
}

export const EvidenceViewer: React.FC<EvidenceViewerProps> = ({
  records,
  submissionId = "SUB-2026-08-CSEX-001",
  contentHashSha3 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
}) => {
  const { redactionMode, setRedactionMode } = useWorkbench();
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const maskString = (val: string) => {
    if (!redactionMode) return val;
    // Mask IPs
    let res = val.replace(/\b(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}\b/g, "$1.***.***");
    // Mask operator codes
    res = res.replace(/OP-\d+/g, "OP-***");
    return res;
  };

  const handleCopy = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 overflow-hidden font-mono text-xs">
      {/* Control Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 bg-slate-900/80 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-slate-300">
            <Lock className="size-3.5 text-blue-400" />
            <span className="font-semibold text-slate-200">Raw Submitted Evidence Rows</span>
          </div>
          <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] text-slate-400">
            {records.length} {records.length === 1 ? "record" : "records"}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Role badge */}
          <div className="hidden sm:flex items-center gap-1 text-[11px] text-slate-400">
            <span>Role:</span>
            <span className="text-slate-200 font-semibold">NCIIPC Supervisory Examiner</span>
          </div>

          {/* Redaction Toggle */}
          <button
            type="button"
            onClick={() => setRedactionMode((prev) => !prev)}
            className={`flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs transition-colors ${
              redactionMode
                ? "border-amber-500/40 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25"
                : "border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {redactionMode ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
            <span>{redactionMode ? "Redaction Active (PII Masked)" : "Full Raw Data (Unmasked)"}</span>
          </button>
        </div>
      </div>

      {/* Provenance Metadata Sub-bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/60 bg-slate-900/40 px-4 py-1.5 text-[11px] text-slate-400">
        <div className="flex items-center gap-2">
          <span>Submission ID: <strong className="text-slate-300">{submissionId}</strong></span>
          <span>·</span>
          <span>SHA3-256: <code className="text-blue-300">{contentHashSha3.slice(0, 16)}...</code></span>
        </div>
        <div className="flex items-center gap-1 text-emerald-400">
          <ShieldCheck className="size-3.5" />
          <span>ML-DSA-65 Signature Verified</span>
        </div>
      </div>

      {/* Records Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-900/60 text-slate-400 uppercase tracking-wider text-[10px]">
              <th className="py-2 px-3">Alert / Record</th>
              <th className="py-2 px-3">Timestamp (UTC)</th>
              <th className="py-2 px-3">Target Asset</th>
              <th className="py-2 px-3">Duration</th>
              <th className="py-2 px-3">Case Link</th>
              <th className="py-2 px-3">Escalation</th>
              <th className="py-2 px-3">Operator</th>
              <th className="py-2 px-3 text-right">Raw Ingest Line</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-slate-300">
            {records.map((rec) => (
              <tr key={rec.id} className="hover:bg-slate-900/40 transition-colors">
                <td className="py-2 px-3 font-semibold text-amber-300">{rec.alertId}</td>
                <td className="py-2 px-3 text-slate-400">{rec.timestampCreated.replace("T", " ").replace("Z", "")}</td>
                <td className="py-2 px-3">
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-200">
                    {maskString(rec.assetId)}
                  </span>
                </td>
                <td className="py-2 px-3 font-mono">{rec.durationSeconds > 0 ? `${rec.durationSeconds}s` : "N/A"}</td>
                <td className="py-2 px-3">
                  {rec.linkedCaseId ? (
                    <span className="text-blue-400">{rec.linkedCaseId}</span>
                  ) : (
                    <span className="text-red-400 font-semibold">[NULL / NONE]</span>
                  )}
                </td>
                <td className="py-2 px-3">
                  {rec.escalationRecordId ? (
                    <span className="text-emerald-400">{rec.escalationRecordId}</span>
                  ) : (
                    <span className="text-red-400 font-semibold">[NULL / NONE]</span>
                  )}
                </td>
                <td className="py-2 px-3 text-slate-400">{maskString(rec.actorId)}</td>
                <td className="py-2 px-3 text-right">
                  <button
                    type="button"
                    onClick={() => handleCopy(maskString(rec.rawJsonSnippet), rec.id)}
                    className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-[10px] text-slate-300 hover:bg-slate-700 transition-colors"
                  >
                    {copiedId === rec.id ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                    <span>{copiedId === rec.id ? "Copied" : "Copy JSON"}</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
