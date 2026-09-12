"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Building2,
  ListOrdered,
  FileSearch,
  LineChart,
  Database,
  FileSpreadsheet,
  ShieldCheck,
  Settings,
  RefreshCw,
  RotateCcw,
  WifiOff,
  ArrowLeft,
  Filter,
} from "lucide-react";
import { useWorkbench } from "../state/WorkbenchContext";

interface WorkbenchLayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { href: "/workbench/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/workbench/entities", label: "Entities", icon: Building2, badge: "42" },
  { href: "/workbench/review-queue", label: "Review Queue", icon: ListOrdered, badge: "23", badgeVariant: "navigational" as const },
  { href: "/workbench/findings", label: "Findings", icon: FileSearch, badge: "8 Attention", badgeVariant: "attention" as const },
  { href: "/workbench/trends", label: "Trends & Benchmarks", icon: LineChart },
  { href: "/workbench/submissions", label: "Data Submissions", icon: Database, badge: "3 Gaps", badgeVariant: "attention" as const },
  { href: "/workbench/reports", label: "Reports", icon: FileSpreadsheet },
  { href: "/workbench/governance", label: "Governance & Audit", icon: ShieldCheck, badge: "PQC OK", badgeVariant: "verified" as const },
  { href: "/workbench/admin", label: "Administration", icon: Settings },
];

export const WorkbenchLayout: React.FC<WorkbenchLayoutProps> = ({ children }) => {
  const pathname = usePathname();
  const {
    selectedCohort,
    setSelectedCohort,
    selectedPeriod,
    undoLastAction,
    lastActionSummary,
    resetToBaseline,
  } = useWorkbench();

  const [refreshSpin, setRefreshSpin] = useState<boolean>(false);

  const handleRefresh = () => {
    setRefreshSpin(true);
    setTimeout(() => setRefreshSpin(false), 600);
  };

  const cohortsList = [
    "All Cohorts",
    "Large financial-services CSEs",
    "Defence · on-prem",
    "Energy & Power SCADA Cohort",
    "Telecom Tier-1 Backbone CSEs",
    "Transport & Civil Aviation Radar CSEs",
  ];

  return (
    <div className="flex min-h-screen bg-[#070d17] text-slate-100 font-sans antialiased selection:bg-blue-600 selection:text-white">
      {/* Short Task-Based Left Sidebar */}
      <aside className="w-64 shrink-0 flex flex-col border-r border-[#15233c] bg-[#0a1222] text-slate-300">
        {/* Brand / Header */}
        <div className="flex flex-col border-b border-[#15233c] p-4">
          <div className="flex items-center justify-between">
            <Link
              href="/workbench/overview"
              className="flex items-center gap-2.5 font-mono text-xs font-bold uppercase tracking-wider text-white hover:text-blue-400 transition-colors"
            >
              <span className="size-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
              <span>SAT&middot;SA Workbench</span>
            </Link>
            <span className="rounded bg-slate-800/80 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-slate-400">
              NCIIPC
            </span>
          </div>
          <div className="mt-2 text-[11px] text-slate-400 font-mono flex items-center justify-between">
            <span>Supervisory Workbench</span>
            <span className="text-emerald-400 font-semibold">Offline Ready</span>
          </div>
        </div>

        {/* Back to Public Landing Page Link */}
        <div className="border-b border-[#15233c] px-4 py-2 bg-slate-950/40">
          <Link
            href="/"
            className="flex items-center gap-2 text-xs font-mono text-slate-400 hover:text-slate-200 transition-colors"
          >
            <ArrowLeft className="size-3.5 text-blue-400" />
            <span>Public SAT-SA Site</span>
          </Link>
        </div>

        {/* Task-Based Navigation */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          <div className="px-2 pb-1 text-[10px] font-mono uppercase tracking-wider text-slate-500 font-semibold">
            Supervisory Tasks
          </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive =
              pathname === item.href ||
              (item.href !== "/workbench/overview" && pathname.startsWith(item.href));

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`group flex items-center justify-between rounded-md px-3 py-2 text-xs font-medium transition-all ${
                  isActive
                    ? "bg-blue-600/20 text-blue-300 font-semibold border border-blue-500/30"
                    : "text-slate-300 hover:bg-[#121f36] hover:text-white"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Icon
                    className={`size-4 transition-colors ${
                      isActive ? "text-blue-400" : "text-slate-400 group-hover:text-slate-200"
                    }`}
                  />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span
                    className={`rounded px-1.5 py-0.2 font-mono text-[10px] uppercase font-medium ${
                      item.badgeVariant === "attention"
                        ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                        : item.badgeVariant === "verified"
                        ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                        : item.badgeVariant === "navigational"
                        ? "bg-blue-500/15 text-blue-300 border border-blue-500/30"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Examiner Role & Cryptographic Trust Footer */}
        <div className="border-t border-[#15233c] p-3 space-y-2 bg-[#080f1c]">
          <div className="rounded border border-slate-800/80 bg-slate-900/60 p-2 text-xs font-mono">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>Examiner:</span>
              <span className="text-slate-200 font-semibold">A. Sharma (Lead)</span>
            </div>
            <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
              <span>Station: EXAM-DEL-04</span>
              <span className="text-blue-400">Restricted</span>
            </div>
          </div>

          <div className="flex items-center justify-between px-1 text-[11px] font-mono text-emerald-400">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="size-3.5" />
              <span>ML-DSA-65 Valid</span>
            </div>
            <span className="text-[10px] text-slate-500">103 Blocks</span>
          </div>

          <div className="flex items-center gap-1.5 px-1 text-[10px] font-mono text-slate-500">
            <WifiOff className="size-3" />
            <span>Air-Gapped: 0 SaaS requests</span>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Supervisory Bar */}
        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-[#15233c] bg-[#0a1222]/95 px-6 py-2.5 backdrop-blur">
          {/* Left Context: Assessment Period & Cohort Filter */}
          <div className="flex flex-wrap items-center gap-3 font-mono text-xs">
            <div className="flex items-center gap-1.5 rounded border border-[#1d2f50] bg-[#0e192f] px-2.5 py-1">
              <span className="text-slate-400 uppercase text-[10px]">Assessment Period:</span>
              <strong className="text-white">{selectedPeriod}</strong>
            </div>

            {/* Cohort Selector */}
            <div className="relative flex items-center gap-1.5 rounded border border-[#1d2f50] bg-[#0e192f] px-2.5 py-1">
              <Filter className="size-3 text-slate-400" />
              <span className="text-slate-400 uppercase text-[10px]">Cohort:</span>
              <select
                aria-label="Filter by Entity Cohort"
                value={selectedCohort}
                onChange={(e) => setSelectedCohort(e.target.value)}
                className="bg-transparent text-white focus:outline-none cursor-pointer pr-4 font-mono text-xs"
              >
                {cohortsList.map((c) => (
                  <option key={c} value={c} className="bg-slate-900 text-white">
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* Refresh button */}
            <button
              type="button"
              onClick={handleRefresh}
              className="flex items-center gap-1.5 rounded border border-[#1d2f50] bg-[#0e192f] px-2.5 py-1 text-slate-300 hover:bg-[#152545] hover:text-white transition-colors"
              title="Refresh local analytical run cache"
            >
              <RefreshCw className={`size-3 text-blue-400 ${refreshSpin ? "animate-spin" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>

          {/* Right Controls: Revertable State & Audit Indicators */}
          <div className="flex items-center gap-3 font-mono text-xs">
            {lastActionSummary && (
              <span className="hidden lg:inline-block rounded bg-blue-950/60 border border-blue-800/40 px-2 py-0.5 text-[11px] text-blue-300">
                {lastActionSummary}
              </span>
            )}

            <button
              type="button"
              onClick={undoLastAction}
              className="flex items-center gap-1.5 rounded border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-amber-300 hover:bg-amber-500/20 transition-colors"
              title="Revert the most recent review action and append an auditable reversal record"
            >
              <RotateCcw className="size-3" />
              <span>Undo Last Review</span>
            </button>

            <button
              type="button"
              onClick={resetToBaseline}
              className="rounded border border-slate-700 bg-slate-800/60 px-2 py-1 text-[11px] text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
              title="Reset state to initial verified assessment cycle baseline"
            >
              Reset Baseline
            </button>
          </div>
        </header>

        {/* Page Children Container */}
        <main className="flex-1 p-6 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
