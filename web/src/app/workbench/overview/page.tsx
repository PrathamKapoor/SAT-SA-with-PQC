"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  ChevronRight,
  DatabaseZap,
  FileSearch,
  Gavel,
  LineChart,
  ListChecks,
  OctagonAlert,
  ShieldCheck,
  Target,
} from "lucide-react";
import { useWorkbench } from "@/components/sites/sat-sa-with-pqc/workbench/state/WorkbenchContext";
import {
  averageDimensions,
  entitiesInCohort,
  summarizeWorkbench,
} from "@/components/sites/sat-sa-with-pqc/workbench/state/derived";
import { CapabilityBar } from "@/components/sites/sat-sa-with-pqc/workbench/ui/HeatmapNCIIPC";

interface ActionCard {
  href: string;
  title: string;
  description: string;
  icon: LucideIcon;
  metric?: { value: number; label: string; tone?: "info" };
  flag?: { value: number; label: string; tone: "attention" | "critical" | "verified" };
}

interface SopStep {
  href: string;
  title: string;
  description: string;
  icon: LucideIcon;
  progress?: { done: number; total: number; label: string };
}

const PRIORITY_TONE: Record<string, string> = {
  critical: "bg-red-50 text-red-700 ring-red-200",
  high: "bg-orange-50 text-orange-700 ring-orange-200",
  medium: "bg-slate-100 text-slate-700 ring-slate-200",
  low: "bg-slate-100 text-slate-600 ring-slate-200",
};

export default function WorkbenchPage() {
  const { entitiesList, queueItems, auditEntries, selectedCohort, selectedPeriod } = useWorkbench();

  const summary = useMemo(
    () => summarizeWorkbench(entitiesList, queueItems, auditEntries, selectedCohort),
    [entitiesList, queueItems, auditEntries, selectedCohort],
  );
  const dimensions = useMemo(
    () => averageDimensions(entitiesInCohort(entitiesList, selectedCohort)),
    [entitiesList, selectedCohort],
  );

  const actions: ActionCard[] = [
    {
      href: "/workbench/submissions",
      title: "Ingest Data",
      description: "Validate CSE submissions",
      icon: DatabaseZap,
      metric: { value: summary.submissions, label: "submissions" },
      flag: summary.submissionGaps
        ? { value: summary.submissionGaps, label: "with data gaps", tone: "attention" }
        : undefined,
    },
    {
      href: "/workbench/entities",
      title: "Entities",
      description: "Rank CSEs by supervisory risk",
      icon: Building2,
      metric: { value: summary.entities, label: "entities assessed" },
      flag: summary.attentionEntities
        ? { value: summary.attentionEntities, label: "high risk", tone: "attention" }
        : undefined,
    },
    {
      href: "/workbench/findings",
      title: "Findings",
      description: "Inspect evidence-backed signals",
      icon: FileSearch,
      metric: { value: summary.findings, label: "findings" },
      flag: summary.severeFindings
        ? { value: summary.severeFindings, label: "critical or high severity", tone: "critical" }
        : undefined,
    },
    {
      href: "/workbench/review-queue",
      title: "Review Queue",
      description: "Record supervisory decisions",
      icon: ListChecks,
      metric: { value: summary.queueOpen, label: "open review samples", tone: "info" },
    },
    {
      href: "/workbench/trends",
      title: "Analytics",
      description: "Capabilities, trends and peers",
      icon: LineChart,
      metric: { value: dimensions.length, label: "capability dimensions" },
    },
    {
      href: "/workbench/governance",
      title: "TRUST-SAT",
      description: "Verify evidence integrity",
      icon: ShieldCheck,
      metric: { value: summary.ledgerBlocks, label: "ledger blocks" },
      flag: summary.ledgerVerified
        ? { value: 0, label: "Ledger signatures verified", tone: "verified" }
        : { value: 0, label: "Ledger verification failed", tone: "critical" },
    },
  ];

  const sop: SopStep[] = [
    { href: "/workbench/entities", title: "Triage attention", description: "Start with the highest-risk CSEs", icon: Target },
    { href: "/workbench/findings", title: "Inspect evidence", description: "Read the signals behind each score", icon: FileSearch },
    {
      href: "/workbench/review-queue",
      title: "Record decision",
      description: "Confirm, dismiss or escalate",
      icon: Gavel,
      progress: {
        done: summary.queueReviewed,
        total: summary.queueTotal,
        label: `${summary.queueReviewed} of ${summary.queueTotal} samples reviewed`,
      },
    },
    { href: "/workbench/governance", title: "Verify & report", description: "Check the ledger, export the packet", icon: ShieldCheck },
  ];

  const next = summary.nextQueueItem;

  return (
    <div data-workbench-launch="true" className="workbench-launch mx-auto flex w-full max-w-[1320px] flex-col">
      {/* Where am I, which assessment, what is next */}
      <header className="workbench-launch__head grid items-end gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
        <div className="min-w-0">
          <p className="whitespace-nowrap font-mono text-xs font-semibold uppercase tracking-[0.16em] text-violet-700">
            Supervisory workbench <span className="text-slate-300" aria-hidden="true">/</span>{" "}
            <span className="text-slate-500">{selectedPeriod}</span>
          </p>
          <h1 className="workbench-launch__title mt-2 font-semibold tracking-[-0.035em] text-slate-950">
            Supervisory intelligence.
          </h1>
          <p className="workbench-launch__lede mt-1 text-slate-500">Analyse. Prioritise. Review. Decide.</p>
        </div>

        {next ? (
          <Link
            href={`/workbench/findings/${next.findingId}`}
            className="workbench-next group flex min-w-0 items-center gap-3 rounded-2xl border border-slate-200 bg-white/90 p-3 pr-4 transition-colors hover:border-violet-300"
          >
            <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-violet-600 text-white">
              <ArrowRight className="size-5" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-2">
                <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Next review</span>
                <span
                  className={`rounded-full px-2 font-mono text-[11px] font-semibold uppercase leading-5 ring-1 ring-inset ${PRIORITY_TONE[next.priority]}`}
                >
                  {next.priority}
                </span>
              </span>
              <span className="mt-0.5 block truncate text-sm font-semibold text-slate-950" title={next.priorityReason}>
                {next.entityName}
              </span>
              <span className="block truncate text-sm text-slate-500">
                {next.findingFamilyLabel} <span aria-hidden="true">&middot;</span> {next.alertOrCaseId}
              </span>
            </span>
            <ChevronRight className="size-4 shrink-0 text-slate-300 group-hover:text-violet-600" aria-hidden="true" />
          </Link>
        ) : (
          <Link
            href="/workbench/review-queue"
            className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white/90 p-3 pr-4 text-sm text-slate-700 hover:border-violet-300"
          >
            <CheckCircle2 className="size-5 text-violet-600" aria-hidden="true" />
            Review queue is clear for this cohort
          </Link>
        )}
      </header>

      {/* What can I do */}
      <nav aria-label="Supervisory workflows" className="workbench-launch__actions grid auto-rows-fr grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        {actions.map((action) => {
          const Icon = action.icon;
          return (
            <Link
              key={action.href}
              href={action.href}
              title={action.description}
              className="workbench-action group min-w-0 rounded-2xl border border-slate-200 bg-white/95 transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:border-violet-300"
            >
              <span className="workbench-action__inner flex h-full flex-col justify-between">
              <span className="workbench-action__top flex items-start justify-between gap-3">
                <span className="workbench-action__icon grid size-10 shrink-0 place-items-center rounded-xl bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-100 transition-colors group-hover:bg-violet-600 group-hover:text-white">
                  <Icon className="size-5" strokeWidth={1.75} aria-hidden="true" />
                </span>
                <ArrowUpRight
                  className="workbench-action__arrow size-5 shrink-0 text-slate-300 transition-colors group-hover:text-violet-600"
                  aria-hidden="true"
                />
              </span>

              <span className="workbench-action__body flex min-w-0 items-end justify-between gap-3">
                <span className="min-w-0">
                  <span className="block text-lg font-semibold tracking-[-0.02em] text-slate-950">{action.title}</span>
                  <span className="workbench-action__desc block truncate text-sm text-slate-500">{action.description}</span>
                </span>

                <span className="flex shrink-0 items-center gap-2">
                  {action.flag && <ActionFlag flag={action.flag} />}
                  {action.metric && (
                    <span
                      className={`font-semibold leading-none tracking-[-0.04em] tabular-nums workbench-action__metric ${
                        action.metric.tone === "info" ? "text-blue-700" : "text-slate-950"
                      }`}
                      title={`${action.metric.value} ${action.metric.label}`}
                    >
                      <span aria-hidden="true">{action.metric.value}</span>
                      <span className="sr-only">
                        {action.metric.value} {action.metric.label}
                      </span>
                    </span>
                  )}
                </span>
              </span>
              </span>
            </Link>
          );
        })}
      </nav>

      {/* How to proceed, and where capability stands */}
      <div className="workbench-launch__panels grid grid-cols-1 lg:grid-cols-2">
        <section aria-labelledby="sop-heading" className="workbench-launch-panel flex flex-col rounded-2xl border border-slate-200 bg-white/95">
          <div className="flex items-center justify-between">
            <h2 id="sop-heading" className="text-base font-semibold tracking-[-0.01em] text-slate-950">
              SOP
            </h2>
            <span className="font-mono text-xs uppercase tracking-[0.14em] text-slate-400">Review cycle</span>
          </div>
          <ol className="workbench-sop mt-2 flex flex-1 flex-col justify-around divide-y divide-slate-200/80">
            {sop.map((step, i) => {
              const Icon = step.icon;
              const pct = step.progress && step.progress.total ? (step.progress.done / step.progress.total) * 100 : 0;
              return (
                <li key={step.title}>
                  <Link
                    href={step.href}
                    title={step.description}
                    className="workbench-sop__step group grid grid-cols-[1.75rem_2rem_minmax(0,1fr)_auto] items-center gap-3 rounded-lg px-1 transition-colors hover:bg-violet-50/60"
                  >
                    <span className="font-mono text-xs font-semibold text-slate-400">{String(i + 1).padStart(2, "0")}</span>
                    <span className="grid size-8 place-items-center rounded-lg bg-slate-100 text-slate-600 group-hover:bg-violet-100 group-hover:text-violet-700">
                      <Icon className="size-4" strokeWidth={1.75} aria-hidden="true" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-semibold text-slate-950">{step.title}</span>
                      <span className="workbench-sop__desc block truncate text-sm text-slate-500">{step.description}</span>
                    </span>
                    {step.progress ? (
                      <span className="flex items-center gap-2" title={step.progress.label}>
                        <span className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-200" aria-hidden="true">
                          <span className="block h-full rounded-full bg-violet-600" style={{ width: `${pct}%` }} />
                        </span>
                        <span className="font-mono text-xs font-semibold tabular-nums text-slate-700">
                          <span aria-hidden="true">
                            {step.progress.done}/{step.progress.total}
                          </span>
                          <span className="sr-only">{step.progress.label}</span>
                        </span>
                      </span>
                    ) : (
                      <ChevronRight className="size-4 text-slate-300 group-hover:text-violet-600" aria-hidden="true" />
                    )}
                  </Link>
                </li>
              );
            })}
          </ol>
        </section>

        <section aria-labelledby="capability-heading" className="workbench-launch-panel rounded-2xl border border-slate-200 bg-white/95">
          <div className="flex items-center justify-between">
            <h2 id="capability-heading" className="text-base font-semibold tracking-[-0.01em] text-slate-950">
              Capability overview
            </h2>
            <Link
              href="/workbench/trends#capabilities"
              aria-label="Open full capability analysis"
              title="Full capability analysis"
              className="grid size-8 place-items-center rounded-lg text-slate-400 transition-colors hover:bg-violet-50 hover:text-violet-700"
            >
              <ArrowUpRight className="size-4" aria-hidden="true" />
            </Link>
          </div>
          {dimensions.length ? (
            <ul className="workbench-capabilities mt-2 grid">
              {dimensions.map((dim) => (
                <li key={dim.id} className="grid grid-cols-[minmax(7rem,13rem)_minmax(3rem,1fr)_3.5rem] items-center gap-4">
                  <CapabilityBar dim={dim} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-slate-500">No entities in this cohort.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function ActionFlag({ flag }: { flag: NonNullable<ActionCard["flag"]> }) {
  if (flag.tone === "verified") {
    return (
      <span title={flag.label} className="grid size-7 place-items-center rounded-full bg-violet-50 text-violet-700">
        <ShieldCheck className="size-4" aria-hidden="true" />
        <span className="sr-only">{flag.label}</span>
      </span>
    );
  }
  const Icon = flag.tone === "critical" ? OctagonAlert : AlertTriangle;
  const tone = flag.tone === "critical" ? "bg-red-50 text-red-700" : "bg-orange-50 text-orange-700";
  const text = flag.value ? `${flag.value} ${flag.label}` : flag.label;
  return (
    <span title={text} className={`inline-flex h-7 items-center gap-1 rounded-full px-2 font-mono text-xs font-semibold tabular-nums ${tone}`}>
      <Icon className="size-3.5" aria-hidden="true" />
      {flag.value > 0 && <span aria-hidden="true">{flag.value}</span>}
      <span className="sr-only">{text}</span>
    </span>
  );
}
