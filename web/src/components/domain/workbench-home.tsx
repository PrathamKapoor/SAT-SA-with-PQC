"use client";

import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  ChevronRight,
  Crosshair,
  Database,
  FileSearch,
  FileText,
  Gavel,
  Layers,
  Server,
  ShieldCheck,
  Upload,
  Users,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { NavIcon } from "@/components/shell/nav-icon";
import { Tag } from "@/components/ui/badges";
import { FAMILY_LABEL, ruleTitle } from "@/lib/domain/labels";
import type { NavIcon as NavIconName } from "@/lib/nav";
import { useReviewStore } from "@/lib/review-store";
import { cn } from "@/lib/utils";
import type { StepProgress, WorkflowStep } from "@/lib/workbench/profile";
import { useAwaiting } from "./attention-queue";
import type { FindingRowData } from "./finding-row";

const S = "[@media(min-width:1024px)_and_(max-height:820px)]";

export interface TileFlag {
  label: string;
  tone: "attention" | "critical" | "brand" | "info";
  icon?: "alert" | "shield";
}

/** One of the six primary destinations. Same component for every role. */
export function WorkbenchTile({
  href,
  icon,
  title,
  description,
  value,
  flag,
  valueTone = "ink",
  emphasis = false,
}: {
  href: string;
  icon: NavIconName;
  title: string;
  description: string;
  value: ReactNode;
  flag?: TileFlag;
  valueTone?: "ink" | "brand" | "info";
  emphasis?: boolean;
}) {
  return (
    <Link
      href={href}
      data-tile={title}
      className={cn(
        "group relative flex h-full min-h-0 flex-col justify-between overflow-hidden rounded-md border bg-paper px-5 py-4 transition-[border-color,box-shadow] hover:shadow-raised focus-visible:border-brand",
        `${S}:py-3`,
        emphasis ? "border-brand/45 hover:border-brand" : "border-line hover:border-ink/25",
      )}
    >
      {emphasis && <span aria-hidden="true" className="absolute inset-x-0 top-0 h-[3px] bg-brand" />}
      <div className="flex items-start justify-between">
        <span aria-hidden="true" className={cn("flex size-9 items-center justify-center rounded-sm", emphasis ? "bg-brand text-white" : "bg-brand-tint text-brand", `${S}:size-8`)}>
          <NavIcon name={icon} className="size-[18px]" />
        </span>
        {emphasis ? (
          <span className="label text-brand-strong">Priority</span>
        ) : (
          <ArrowUpRight className="size-4 text-faint transition-colors group-hover:text-ink" aria-hidden="true" />
        )}
      </div>
      <div className={cn("mt-3 flex items-end justify-between gap-3", `${S}:mt-2`)}>
        <div className="min-w-0">
          <p className="text-[16px] font-semibold tracking-[-0.01em] text-ink">{title}</p>
          <p className="mt-0.5 truncate text-[13px] text-muted">{description}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {flag && (
            <Tag tone={flag.tone} icon={flag.icon === "shield" ? <ShieldCheck className="size-3" aria-hidden="true" /> : <AlertTriangle className="size-3" aria-hidden="true" />}>
              {flag.label}
            </Tag>
          )}
          <span
            className={cn(
              "num text-[30px] leading-none font-semibold tracking-[-0.03em]",
              `${S}:text-[26px]`,
              valueTone === "brand" ? "text-brand" : valueTone === "info" ? "text-info" : "text-ink",
            )}
          >
            {value}
          </span>
        </div>
      </div>
    </Link>
  );
}

/** Awaiting count that also reflects development-session decisions in this browser. */
export function AwaitingValue({ findings }: { findings: FindingRowData[] }) {
  return <>{useAwaiting(findings).length}</>;
}

/** Header card: a pointer to the next thing this role would look at. */
export function ContextCard({
  label,
  title,
  detail,
  href,
  cta,
  tag,
}: {
  label: string;
  title: string;
  detail: string;
  href: string;
  cta?: string;
  tag?: { text: string; tone: "attention" | "info" | "neutral" | "brand" | "critical" };
}) {
  return (
    <Link
      href={href}
      data-context={label}
      className="group flex max-w-[27rem] min-w-0 items-center gap-3.5 rounded-md border border-line bg-paper px-4 py-3 transition-[border-color,box-shadow] hover:border-ink/25 hover:shadow-raised"
    >
      <span aria-hidden="true" className="flex size-10 shrink-0 items-center justify-center rounded-sm bg-brand text-white">
        <ArrowRight className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-2">
          <span className="label">{label}</span>
          {tag && <Tag tone={tag.tone}>{tag.text}</Tag>}
        </span>
        <span className="mt-1 block truncate text-[14px] font-semibold text-ink">{title}</span>
        <span className="block truncate text-[12.5px] text-muted">{detail}</span>
      </span>
      {cta ? (
        <span className="hidden shrink-0 items-center gap-1 text-[12.5px] font-medium text-brand group-hover:text-brand-strong sm:flex">
          {cta}
          <ChevronRight className="size-3.5" aria-hidden="true" />
        </span>
      ) : (
        <ChevronRight className="size-4 shrink-0 text-faint group-hover:text-ink" aria-hidden="true" />
      )}
    </Link>
  );
}

/** Supervisor context: the highest-priority finding still awaiting a decision. */
export function NextReviewCard({ findings, canDecide }: { findings: FindingRowData[]; canDecide: boolean }) {
  const [next] = useAwaiting(findings);
  if (!next) return <ContextCard label="Next review" title="Every finding has a decision" detail="Open decisions to see the record" href="/workbench/decisions" />;
  return (
    <ContextCard
      label="Next review"
      tag={next.severity ? { text: next.severity, tone: next.severity === "high" ? "attention" : next.severity === "medium" ? "info" : "neutral" } : undefined}
      title={next.entityName}
      detail={`${FAMILY_LABEL[next.family]} · ${ruleTitle(next.ruleOrCategory)}`}
      href={`/workbench/findings/${next.id}`}
      cta={canDecide ? "Review now" : "Open"}
    />
  );
}

const STEP_ICON: Record<WorkflowStep["icon"], LucideIcon> = {
  crosshair: Crosshair,
  search: FileSearch,
  gavel: Gavel,
  shield: ShieldCheck,
  upload: Upload,
  chart: BarChart3,
  database: Database,
  file: FileText,
  server: Server,
  users: Users,
  layers: Layers,
};

/**
 * Workflow guide for the active role: product navigation, not an official
 * procedure. Progress bars are real counts; decision progress also reflects
 * development-session decisions recorded in this browser.
 */
export function WorkflowCard({
  steps,
  findings,
  progress,
}: {
  steps: WorkflowStep[];
  findings: FindingRowData[];
  progress: Record<StepProgress, { done: number; total: number }>;
}) {
  const { decisions } = useReviewStore();
  const ids = new Set(findings.map((f) => f.id));
  const devDecided = new Set(decisions.map((d) => d.findingId).filter((id) => ids.has(id))).size;
  const values: Record<StepProgress, { done: number; total: number }> = {
    ...progress,
    decisions: { done: Math.min(progress.decisions.total, progress.decisions.done + devDecided), total: progress.decisions.total },
  };
  return (
    <ol className="mt-1 flex min-h-0 flex-1 flex-col" aria-label="Workflow">
      {steps.map((s, i) => {
        const Icon = STEP_ICON[s.icon];
        const p = s.progress ? values[s.progress] : null;
        return (
          <li key={s.title} className="flex min-h-0 flex-1 border-b border-line/80 last:border-0">
            <Link href={s.href} className="group -mx-2 grid w-full grid-cols-[1.75rem_2.25rem_minmax(0,1fr)_auto] items-center gap-3 rounded-sm px-2 py-1.5 hover:bg-canvas/80">
              <span className="font-mono text-[11.5px] text-faint">{String(i + 1).padStart(2, "0")}</span>
              <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-sm border border-line bg-canvas text-muted group-hover:text-ink">
                <Icon className="size-4" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[14px] font-medium text-ink">{s.title}</span>
                <span className="block truncate text-[12.5px] text-muted">{s.detail}</span>
              </span>
              {p ? (
                <span className="flex items-center gap-2" title={`${p.done} of ${p.total}`}>
                  <span className="h-1.5 w-14 overflow-hidden rounded-[1px] bg-sunken">
                    <span className="block h-full bg-brand" style={{ width: `${p.total ? (p.done / p.total) * 100 : 0}%` }} />
                  </span>
                  <span className="num font-mono text-[11.5px] text-ink-2">
                    {p.done}/{p.total}
                  </span>
                </span>
              ) : (
                <ChevronRight className="size-4 text-faint group-hover:text-ink" aria-hidden="true" />
              )}
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
