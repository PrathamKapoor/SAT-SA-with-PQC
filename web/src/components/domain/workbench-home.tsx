"use client";

import { AlertTriangle, ArrowRight, ArrowUpRight, ChevronRight, Crosshair, FileSearch, Gavel, ShieldCheck, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { Tag } from "@/components/ui/badges";
import { FAMILY_LABEL, ruleTitle } from "@/lib/domain/labels";
import { useReviewStore } from "@/lib/review-store";
import { cn } from "@/lib/utils";
import { useAwaiting } from "./attention-queue";
import type { FindingRowData } from "./finding-row";
import { NavIcon } from "@/components/shell/nav-icon";
import type { NavIcon as NavIconName } from "@/lib/nav";

/** One of the six primary destinations on the Workbench. */
export function WorkbenchTile({
  href,
  icon,
  title,
  description,
  value,
  flag,
  valueTone = "ink",
}: {
  href: string;
  icon: NavIconName;
  title: string;
  description: string;
  value: ReactNode;
  flag?: { label: string; tone: "attention" | "critical" | "brand" | "info"; icon?: "alert" | "shield" };
  valueTone?: "ink" | "brand" | "info";
}) {
  return (
    <Link
      href={href}
      className="group relative flex h-full min-h-0 flex-col justify-between overflow-hidden rounded-md border border-line bg-paper px-5 py-4 transition-[border-color,box-shadow] hover:border-ink/25 hover:shadow-raised focus-visible:border-brand [@media(min-width:1024px)_and_(max-height:820px)]:py-3"
    >
      <div className="flex items-start justify-between">
        <span aria-hidden="true" className="flex size-9 items-center justify-center rounded-sm bg-brand-tint text-brand [@media(min-width:1024px)_and_(max-height:820px)]:size-8">
          <NavIcon name={icon} className="size-[18px]" />
        </span>
        <ArrowUpRight className="size-4 text-faint transition-colors group-hover:text-ink" aria-hidden="true" />
      </div>
      <div className="mt-3 flex items-end justify-between gap-3 [@media(min-width:1024px)_and_(max-height:820px)]:mt-2">
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
          <span className={cn("num text-[30px] leading-none font-semibold tracking-[-0.03em] [@media(min-width:1024px)_and_(max-height:820px)]:text-[26px]", valueTone === "brand" ? "text-brand" : valueTone === "info" ? "text-info" : "text-ink")}>
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

/** The highest-priority finding still awaiting a decision. */
export function NextReviewCard({ findings }: { findings: FindingRowData[] }) {
  const [next] = useAwaiting(findings);
  if (!next) {
    return (
      <div className="flex items-center gap-3 rounded-md border border-line bg-paper px-4 py-3">
        <span className="flex size-10 shrink-0 items-center justify-center rounded-sm bg-sunken text-muted">
          <Gavel className="size-4" aria-hidden="true" />
        </span>
        <div>
          <p className="label">Next review</p>
          <p className="text-[13.5px] text-ink">Every finding has a decision.</p>
        </div>
      </div>
    );
  }
  return (
    <Link
      href={`/workbench/findings/${next.id}`}
      className="group flex max-w-[26rem] items-center gap-3.5 rounded-md border border-line bg-paper px-4 py-3 transition-[border-color,box-shadow] hover:border-ink/25 hover:shadow-raised"
    >
      <span aria-hidden="true" className="flex size-10 shrink-0 items-center justify-center rounded-sm bg-brand text-white">
        <ArrowRight className="size-4" />
      </span>
      <span className="min-w-0">
        <span className="flex items-center gap-2">
          <span className="label">Next review</span>
          {next.severity && (
            <Tag tone={next.severity === "high" ? "attention" : next.severity === "medium" ? "info" : "neutral"}>{next.severity}</Tag>
          )}
        </span>
        <span className="mt-1 block truncate text-[14px] font-semibold text-ink">{next.entityName}</span>
        <span className="block truncate text-[12.5px] text-muted">
          {FAMILY_LABEL[next.family]} · {ruleTitle(next.ruleOrCategory)}
        </span>
      </span>
      <ChevronRight className="size-4 shrink-0 text-faint group-hover:text-ink" aria-hidden="true" />
    </Link>
  );
}

const SOP: Array<{ n: string; title: string; detail: string; href: string; icon: LucideIcon; progress?: boolean }> = [
  { n: "01", title: "Triage attention", detail: "Start with the highest-risk entities", href: "/workbench/entities", icon: Crosshair },
  { n: "02", title: "Inspect evidence", detail: "Read the signals behind each score", href: "/workbench/findings", icon: FileSearch },
  { n: "03", title: "Record decision", detail: "Confirm, reject or escalate", href: "/workbench/review-queue", icon: Gavel, progress: true },
  { n: "04", title: "Verify and report", detail: "Check the ledger, export the report", href: "/workbench/trust", icon: ShieldCheck },
];

/** Standard operating procedure for a review cycle, with real decision progress. */
export function SopCard({ findings, backendDecided, verifyHref }: { findings: FindingRowData[]; backendDecided: number; verifyHref: string }) {
  const { decisions } = useReviewStore();
  const total = findings.length;
  const decided = Math.min(total, backendDecided + new Set(decisions.map((d) => d.findingId).filter((id) => findings.some((f) => f.id === id))).size);
  return (
    <ol className="mt-1 flex min-h-0 flex-1 flex-col" aria-label="Review cycle">
      {SOP.map((s) => (
        <li key={s.n} className="flex min-h-0 flex-1 border-b border-line/80 last:border-0">
          <Link href={s.n === "04" ? verifyHref : s.href} className="group -mx-2 grid w-full grid-cols-[1.75rem_2.25rem_minmax(0,1fr)_auto] items-center gap-3 rounded-sm px-2 py-1.5 hover:bg-canvas/80">
            <span className="font-mono text-[11.5px] text-faint">{s.n}</span>
            <span aria-hidden="true" className="flex size-8 items-center justify-center rounded-sm border border-line bg-canvas text-muted group-hover:text-ink">
              <s.icon className="size-4" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-[14px] font-medium text-ink">{s.title}</span>
              <span className="block truncate text-[12.5px] text-muted">{s.detail}</span>
            </span>
            {s.progress ? (
              <span className="flex items-center gap-2" title={`${decided} of ${total} findings decided`}>
                <span className="h-1.5 w-16 overflow-hidden rounded-[1px] bg-sunken">
                  <span className="block h-full bg-brand" style={{ width: `${total ? (decided / total) * 100 : 0}%` }} />
                </span>
                <span className="num font-mono text-[11.5px] text-ink-2">
                  {decided}/{total}
                </span>
              </span>
            ) : (
              <ChevronRight className="size-4 text-faint group-hover:text-ink" aria-hidden="true" />
            )}
          </Link>
        </li>
      ))}
    </ol>
  );
}
