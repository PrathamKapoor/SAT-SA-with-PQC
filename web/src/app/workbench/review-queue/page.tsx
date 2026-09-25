"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  ListOrdered,
  FileCheck,
  AlertTriangle,
  ShieldAlert,
  ShieldCheck,
  Send,
  Download,
  Eye,
  Filter,
  CheckCircle2,
  Calendar,
  UserCheck,
  RotateCcw,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";
import { DispositionModal } from "@/components/sites/sat-sa-with-pqc/workbench/ui/DispositionModal";
import { EvidenceViewer } from "@/components/sites/sat-sa-with-pqc/workbench/ui/EvidenceViewer";
import { QueueItem } from "@/components/sites/sat-sa-with-pqc/workbench/data/reviewQueue";
import { findings } from "@/components/sites/sat-sa-with-pqc/workbench/data/findings";

export default function ReviewQueuePage() {
  const { queueItems, selectedCohort, exportReviewPacket, undoLastAction } = useWorkbench();
  const [priorityFilter, setPriorityFilter] = useState<string>("All");
  const [dispositionFilter, setDispositionFilter] = useState<string>("All");
  const [selectedItemForDisposition, setSelectedItemForDisposition] = useState<QueueItem | null>(null);
  const [selectedItemForEvidence, setSelectedItemForEvidence] = useState<QueueItem | null>(null);
  const [selectedCheckboxIds, setSelectedCheckboxIds] = useState<string[]>([]);

  // Filter items
  const filteredItems = queueItems.filter((item) => {
    if (priorityFilter !== "All" && item.priority !== priorityFilter.toLowerCase()) return false;
    if (dispositionFilter !== "All" && item.currentDisposition !== dispositionFilter.toLowerCase()) return false;
    return true;
  });

  const toggleSelectAll = () => {
    if (selectedCheckboxIds.length === filteredItems.length) {
      setSelectedCheckboxIds([]);
    } else {
      setSelectedCheckboxIds(filteredItems.map((i) => i.id));
    }
  };

  const toggleSelectOne = (id: string) => {
    if (selectedCheckboxIds.includes(id)) {
      setSelectedCheckboxIds(selectedCheckboxIds.filter((x) => x !== id));
    } else {
      setSelectedCheckboxIds([...selectedCheckboxIds, id]);
    }
  };

  // Find evidence records for selected item
  const activeEvidenceFinding = selectedItemForEvidence
    ? findings.find((f) => f.id === selectedItemForEvidence.findingId) || findings[0]
    : null;

  return (
    <div className="space-y-5">
      {/* Screen Header */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white">
            Review Queue
          </h1>
          <p className="mt-0.5 text-sm text-slate-400">
            Ranked samples awaiting a human decision
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => exportReviewPacket(selectedCheckboxIds)}
            className="inline-flex items-center gap-1.5 rounded border border-slate-700 bg-slate-800 px-3 py-1.5 font-mono text-xs text-slate-200 hover:bg-slate-700 transition-colors shadow"
          >
            <Download className="size-3.5 text-violet-400" />
            <span>
              Export Review Packet {selectedCheckboxIds.length > 0 ? `(${selectedCheckboxIds.length})` : "(All)"}
            </span>
          </button>
        </div>
      </div>

      {/* Filter and Control Sub-bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-800 bg-[#0c1424] p-3 text-xs font-mono">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 uppercase text-xs">Priority:</span>
            <select
              aria-label="Filter by Priority"
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200 focus:outline-none"
            >
              <option value="All">All Priorities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-400 uppercase text-xs">Disposition:</span>
            <select
              aria-label="Filter by Disposition"
              value={dispositionFilter}
              onChange={(e) => setDispositionFilter(e.target.value)}
              className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200 focus:outline-none"
            >
              <option value="All">All States</option>
              <option value="open">Open (Unreviewed)</option>
              <option value="confirmed_concern">Confirmed Concern</option>
              <option value="not_substantiated">Not Substantiated</option>
              <option value="needs_more_info">Needs More Info</option>
              <option value="escalated">Escalated</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2 text-slate-400 text-xs">
          <span>Queue Total: <strong className="text-white">{filteredItems.length} items</strong></span>
          <span>·</span>
          <span className="text-amber-300">
            {filteredItems.filter((i) => i.currentDisposition === "open").length} open
          </span>
        </div>
      </div>

      {/* Queue Items List / Table */}
      <div className="space-y-3">
        {filteredItems.map((item) => {
          const isSelected = selectedCheckboxIds.includes(item.id);

          return (
            <div
              key={item.id}
              className={`rounded-lg border transition-all p-4 space-y-3 ${
                item.priority === "critical"
                  ? "border-amber-500/40 bg-[#121624] hover:border-amber-500/70"
                  : "border-slate-800 bg-[#0c1424] hover:border-slate-700"
              }`}
            >
              {/* Card Top Line */}
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800/80 pb-3">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleSelectOne(item.id)}
                    aria-label={`Select sample ${item.alertOrCaseId}`}
                    className="size-4 rounded border-slate-700 bg-slate-950 text-violet-600 focus:ring-0 cursor-pointer"
                  />
                  <span className="font-mono text-xs font-bold text-amber-400">
                    Rank #{item.rank}
                  </span>
                  <StatusBadge
                    variant={
                      item.priority === "critical"
                        ? "confirmed_concern"
                        : item.priority === "high"
                        ? "attention"
                        : "navigational"
                    }
                    label={`${item.priority.toUpperCase()} PRIORITY`}
                    size="sm"
                  />
                  <span className="rounded bg-slate-800/90 border border-slate-700/60 px-2 py-0.5 font-mono text-xs uppercase text-slate-300">
                    {item.findingFamilyLabel}
                  </span>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center font-mono text-xs">
                  <span className="text-slate-400 text-xs">Assigned: {item.assignedExaminer.split(" ")[0]}</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-slate-400 text-xs">Due: {item.reviewDueDate}</span>
                </div>
              </div>

              {/* Priority Reason & Target Context */}
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
                <div className="lg:col-span-8 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-white">
                      {item.alertOrCaseId}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">
                      on <strong className="text-slate-200">{item.assetName}</strong> ({item.assetId})
                    </span>
                    <span className="text-slate-600">·</span>
                    <Link
                      href={`/workbench/entities/${item.entitySlug}`}
                      className="text-xs font-semibold text-violet-400 hover:underline"
                    >
                      {item.entityName}
                    </Link>
                  </div>

                  {/* Explicit Priority Reason */}
                  <div className="rounded border border-amber-500/20 bg-amber-500/5 p-2.5 text-xs text-slate-200 font-sans">
                    <span className="font-mono font-bold text-amber-400 uppercase text-xs block mb-0.5">
                      Reason for Priority:
                    </span>
                    {item.priorityReason}
                  </div>

                  {/* Corroborating Signals Callout */}
                  <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                    <span className="text-violet-300 font-semibold">{item.corroboratingSignalsCount} corroborating signals</span>
                    <span>·</span>
                    <span>Confidence: <strong className="text-white uppercase">{item.confidence}</strong></span>
                    <span>·</span>
                    <span>Evidence Count: {item.evidenceCount} records</span>
                  </div>
                </div>

                {/* Examiner Action & Disposition Panel */}
                <div className="lg:col-span-4 flex flex-col justify-between border-t border-slate-800/80 pt-3 lg:border-t-0 lg:border-l lg:pl-4 space-y-2">
                  <div>
                    <span className="font-mono text-xs uppercase text-slate-500 block">
                      Recommended Action:
                    </span>
                    <span className="font-mono text-xs font-semibold text-violet-300 block">
                      {item.recommendedActionLabel}
                    </span>
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between font-mono text-xs">
                      <span className="text-slate-400 text-xs uppercase">Disposition:</span>
                      <StatusBadge
                        variant={
                          item.currentDisposition === "confirmed_concern"
                            ? "confirmed_concern"
                            : item.currentDisposition === "open"
                            ? "attention"
                            : "navigational"
                        }
                        label={item.currentDisposition.replace(/_/g, " ")}
                        size="sm"
                      />
                    </div>

                    <div className="flex items-center gap-2 pt-1">
                      <button
                        type="button"
                        onClick={() => setSelectedItemForEvidence(item)}
                        className="flex-1 rounded border border-slate-700 bg-slate-800/80 py-1.5 text-center font-mono text-xs text-slate-300 hover:bg-slate-700 transition-colors"
                      >
                        Evidence ({item.evidenceCount})
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelectedItemForDisposition(item)}
                        className="flex-1 rounded bg-violet-600 py-1.5 text-center font-mono text-xs font-semibold text-white hover:bg-violet-500 transition-colors shadow"
                      >
                        Record Disposition
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Examiner Disposition Recording Modal */}
      {selectedItemForDisposition && (
        <DispositionModal
          item={selectedItemForDisposition}
          onClose={() => setSelectedItemForDisposition(null)}
          onViewEvidence={(it) => {
            setSelectedItemForDisposition(null);
            setSelectedItemForEvidence(it);
          }}
        />
      )}

      {/* Raw Evidence Inspection Drawer / Modal */}
      {selectedItemForEvidence && activeEvidenceFinding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm">
          <div className="w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-2xl p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">
                  Evidence Records for {selectedItemForEvidence.alertOrCaseId}
                </h3>
                <p className="font-mono text-xs text-slate-400 mt-0.5">
                  Entity: {selectedItemForEvidence.entityName} · Finding: {activeEvidenceFinding.title}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedItemForEvidence(null)}
                className="rounded border border-slate-700 bg-slate-800 px-3 py-1 font-mono text-xs text-slate-300 hover:bg-slate-700"
              >
                Close
              </button>
            </div>

            <EvidenceViewer
              records={activeEvidenceFinding.evidenceRecords}
              submissionId={activeEvidenceFinding.submissionId}
              contentHashSha3={activeEvidenceFinding.contentHashSha3}
            />

            <div className="flex items-center justify-between border-t border-slate-800 pt-3">
              <Link
                href={`/workbench/findings/${activeEvidenceFinding.findingSlug}`}
                className="font-mono text-xs text-violet-400 hover:underline"
              >
                View Complete Finding Evidence Narrative <ArrowRight className="inline size-3.5 shrink-0" aria-hidden="true" />
              </Link>
              <button
                type="button"
                onClick={() => {
                  const it = selectedItemForEvidence;
                  setSelectedItemForEvidence(null);
                  setSelectedItemForDisposition(it);
                }}
                className="rounded bg-violet-600 px-3 py-1.5 font-mono text-xs font-semibold text-white hover:bg-violet-500"
              >
                Proceed to Disposition
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
