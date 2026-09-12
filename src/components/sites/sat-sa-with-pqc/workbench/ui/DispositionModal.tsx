"use client";

import React, { useState } from "react";
import {
  X,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  FileText,
  RotateCcw,
  CheckCircle2,
  Send,
} from "lucide-react";
import { QueueItem, DispositionType } from "../data/reviewQueue";
import { useWorkbench } from "../state/WorkbenchContext";
import { StatusBadge } from "./StatusBadge";

interface DispositionModalProps {
  item: QueueItem | null;
  onClose: () => void;
  onViewEvidence?: (item: QueueItem) => void;
}

export const DispositionModal: React.FC<DispositionModalProps> = ({
  item,
  onClose,
  onViewEvidence,
}) => {
  const { recordDisposition, revertDisposition } = useWorkbench();
  const [selectedDisposition, setSelectedDisposition] = useState<DispositionType>(
    item?.currentDisposition && item.currentDisposition !== "open"
      ? item.currentDisposition
      : "confirmed_concern"
  );
  const [rationale, setRationale] = useState<string>(item?.dispositionRationale || "");
  const [reversalMode, setReversalMode] = useState<boolean>(false);
  const [reversalReason, setReversalReason] = useState<string>("");

  if (!item) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (reversalMode) {
      if (!reversalReason.trim()) {
        alert("Please provide an audited reason for reversing this disposition.");
        return;
      }
      revertDisposition(item.id, reversalReason);
      onClose();
      return;
    }

    if (!rationale.trim()) {
      alert("A structured examiner rationale is required for every supervisory disposition.");
      return;
    }

    recordDisposition(item.id, selectedDisposition, rationale);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl overflow-hidden rounded-lg border border-slate-700 bg-slate-900 shadow-2xl">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            <span className="font-mono text-xs text-amber-400 font-bold">#{item.rank}</span>
            <h3 className="font-sans text-sm font-semibold text-white">
              Supervisory Disposition Record
            </h3>
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-400 uppercase">
              Immutable Ledger
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Item Context */}
        <div className="border-b border-slate-800 bg-slate-900/60 p-4 font-mono text-xs">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 text-slate-300">
            <div>
              <span className="text-slate-500 block text-[10px] uppercase">Entity</span>
              <strong className="text-slate-200">{item.entityName}</strong>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase">Asset</span>
              <strong className="text-slate-200">{item.assetId}</strong>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase">Alert / Case ID</span>
              <strong className="text-amber-400">{item.alertOrCaseId}</strong>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase">Current State</span>
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
          </div>
          <div className="mt-2 text-slate-400 text-[11px] bg-slate-950/40 p-2 rounded border border-slate-800/80">
            <span className="text-amber-400 font-semibold">Priority Reason: </span>
            {item.priorityReason}
          </div>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {!reversalMode ? (
            <>
              {/* Disposition Selector */}
              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-slate-400 mb-2">
                  Select Supervisory Conclusion
                </label>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <button
                    type="button"
                    onClick={() => setSelectedDisposition("confirmed_concern")}
                    className={`flex flex-col items-center justify-center p-3 rounded border text-center transition-all ${
                      selectedDisposition === "confirmed_concern"
                        ? "border-red-500 bg-red-500/20 text-red-200 shadow"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <ShieldAlert className="size-5 mb-1 text-red-400" />
                    <span className="text-xs font-bold font-mono uppercase">Confirmed Concern</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Serious anomaly verified</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedDisposition("not_substantiated")}
                    className={`flex flex-col items-center justify-center p-3 rounded border text-center transition-all ${
                      selectedDisposition === "not_substantiated"
                        ? "border-slate-400 bg-slate-800 text-slate-200 shadow"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <ShieldCheck className="size-5 mb-1 text-slate-400" />
                    <span className="text-xs font-bold font-mono uppercase">Not Substantiated</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Satisfactorily explained</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedDisposition("needs_more_info")}
                    className={`flex flex-col items-center justify-center p-3 rounded border text-center transition-all ${
                      selectedDisposition === "needs_more_info"
                        ? "border-amber-500 bg-amber-500/20 text-amber-200 shadow"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <AlertTriangle className="size-5 mb-1 text-amber-400" />
                    <span className="text-xs font-bold font-mono uppercase">Needs More Info</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Request periodic data</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setSelectedDisposition("escalated")}
                    className={`flex flex-col items-center justify-center p-3 rounded border text-center transition-all ${
                      selectedDisposition === "escalated"
                        ? "border-blue-500 bg-blue-500/20 text-blue-200 shadow"
                        : "border-slate-800 bg-slate-950 text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <Send className="size-5 mb-1 text-blue-400" />
                    <span className="text-xs font-bold font-mono uppercase">Escalate to Case</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Formal inquiry case</span>
                  </button>
                </div>
              </div>

              {/* Rationale Textarea */}
              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-slate-400 mb-1.5">
                  Examiner Structured Rationale (Immutable Audit Note)
                </label>
                <textarea
                  rows={3}
                  value={rationale}
                  onChange={(e) => setRationale(e.target.value)}
                  placeholder="Record verifiable justification (e.g. 'Shift handover log confirms absence of ticket creation for alert A-1001. Cross-referenced with operator OP-881 desk roster...')"
                  className="w-full rounded border border-slate-700 bg-slate-950 p-2.5 font-mono text-xs text-slate-200 placeholder:text-slate-600 focus:border-blue-500 focus:outline-none"
                  required
                />
                <p className="mt-1 text-[11px] text-slate-500 font-mono">
                  Every disposition record is digitally signed with ML-DSA-65 and hashed into the supervisory ledger.
                </p>
              </div>
            </>
          ) : (
            /* Reversal Mode */
            <div className="rounded border border-amber-500/40 bg-amber-500/10 p-4 space-y-3">
              <div className="flex items-center gap-2 text-amber-300 font-mono text-xs font-semibold">
                <RotateCcw className="size-4" />
                <span>Auditable Reversal Protocol</span>
              </div>
              <p className="text-xs text-slate-300">
                In compliance with supervisory integrity principles, disposition corrections are handled through an explicit subsequent reversal record rather than silent overwrite.
              </p>
              <div>
                <label className="block text-xs font-mono uppercase text-slate-400 mb-1">
                  Reason for Reversal / Correction
                </label>
                <textarea
                  rows={2}
                  value={reversalReason}
                  onChange={(e) => setReversalReason(e.target.value)}
                  placeholder="State why previous disposition is being revoked or modified..."
                  className="w-full rounded border border-amber-500/40 bg-slate-950 p-2 font-mono text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none"
                  required
                />
              </div>
            </div>
          )}

          {/* Audit History Snapshot */}
          {item.dispositionHistory.length > 0 && (
            <div className="border-t border-slate-800 pt-3">
              <span className="text-[11px] font-mono text-slate-500 uppercase block mb-1.5">
                Prior Review Ledger ({item.dispositionHistory.length} recorded events)
              </span>
              <div className="max-h-24 overflow-y-auto space-y-1 text-[11px] font-mono">
                {item.dispositionHistory.map((hist) => (
                  <div key={hist.id} className="flex items-center justify-between text-slate-400 bg-slate-950/60 px-2 py-1 rounded">
                    <span>
                      <strong className="text-slate-300 uppercase">{hist.disposition}</strong> by {hist.examiner}
                    </span>
                    <span className="text-slate-500">{hist.timestamp.split("T")[0]}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-4">
            <div className="flex items-center gap-2">
              {item.dispositionHistory.length > 0 && (
                <button
                  type="button"
                  onClick={() => setReversalMode((prev) => !prev)}
                  className="inline-flex items-center gap-1.5 rounded border border-amber-500/30 px-3 py-1.5 font-mono text-xs text-amber-300 hover:bg-amber-500/10"
                >
                  <RotateCcw className="size-3.5" />
                  <span>{reversalMode ? "Cancel Reversal" : "Revert Previous Record"}</span>
                </button>
              )}
              {onViewEvidence && (
                <button
                  type="button"
                  onClick={() => onViewEvidence(item)}
                  className="inline-flex items-center gap-1.5 rounded border border-slate-700 px-3 py-1.5 font-mono text-xs text-slate-300 hover:bg-slate-800"
                >
                  <FileText className="size-3.5 text-blue-400" />
                  <span>Inspect Raw Evidence</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded border border-slate-700 px-3 py-1.5 font-mono text-xs text-slate-400 hover:bg-slate-800 hover:text-white"
              >
                Cancel
              </button>
              <button
                type="submit"
                className={`inline-flex items-center gap-1.5 rounded px-4 py-1.5 font-mono text-xs font-semibold text-white shadow ${
                  reversalMode
                    ? "bg-amber-600 hover:bg-amber-500"
                    : "bg-blue-600 hover:bg-blue-500"
                }`}
              >
                <CheckCircle2 className="size-4" />
                <span>{reversalMode ? "Record Audited Reversal" : "Commit Disposition"}</span>
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};
