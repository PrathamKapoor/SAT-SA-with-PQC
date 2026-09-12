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
  Menu,
  X,
  SlidersHorizontal,
  ChevronDown,
} from "lucide-react";
import { useWorkbench } from "../state/WorkbenchContext";

interface WorkbenchLayoutProps {
  children: React.ReactNode;
}

const navGroups = [
  {
    title: "Supervisory Workflow",
    items: [
      { href: "/workbench/overview", label: "Overview", icon: LayoutDashboard },
      { href: "/workbench/review-queue", label: "Review Queue", icon: ListOrdered, badge: "23", badgeVariant: "navigational" as const },
      { href: "/workbench/entities", label: "Entities", icon: Building2, badge: "42", badgeVariant: "neutral" as const },
      { href: "/workbench/findings", label: "Findings", icon: FileSearch, badge: "8", badgeVariant: "attention" as const },
    ],
  },
  {
    title: "Benchmarking & Data",
    items: [
      { href: "/workbench/trends", label: "Trends & Benchmarks", icon: LineChart },
      { href: "/workbench/submissions", label: "Data Submissions", icon: Database, badge: "3 Gaps", badgeVariant: "attention" as const },
      { href: "/workbench/reports", label: "Reports", icon: FileSpreadsheet },
    ],
  },
  {
    title: "Assurance & System",
    items: [
      { href: "/workbench/governance", label: "Governance & Audit", icon: ShieldCheck, badge: "PQC OK", badgeVariant: "verified" as const },
      { href: "/workbench/admin", label: "Administration", icon: Settings },
    ],
  },
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
  const [mobileMenuOpen, setMobileMenuOpen] = useState<boolean>(false);
  const [adminMenuOpen, setAdminMenuOpen] = useState<boolean>(false);

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
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div
          aria-hidden="true"
          onClick={() => setMobileMenuOpen(false)}
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
        />
      )}

      {/* Sidebar: 240px fixed desktop width */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-60 flex-col border-r border-[#15233c] bg-[#0a1222] text-slate-300 transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 ${
          mobileMenuOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"
        }`}
      >
        {/* Brand / Header */}
        <div className="flex flex-col border-b border-[#15233c] p-4">
          <div className="flex items-center justify-between">
            <Link
              href="/workbench/overview"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-wider text-white hover:text-blue-400 transition-colors"
            >
              <span className="size-2 rounded-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
              <span>SAT&middot;SA Workbench</span>
            </Link>
            <div className="flex items-center gap-1.5">
              <span className="rounded bg-slate-800/80 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-slate-400">
                NCIIPC
              </span>
              <button
                type="button"
                onClick={() => setMobileMenuOpen(false)}
                className="p-1 text-slate-400 hover:text-white lg:hidden"
                aria-label="Close navigation sidebar"
              >
                <X className="size-4" />
              </button>
            </div>
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] font-mono text-slate-400">
            <span>Supervisory Workbench</span>
            <span className="font-semibold text-emerald-400">Offline Ready</span>
          </div>
        </div>

        {/* Public Site Switcher */}
        <div className="border-b border-[#15233c] bg-slate-950/40 px-4 py-2">
          <Link
            href="/"
            className="flex items-center gap-2 font-mono text-xs text-slate-400 hover:text-slate-200 transition-colors"
          >
            <ArrowLeft className="size-3.5 text-blue-400" />
            <span>Public SAT-SA Site</span>
          </Link>
        </div>

        {/* Grouped Navigation */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-4">
          {navGroups.map((group) => (
            <div key={group.title} className="space-y-1">
              <div className="px-2 pb-1 text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-500">
                {group.title}
              </div>
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/workbench/overview" && pathname.startsWith(item.href));

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`group flex items-center justify-between rounded-md px-2.5 py-1.5 text-xs font-medium transition-all ${
                      isActive
                        ? "border border-blue-500/30 bg-blue-600/20 font-semibold text-blue-300"
                        : "text-slate-300 hover:bg-[#121f36] hover:text-white"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon
                        className={`size-4 shrink-0 transition-colors ${
                          isActive ? "text-blue-400" : "text-slate-400 group-hover:text-slate-200"
                        }`}
                      />
                      <span className="truncate">{item.label}</span>
                    </div>
                    {item.badge && (
                      <span
                        className={`ml-2 shrink-0 rounded px-1.5 py-0.2 font-mono text-[10px] font-medium uppercase ${
                          item.badgeVariant === "attention"
                            ? "border border-amber-500/30 bg-amber-500/15 text-amber-300"
                            : item.badgeVariant === "verified"
                            ? "border border-emerald-500/30 bg-emerald-500/15 text-emerald-300"
                            : item.badgeVariant === "navigational"
                            ? "border border-blue-500/30 bg-blue-500/15 text-blue-300"
                            : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {item.badge}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Examiner Role & Cryptographic Trust Footer */}
        <div className="border-t border-[#15233c] bg-[#080f1c] p-3 space-y-2">
          <div className="rounded border border-slate-800/80 bg-slate-900/60 p-2 font-mono text-xs">
            <div className="flex items-center justify-between text-[11px] text-slate-400">
              <span>Examiner:</span>
              <span className="font-semibold text-slate-200">A. Sharma (Lead)</span>
            </div>
            <div className="mt-1 flex items-center justify-between text-[10px] text-slate-500">
              <span>Station: EXAM-DEL-04</span>
              <span className="text-blue-400">Restricted</span>
            </div>
          </div>

          <div className="flex items-center justify-between px-1 font-mono text-[11px] text-emerald-400">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="size-3.5" />
              <span>ML-DSA-65 Valid</span>
            </div>
            <span className="text-[10px] text-slate-500">103 Blocks</span>
          </div>

          <div className="flex items-center gap-1.5 px-1 font-mono text-[10px] text-slate-500">
            <WifiOff className="size-3" />
            <span>Air-Gapped: 0 SaaS requests</span>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Supervisory Bar */}
        <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-3 border-b border-[#15233c] bg-[#0a1222]/95 px-4 py-2.5 backdrop-blur sm:px-6">
          {/* Left Context: Mobile toggle + Assessment Period & Cohort Filter */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-3 font-mono text-xs">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="rounded border border-slate-700 bg-[#0e192f] p-1.5 text-slate-300 hover:text-white lg:hidden"
              aria-label="Open navigation sidebar"
            >
              <Menu className="size-4" />
            </button>

            {/* Assessment Period */}
            <div className="flex items-center gap-1.5 rounded border border-[#1d2f50] bg-[#0e192f] px-2.5 py-1">
              <span className="text-[10px] uppercase text-slate-400">Period:</span>
              <strong className="text-white">{selectedPeriod}</strong>
            </div>

            {/* Cohort Selector */}
            <div className="relative flex items-center gap-1.5 rounded border border-[#1d2f50] bg-[#0e192f] px-2.5 py-1">
              <Filter className="size-3 text-slate-400" />
              <span className="text-[10px] uppercase text-slate-400">Cohort:</span>
              <select
                aria-label="Filter by Entity Cohort"
                value={selectedCohort}
                onChange={(e) => setSelectedCohort(e.target.value)}
                className="cursor-pointer bg-transparent pr-4 font-mono text-xs text-white focus:outline-none"
              >
                {cohortsList.map((c) => (
                  <option key={c} value={c} className="bg-slate-900 text-white">
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* Secondary action: Refresh */}
            <button
              type="button"
              onClick={handleRefresh}
              className="flex items-center gap-1.5 rounded border border-[#1d2f50] bg-[#0e192f] px-2.5 py-1 text-slate-300 transition-colors hover:bg-[#152545] hover:text-white"
              title="Refresh local analytical run cache"
            >
              <RefreshCw className={`size-3 text-blue-400 ${refreshSpin ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>

          {/* Right Controls: Primary Review Action + Tertiary Admin Menu */}
          <div className="flex items-center gap-2 sm:gap-3 font-mono text-xs">
            {/* Primary Action: Open Review Queue */}
            <Link
              href="/workbench/review-queue"
              className="flex items-center gap-1.5 rounded bg-blue-600 px-3 py-1 font-mono text-xs font-semibold text-white shadow-sm transition-colors hover:bg-blue-500 active:bg-blue-700"
            >
              <ListOrdered className="size-3.5" />
              <span>Open Review Queue</span>
              <span className="hidden rounded bg-blue-800 px-1 py-0.2 text-[10px] md:inline">
                23 due
              </span>
            </Link>

            {/* Tertiary Administrative / Reversal Dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setAdminMenuOpen(!adminMenuOpen)}
                className="flex items-center gap-1.5 rounded border border-slate-700/80 bg-slate-800/60 px-2 py-1 text-slate-400 transition-colors hover:border-slate-600 hover:bg-slate-800 hover:text-slate-200"
                title="Supervisory actions & audit controls"
                aria-expanded={adminMenuOpen}
              >
                <SlidersHorizontal className="size-3 text-slate-400" />
                <span className="hidden md:inline">Admin</span>
                <ChevronDown className="size-3 text-slate-500" />
              </button>

              {adminMenuOpen && (
                <>
                  <div
                    aria-hidden="true"
                    onClick={() => setAdminMenuOpen(false)}
                    className="fixed inset-0 z-30"
                  />
                  <div className="absolute right-0 top-full z-40 mt-1 w-64 rounded-lg border border-slate-800 bg-[#0c1628] p-2 shadow-xl">
                    <div className="px-2 py-1 text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-400">
                      Supervisory Controls
                    </div>

                    {lastActionSummary && (
                      <div className="my-1 rounded bg-blue-950/60 border border-blue-800/40 p-2 text-[11px] text-blue-300">
                        <span className="block text-[10px] uppercase text-slate-400">Last Action:</span>
                        {lastActionSummary}
                      </div>
                    )}

                    <div className="mt-2 space-y-1">
                      <button
                        type="button"
                        onClick={() => {
                          undoLastAction();
                          setAdminMenuOpen(false);
                        }}
                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-amber-300 hover:bg-amber-500/10 transition-colors"
                      >
                        <RotateCcw className="size-3.5" />
                        <span>Undo Last Review</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          resetToBaseline();
                          setAdminMenuOpen(false);
                        }}
                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-slate-400 hover:bg-slate-800 hover:text-slate-200 transition-colors"
                      >
                        <RefreshCw className="size-3.5" />
                        <span>Reset Baseline Data</span>
                      </button>

                      <div className="border-t border-slate-800 my-1" />

                      <Link
                        href="/workbench/admin"
                        onClick={() => setAdminMenuOpen(false)}
                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                      >
                        <Settings className="size-3.5" />
                        <span>Full Admin Console</span>
                      </Link>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        {/* Page Children Container */}
        <main className="flex-1 p-4 sm:p-6 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
};
