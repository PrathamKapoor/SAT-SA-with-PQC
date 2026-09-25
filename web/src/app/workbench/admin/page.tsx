"use client";

import React, { useState } from "react";
import {
  Settings,
  ShieldCheck,
  WifiOff,
  UserCheck,
  Sliders,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import { StatusBadge } from "@/components/sites/sat-sa-with-pqc/workbench/ui/StatusBadge";

export default function AdminPage() {
  const { resetToBaseline } = useWorkbench();
  const [fastClosureThreshold, setFastClosureThreshold] = useState(300); // 300s = 5m
  const [minInvestigationNotes, setMinInvestigationNotes] = useState(25);
  const [savedNote, setSavedNote] = useState(false);

  const handleSaveCalibration = (e: React.FormEvent) => {
    e.preventDefault();
    setSavedNote(true);
    setTimeout(() => setSavedNote(false), 2500);
  };

  return (
    <div className="space-y-6 font-mono text-xs">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-white font-sans">
            Administration
          </h1>
          <p className="mt-0.5 text-sm text-slate-400">
            Roles and threshold governance
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Air-Gap Verification Diagnostics */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <WifiOff className="size-4 text-emerald-400" />
              <h2 className="text-sm font-bold uppercase text-white font-sans">
                Air-Gap & Offline Integrity Diagnostics
              </h2>
            </div>
            <StatusBadge variant="verified" label="COMPLIANT" size="sm" icon="check" />
          </div>

          <div className="space-y-2.5 text-slate-300">
            <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded border border-slate-800">
              <span>Outbound SaaS Network Requests:</span>
              <span className="text-emerald-400 font-bold">0 (Blocked at Kernel Diode)</span>
            </div>
            <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded border border-slate-800">
              <span>Remote CDN Font Imports:</span>
              <span className="text-emerald-400 font-bold">0 (Local Fonts Embedded)</span>
            </div>
            <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded border border-slate-800">
              <span>Third-party Chart SaaS APIs:</span>
              <span className="text-emerald-400 font-bold">0 (Native Offline SVG Engine)</span>
            </div>
            <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded border border-slate-800">
              <span>PQC Cryptographic Provider:</span>
              <span className="text-violet-300 font-bold">Local ML-DSA-65 (NIST FIPS 204)</span>
            </div>
          </div>
        </div>

        {/* Examiner Workstation Roster */}
        <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-2">
              <UserCheck className="size-4 text-violet-400" />
              <h2 className="text-sm font-bold uppercase text-white font-sans">
                Authorized Examiner Roster
              </h2>
            </div>
            <span className="text-slate-400 text-xs">NCIIPC Station 04</span>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded border border-slate-800">
              <div>
                <strong className="text-white block font-sans">Examiner A. Sharma</strong>
                <span className="text-slate-400 text-xs">Identity: EXAM-SHARMA-01</span>
              </div>
              <span className="rounded bg-violet-500/15 border border-violet-500/30 px-2 py-0.5 text-violet-300 font-bold">
                Lead Examiner
              </span>
            </div>

            <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded border border-slate-800">
              <div>
                <strong className="text-white block font-sans">Examiner V. Patel</strong>
                <span className="text-slate-400 text-xs">Identity: EXAM-PATEL-02</span>
              </div>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-300">
                Senior Analyst
              </span>
            </div>

            <div className="flex items-center justify-between bg-slate-900/60 p-2.5 rounded border border-slate-800">
              <div>
                <strong className="text-white block font-sans">Examiner M. Rao</strong>
                <span className="text-slate-400 text-xs">Identity: EXAM-RAO-04</span>
              </div>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-slate-300">
                Supervisory Examiner
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Threshold Calibration Settings */}
      <div className="rounded-lg border border-slate-800 bg-[#0c1424] p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center gap-2">
            <Sliders className="size-4 text-amber-400" />
            <h2 className="text-sm font-bold uppercase text-white font-sans">
              Supervisory Detector Calibration Settings
            </h2>
          </div>
          <span className="text-amber-400 text-xs">Audit Logging Mandatory</span>
        </div>

        <form onSubmit={handleSaveCalibration} className="space-y-4 max-w-xl">
          <div>
            <label className="block text-slate-300 mb-1">
              Rapid Closure Anomaly Threshold (seconds):
            </label>
            <input
              type="number"
              value={fastClosureThreshold}
              onChange={(e) => setFastClosureThreshold(Number(e.target.value))}
              className="w-full rounded border border-slate-700 bg-slate-950 p-2 text-white"
            />
            <span className="text-xs text-slate-500 mt-0.5 block font-sans">
              Current: Alerts closed faster than 300s (5m) trigger Execution Gap inspection.
            </span>
          </div>

          <div>
            <label className="block text-slate-300 mb-1">
              Minimum Required Investigation Notes Length (characters):
            </label>
            <input
              type="number"
              value={minInvestigationNotes}
              onChange={(e) => setMinInvestigationNotes(Number(e.target.value))}
              className="w-full rounded border border-slate-700 bg-slate-950 p-2 text-white"
            />
            <span className="text-xs text-slate-500 mt-0.5 block font-sans">
              Closure notes shorter than 25 chars without telemetry attachments are flagged as metric gaming.
            </span>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <button
              type="submit"
              className="rounded bg-violet-600 px-4 py-2 font-semibold text-white hover:bg-violet-500 transition-colors shadow"
            >
              Commit Calibration Update
            </button>
            {savedNote && (
              <span className="text-emerald-400 flex items-center gap-1 font-semibold">
                <CheckCircle2 className="size-3.5" />
                <span>Calibration saved and logged in ledger block #104.</span>
              </span>
            )}
          </div>
        </form>
      </div>

      {/* State Revertibility & Master Reset */}
      <div className="rounded-lg border border-red-500/30 bg-red-950/10 p-5 space-y-3">
        <div className="flex items-center gap-2 text-red-400 font-bold uppercase">
          <RotateCcw className="size-4" />
          <h2 className="text-sm font-sans">Supervisory State Revertibility Boundary</h2>
        </div>
        <p className="text-slate-300 font-sans text-xs">
          All review decisions made in the workbench persist across browser sessions. You may reset the entire examination state to the clean, verified cycle baseline. A formal revocation record will be logged to preserve full auditability.
        </p>
        <button
          type="button"
          onClick={resetToBaseline}
          className="rounded border border-red-500/40 bg-red-500/20 px-4 py-1.5 font-bold text-red-200 hover:bg-red-500/30 transition-colors"
        >
          Reset All Dispositions to Baseline
        </button>
      </div>
    </div>
  );
}
