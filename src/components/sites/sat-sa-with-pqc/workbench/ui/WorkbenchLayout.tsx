"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutGrid,
  Building2,
  ListChecks,
  FileSearch,
  LineChart,
  DatabaseZap,
  FileSpreadsheet,
  ShieldCheck,
  Settings,
  Network,
  RotateCcw,
  RefreshCw,
  Menu,
  X,
  ChevronDown,
  CalendarRange,
  Layers,
  Globe,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import Grainient from "@/components/reactbits/Grainient";
import { useWorkbench } from "../state/WorkbenchContext";
import { ALL_COHORTS, summarizeWorkbench } from "../state/derived";

interface WorkbenchLayoutProps {
  children: React.ReactNode;
}

type BadgeTone = "info" | "attention";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: { value: number; tone: BadgeTone; label: string };
}

const EXAMINER = { name: "A. Sharma", role: "Lead examiner", initials: "AS" };

export const WorkbenchLayout: React.FC<WorkbenchLayoutProps> = ({ children }) => {
  const pathname = usePathname();
  const {
    entitiesList,
    queueItems,
    auditEntries,
    selectedCohort,
    setSelectedCohort,
    selectedPeriod,
    undoLastAction,
    lastActionSummary,
    resetToBaseline,
  } = useWorkbench();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [adminMenuOpen, setAdminMenuOpen] = useState(false);

  const summary = useMemo(
    () => summarizeWorkbench(entitiesList, queueItems, auditEntries, selectedCohort),
    [entitiesList, queueItems, auditEntries, selectedCohort],
  );

  const cohorts = useMemo(
    () => [ALL_COHORTS, ...Array.from(new Set(entitiesList.map((e) => e.cohort))).sort()],
    [entitiesList],
  );

  const navGroups: Array<{ title: string; items: NavItem[] }> = [
    {
      title: "Workbench",
      items: [{ href: "/workbench/overview", label: "Workbench", icon: LayoutGrid }],
    },
    {
      title: "Assess",
      items: [
        { href: "/workbench/entities", label: "Entities", icon: Building2 },
        { href: "/workbench/findings", label: "Findings", icon: FileSearch },
        {
          href: "/workbench/review-queue",
          label: "Review Queue",
          icon: ListChecks,
          badge: summary.queueOpen
            ? { value: summary.queueOpen, tone: "info", label: `${summary.queueOpen} open review samples` }
            : undefined,
        },
      ],
    },
    {
      title: "Analyze",
      items: [
        { href: "/workbench/trends", label: "Analytics", icon: LineChart },
        { href: "/workbench/reports", label: "Reports", icon: FileSpreadsheet },
      ],
    },
    {
      title: "Data",
      items: [
        {
          href: "/workbench/submissions",
          label: "Submissions",
          icon: DatabaseZap,
          badge: summary.submissionGaps
            ? { value: summary.submissionGaps, tone: "attention", label: `${summary.submissionGaps} submissions with data gaps` }
            : undefined,
        },
      ],
    },
    {
      title: "Trust & Governance",
      items: [{ href: "/workbench/governance", label: "TRUST-SAT & Audit", icon: ShieldCheck }],
    },
    {
      title: "System",
      items: [
        { href: "/#pipeline", label: "Architecture", icon: Network },
        { href: "/workbench/admin", label: "Administration", icon: Settings },
      ],
    },
  ];

  const isActive = (href: string) =>
    !href.startsWith("/#") && (pathname === href || (href !== "/workbench/overview" && pathname.startsWith(href)));

  return (
    <div
      data-theme="satsa-light"
      className="satsa-light satsa-workbench relative isolate flex min-h-svh bg-[#f7f7fb] font-sans text-slate-950 antialiased selection:bg-violet-200 selection:text-slate-950"
    >
      <Grainient
        className="pointer-events-none absolute inset-0 z-0 opacity-40"
        color1="#EDE9FE"
        color2="#F5F3FF"
        color3="#E0E7FF"
        lightMode
        timeSpeed={0.035}
        colorBalance={0.1}
        warpStrength={0.16}
        warpFrequency={2.1}
        warpSpeed={0.25}
        warpAmplitude={90}
        grainAmount={0.018}
        contrast={1.05}
        saturation={0.68}
      />

      {mobileMenuOpen && (
        <div
          aria-hidden="true"
          onClick={() => setMobileMenuOpen(false)}
          className="fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-sm lg:hidden"
        />
      )}

      <aside
        className={`workbench-sidebar fixed inset-y-0 left-0 z-50 flex w-60 flex-col border-r border-slate-200 bg-white/92 text-slate-700 backdrop-blur-xl transition-transform duration-200 ease-in-out lg:sticky lg:top-0 lg:h-svh lg:translate-x-0 ${
          mobileMenuOpen ? "translate-x-0 shadow-2xl" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <Link
            href="/workbench/overview"
            onClick={() => setMobileMenuOpen(false)}
            className="flex flex-col leading-tight"
          >
            <span className="font-mono text-sm font-bold tracking-[0.14em] text-slate-950">
              SAT<span className="text-violet-600">&middot;</span>SA
            </span>
            <span className="text-xs text-slate-500">Supervisory Analytics</span>
          </Link>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(false)}
            className="grid size-9 place-items-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900 lg:hidden"
            aria-label="Close navigation"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-3" aria-label="Workbench">
          {navGroups.map((group, gi) => (
            <div key={group.title} className={gi === 0 ? "" : "mt-3"}>
              {gi > 0 && (
                <p className="px-3 pb-1 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                  {group.title}
                </p>
              )}
              <ul className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={() => setMobileMenuOpen(false)}
                        aria-current={active ? "page" : undefined}
                        className={`workbench-nav-link group flex h-9 items-center justify-between gap-2 rounded-lg px-3 text-sm font-medium transition-colors ${
                          active
                            ? "bg-violet-50 text-violet-700"
                            : "text-slate-600 hover:bg-slate-100/80 hover:text-slate-950"
                        }`}
                      >
                        <span className="flex min-w-0 items-center gap-2.5">
                          <Icon
                            strokeWidth={1.75}
                            className={`size-4 shrink-0 ${active ? "text-violet-600" : "text-slate-400 group-hover:text-slate-700"}`}
                            aria-hidden="true"
                          />
                          <span className="truncate">{item.label}</span>
                        </span>
                        {item.badge && (
                          <span
                            title={item.badge.label}
                            className={`min-w-6 shrink-0 rounded-full px-1.5 text-center font-mono text-[11px] font-semibold leading-5 tabular-nums ${
                              item.badge.tone === "attention"
                                ? "bg-orange-100 text-orange-700"
                                : "bg-blue-50 text-blue-700"
                            }`}
                          >
                            <span aria-hidden="true">{item.badge.value}</span>
                            <span className="sr-only">{item.badge.label}</span>
                          </span>
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-slate-200 px-3 py-3">
          <Link
            href="/"
            className="flex h-9 items-center gap-2.5 rounded-lg px-3 text-sm text-slate-500 transition-colors hover:bg-slate-100/80 hover:text-slate-900"
          >
            <Globe strokeWidth={1.75} className="size-4" aria-hidden="true" />
            <span>Public site</span>
          </Link>
        </div>
      </aside>

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <header className="workbench-topbar sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white/85 px-4 backdrop-blur sm:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="grid size-9 place-items-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:text-slate-950 lg:hidden"
              aria-label="Open navigation"
            >
              <Menu className="size-4" aria-hidden="true" />
            </button>

            <span
              className="hidden items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 sm:inline-flex"
              title="Assessment period"
            >
              <CalendarRange className="size-4 text-violet-600" strokeWidth={1.75} aria-hidden="true" />
              <span className="sr-only">Assessment period:</span>
              <strong className="font-semibold text-slate-950">{selectedPeriod}</strong>
            </span>

            <label className="relative inline-flex min-w-0 items-center gap-2 rounded-lg border border-slate-200 bg-white py-1.5 pl-3 pr-2 text-sm text-slate-700 focus-within:border-violet-400">
              <Layers className="size-4 shrink-0 text-violet-600" strokeWidth={1.75} aria-hidden="true" />
              <span className="sr-only">Cohort</span>
              <select
                value={selectedCohort}
                onChange={(e) => setSelectedCohort(e.target.value)}
                className="min-w-0 max-w-[16rem] cursor-pointer truncate bg-transparent pr-1 font-medium text-slate-950 focus:outline-none"
              >
                {cohorts.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="relative shrink-0">
            <button
              type="button"
              onClick={() => setAdminMenuOpen(!adminMenuOpen)}
              className="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 text-sm text-slate-700 transition-colors hover:bg-slate-100"
              aria-expanded={adminMenuOpen}
              aria-haspopup="menu"
              aria-label={`${EXAMINER.name}, ${EXAMINER.role}. Supervisory controls`}
            >
              <span className="grid size-8 place-items-center rounded-full bg-violet-600 font-mono text-xs font-semibold text-white">
                {EXAMINER.initials}
              </span>
              <span className="hidden text-left leading-tight md:block">
                <span className="block font-medium text-slate-950">{EXAMINER.name}</span>
                <span className="block text-xs text-slate-500">{EXAMINER.role}</span>
              </span>
              <ChevronDown className="size-4 text-slate-400" aria-hidden="true" />
            </button>

            {adminMenuOpen && (
              <>
                <div aria-hidden="true" onClick={() => setAdminMenuOpen(false)} className="fixed inset-0 z-30" />
                <div
                  role="menu"
                  className="absolute right-0 top-full z-40 mt-2 w-64 rounded-xl border border-slate-200 bg-white p-2 shadow-xl"
                >
                  {lastActionSummary && (
                    <p className="mb-1 rounded-lg bg-violet-50 px-2.5 py-2 text-xs text-violet-800">{lastActionSummary}</p>
                  )}
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      undoLastAction();
                      setAdminMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-orange-700 hover:bg-orange-50"
                  >
                    <RotateCcw className="size-4" aria-hidden="true" />
                    Undo last review
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      resetToBaseline();
                      setAdminMenuOpen(false);
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-slate-700 hover:bg-slate-100"
                  >
                    <RefreshCw className="size-4" aria-hidden="true" />
                    Reset to baseline
                  </button>
                  <div className="my-1 border-t border-slate-200" />
                  <Link
                    href="/workbench/admin"
                    role="menuitem"
                    onClick={() => setAdminMenuOpen(false)}
                    className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-slate-700 hover:bg-slate-100"
                  >
                    <Settings className="size-4" aria-hidden="true" />
                    Administration
                  </Link>
                </div>
              </>
            )}
          </div>
        </header>

        <main className="workbench-main flex-1 px-4 sm:px-6">{children}</main>
      </div>
    </div>
  );
};
