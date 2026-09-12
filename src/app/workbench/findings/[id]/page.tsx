"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  FileCheck2,
  Clock,
  Layers,
  Scale,
  Hash,
  GitCommit,
  CheckCircle2,
  HelpCircle,
  Download,
  FileText,
} from "lucide-react";
import { findings } from "@/components/sites/sat-sa-with-pqc/workbench/data/findings";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";
import { EvidenceViewer } from "@/components/sites/sat-sa-with-pqc/workbench/ui/EvidenceViewer";

export default function FindingDetailPage() {
  const params = useParams();
  const slug = (params.id as string)?.toLowerCase();

  const finding =
    findings.find((f) => f.findingSlug === slug || f.id === slug) || findings[0];

  const [showEvidenceTable, setShowEvidenceTable] = useState(true);

  return (
    <div className="space-y-6">
      {/* Back Link */}
      <div className="flex items-center justify-between">
        <Link
          href="/workbench/findings"
          className="inline-flex items-center gap-1.5 font-mono text-xs text-blue-400 hover:underline"
        >
          <ArrowLeft className="size-3.5" />
          <span>Back to Findings Repository</span>
        </Link>
        <span className="font-mono text-xs text-slate-400">
          Finding ID: <code>{finding.id}</code>
        </span>
      </div>

      {/* Main Evidence Narrative Header Card */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between border-b border-slate-800 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <StatusBadge
                variant={finding.severity === "critical" ? "confirmed_concern" : "attention"}
                label={finding.findingFamilyLabel.toUpperCase()}
                size="md"
              />
              <h1 className="text-xl font-bold tracking-tight text-white">
                {finding.title}
              </h1>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3 font-mono text-xs text-slate-300">
              <span>Entity: <strong className="text-white">{finding.entityName}</strong></span>
              <span>·</span>
              <span>Period: <strong className="text-slate-200">{finding.period}</strong></span>
              <span>·</span>
              <span>Confidence: <strong className="text-emerald-400 uppercase">{finding.confidence}</strong></span>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start font-mono text-xs text-emerald-400 border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 rounded">
            <ShieldCheck className="size-3.5" />
            <span>ML-DSA-65 Verified</span>
          </div>
        </div>

        {/* Narrative Section 1: Observed Pattern & Why This Matters */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 text-xs">
          <div className="rounded border border-slate-800 bg-slate-900/60 p-4 space-y-1.5">
            <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-amber-400 block">
              Observed Pattern
            </span>
            <p className="text-slate-200 leading-relaxed font-sans">
              {finding.observedPattern}
            </p>
          </div>

          <div className="rounded border border-slate-800 bg-slate-900/60 p-4 space-y-1.5">
            <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-blue-400 block">
              Why This Matters (Statutory Baseline)
            </span>
            <p className="text-slate-200 leading-relaxed font-sans">
              {finding.whyThisMatters}
            </p>
          </div>
        </div>

        {/* Narrative Section 2: Statistical Peer Context & System Limitation */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 text-xs">
          {/* Peer Context Box */}
          <div className="rounded border border-blue-500/30 bg-blue-950/20 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-blue-300">
                Peer Context ({finding.peerContext.cohortName})
              </span>
              <span className="font-mono text-amber-300 font-bold">
                {finding.peerContext.varianceRatio}× Cohort Median
              </span>
            </div>
            <div className="flex items-center gap-6 font-mono text-xs">
              <div>
                <span className="text-slate-400 block text-[10px]">Cohort Median</span>
                <span className="text-slate-200 font-bold text-sm">
                  {finding.peerContext.cohortMedianPct}%
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[10px]">Observed Entity Rate</span>
                <span className="text-amber-300 font-bold text-sm">
                  {finding.peerContext.entityObservedPct}%
                </span>
              </div>
            </div>
            <p className="text-slate-300 text-[11px] font-sans">
              {finding.peerContext.description}
            </p>
          </div>

          {/* System Limitation Boundary Box */}
          <div className="rounded border border-slate-700 bg-slate-900/80 p-4 space-y-2">
            <div className="flex items-center gap-1.5 text-amber-400 font-mono text-[11px] font-bold uppercase">
              <AlertTriangle className="size-3.5" />
              <span>System Analytical Limitation</span>
            </div>
            <p className="text-slate-300 text-xs font-sans leading-relaxed">
              {finding.systemLimitation}
            </p>
            <span className="text-[10px] font-mono text-slate-500 block">
              Bound by air-gapped periodic submission verification protocol.
            </span>
          </div>
        </div>

        {/* Narrative Section 3: Reconstructed Workflow Timeline */}
        <div className="rounded border border-slate-800 bg-slate-900/50 p-4 space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <div className="flex items-center gap-2">
              <Clock className="size-4 text-blue-400" />
              <span className="font-bold uppercase text-white">
                Reconstructed Operational Timeline
              </span>
            </div>
            <span className="text-[11px] text-slate-500">
              Reconstructed from forensic SIEM & ingestion timestamps
            </span>
          </div>

          <div className="relative pl-6 space-y-3 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-800">
            {finding.reconstructedTimeline.map((step, idx) => (
              <div key={idx} className="relative">
                <span className="absolute -left-6 top-1 size-2.5 rounded-full bg-blue-500 ring-4 ring-slate-900" />
                <div className="flex flex-col sm:flex-row sm:items-baseline sm:justify-between gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-200">{step.step}</span>
                    <span className="text-[11px] text-slate-500">({step.actorOrSystem})</span>
                  </div>
                  <span className="text-[11px] text-slate-400">{step.timestamp}</span>
                </div>
                <p className="text-[11px] text-slate-300 font-sans mt-0.5">{step.detail}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Narrative Section 4: Clear Distinction (Facts vs Inferences vs Examiner Actions) */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3 text-xs">
          {/* Column A: Observed Facts */}
          <div className="rounded border border-slate-800 bg-slate-900/70 p-3.5 space-y-2">
            <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-emerald-400 block border-b border-slate-800 pb-1.5">
              1. Observed Facts (Verifiable)
            </span>
            <ul className="space-y-1.5 text-[11px] text-slate-300 font-sans list-disc pl-4">
              {finding.observedFacts.map((fact, i) => (
                <li key={i}>{fact}</li>
              ))}
            </ul>
          </div>

          {/* Column B: System Inferences */}
          <div className="rounded border border-slate-800 bg-slate-900/70 p-3.5 space-y-2">
            <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-amber-400 block border-b border-slate-800 pb-1.5">
              2. Analytical Inferences
            </span>
            <ul className="space-y-1.5 text-[11px] text-slate-300 font-sans list-disc pl-4">
              {finding.systemInferences.map((inf, i) => (
                <li key={i}>{inf}</li>
              ))}
            </ul>
          </div>

          {/* Column C: Recommended Action */}
          <div className="rounded border border-blue-500/30 bg-blue-950/20 p-3.5 space-y-2">
            <span className="font-mono text-[11px] font-bold uppercase tracking-wider text-blue-300 block border-b border-slate-800 pb-1.5">
              3. Recommended Examiner Action
            </span>
            <p className="text-[11px] text-slate-200 font-sans leading-relaxed">
              {finding.recommendedAction}
            </p>
            <div className="pt-2">
              <Link
                href={`/workbench/review-queue`}
                className="inline-block rounded bg-blue-600 px-3 py-1.5 font-mono text-[11px] font-semibold text-white hover:bg-blue-500 transition-colors"
              >
                Record Supervisory Decision &rarr;
              </Link>
            </div>
          </div>
        </div>

        {/* Technical & Calibration Metadata Footer */}
        <div className="rounded border border-slate-800/80 bg-slate-950/70 p-3 font-mono text-[11px] text-slate-400 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <div>
            <span className="text-slate-500 block uppercase text-[10px]">Submission ID</span>
            <span className="text-slate-300">{finding.submissionId}</span>
          </div>
          <div>
            <span className="text-slate-500 block uppercase text-[10px]">Detector Worker</span>
            <span className="text-slate-300">{finding.detectorVersion}</span>
          </div>
          <div>
            <span className="text-slate-500 block uppercase text-[10px]">Calibration Ruleset</span>
            <span className="text-slate-300">{finding.calibrationVersion}</span>
          </div>
          <div>
            <span className="text-slate-500 block uppercase text-[10px]">SHA3-256 Digest</span>
            <code className="text-blue-300">{finding.contentHashSha3.slice(0, 16)}...</code>
          </div>
        </div>
      </div>

      {/* Raw Supporting Evidence Rows (Table with Redaction Controls) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase font-mono text-white">
            Supporting Raw Evidence ({finding.evidenceRecords.length} records)
          </h2>
          <button
            type="button"
            onClick={() => setShowEvidenceTable((prev) => !prev)}
            className="font-mono text-xs text-blue-400 hover:underline"
          >
            {showEvidenceTable ? "Collapse Table" : "Expand Table"}
          </button>
        </div>

        {showEvidenceTable && (
          <EvidenceViewer
            records={finding.evidenceRecords}
            submissionId={finding.submissionId}
            contentHashSha3={finding.contentHashSha3}
          />
        )}
      </div>
    </div>
  );
}
