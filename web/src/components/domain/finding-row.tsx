import { ChevronRight, Paperclip } from "lucide-react";
import Link from "next/link";
import { FamilyLabel, ReviewStatusTag, SeverityMark, TrustTag } from "@/components/ui/badges";
import { ConfidenceInline } from "@/components/ui/data";
import { RECOMMENDATION_LABEL, ruleTitle } from "@/lib/domain/labels";
import type { FindingView } from "@/lib/model";
import { cn } from "@/lib/utils";

/** Serializable subset passed to client lists. */
export type FindingRowData = Pick<
  FindingView,
  | "id"
  | "ruleOrCategory"
  | "family"
  | "entityName"
  | "entityId"
  | "severity"
  | "confidence"
  | "evidenceCount"
  | "reviewStatus"
  | "trust"
  | "recommendation"
  | "priorityScore"
  | "rationale"
  | "createdAt"
  | "riskDimension"
  | "workerName"
>;

export function toRowData(f: FindingView): FindingRowData {
  return {
    id: f.id,
    ruleOrCategory: f.ruleOrCategory,
    family: f.family,
    entityName: f.entityName,
    entityId: f.entityId,
    severity: f.severity,
    confidence: f.confidence,
    evidenceCount: f.evidenceCount,
    reviewStatus: f.reviewStatus,
    trust: f.trust,
    recommendation: f.recommendation,
    priorityScore: f.priorityScore,
    rationale: f.rationale,
    createdAt: f.createdAt,
    riskDimension: f.riskDimension,
    workerName: f.workerName,
  };
}

/** Compact queue row used on the Workbench. */
export function FindingLine({ f, rank }: { f: FindingRowData; rank?: number }) {
  return (
    <Link
      href={`/workbench/findings/${f.id}`}
      className="group relative grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-3 border-b border-line/80 px-4 py-2.5 last:border-0 hover:bg-canvas focus-visible:bg-canvas"
    >
      <span className="num text-[11.5px] text-faint">{rank ? String(rank).padStart(2, "0") : ""}</span>
      <span className="min-w-0">
        <span className="block truncate text-[13.5px] font-medium text-ink group-hover:text-brand-strong">{ruleTitle(f.ruleOrCategory)}</span>
        <span className="mt-0.5 flex min-w-0 items-center gap-2 text-[12px] text-muted">
          <span className="truncate font-medium text-ink-2">{f.entityName}</span>
          <span aria-hidden="true" className="text-line-2">/</span>
          <span className="truncate">{f.recommendation ? RECOMMENDATION_LABEL[f.recommendation.action] : "Review"}</span>
        </span>
      </span>
      <span className="flex items-center gap-3">
        <SeverityMark severity={f.severity} className="max-2xl:hidden" />
        <ConfidenceInline confidence={f.confidence} />
        <ChevronRight className="size-4 text-faint group-hover:text-ink" aria-hidden="true" />
      </span>
    </Link>
  );
}

/** Full row used by the Findings queue: built for scanning dozens quickly. */
export function FindingRow({ f, className }: { f: FindingRowData; className?: string }) {
  return (
    <li className={cn("border-b border-line last:border-0", className)}>
      <Link
        href={`/workbench/findings/${f.id}`}
        className="group relative grid grid-cols-1 gap-x-5 gap-y-2 px-4 py-3.5 hover:bg-canvas focus-visible:bg-canvas md:grid-cols-[6.5rem_minmax(0,1fr)_7.5rem_5rem_9.5rem_1rem] md:items-center"
      >
        <SeverityMark severity={f.severity} />
        <span className="min-w-0">
          <FamilyLabel family={f.family} />
          <span className="mt-1 block truncate text-[14px] font-medium text-ink group-hover:text-brand-strong">{ruleTitle(f.ruleOrCategory)}</span>
          <span className="mt-0.5 block truncate text-[12.5px] text-muted">
            <span className="font-medium text-ink-2">{f.entityName}</span>
            <span aria-hidden="true"> · </span>
            {f.recommendation ? RECOMMENDATION_LABEL[f.recommendation.action] : "Review"}
          </span>
        </span>
        <ConfidenceInline confidence={f.confidence} />
        <span className="inline-flex items-center gap-1 text-[12.5px] text-ink-2">
          <Paperclip className="size-3.5 text-faint" aria-hidden="true" />
          <span className="num">{f.evidenceCount}</span>
          <span className="sr-only">evidence records</span>
        </span>
        <span className="flex flex-wrap items-center gap-1.5">
          <ReviewStatusTag status={f.reviewStatus} />
          {f.trust !== "verified" && <TrustTag state={f.trust} />}
        </span>
        <ChevronRight className="hidden size-4 text-faint group-hover:text-ink md:block" aria-hidden="true" />
      </Link>
    </li>
  );
}
