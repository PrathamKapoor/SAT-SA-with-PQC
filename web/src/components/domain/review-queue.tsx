"use client";

import { ArrowUpRight, Paperclip } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { FamilyLabel, ReviewStatusTag, SeverityMark } from "@/components/ui/badges";
import { buttonClass } from "@/components/ui/button";
import { ConfidenceInline, Meter } from "@/components/ui/data";
import { EmptyState } from "@/components/ui/states";
import { fmtNum, fmtPct } from "@/lib/domain/format";
import { RECOMMENDATION_LABEL, ruleTitle } from "@/lib/domain/labels";
import { STATUS_FOR_ACTION } from "@/lib/domain/review";
import { useReviewStore } from "@/lib/review-store";
import type { ReviewDecision } from "@/lib/types/domain";
import { cn } from "@/lib/utils";
import type { FindingRowData } from "./finding-row";
import { ReviewPanel } from "./review-panel";

export type QueueItem = FindingRowData & { contentDigest: string; limitations: string; history: ReviewDecision[] };

export function ReviewQueue({
  items,
  canRecord,
  roleLabel,
  sessionMode,
}: {
  items: QueueItem[];
  canRecord: boolean;
  roleLabel: string;
  sessionMode: "development" | "backend";
}) {
  const { decisions, latestFor } = useReviewStore();
  const devDecided = useMemo(() => new Set(decisions.map((d) => d.findingId)), [decisions]);
  const awaiting = items.filter((i) => i.reviewStatus === "awaiting" && !devDecided.has(i.id));
  const decided = items.filter((i) => i.reviewStatus !== "awaiting" || devDecided.has(i.id));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = items.find((i) => i.id === selectedId) ?? awaiting[0] ?? null;
  const maxPriority = Math.max(...items.map((i) => i.priorityScore ?? 0), 1);

  const row = (i: QueueItem, idx: number, done: boolean) => {
    const dev = latestFor(i.id);
    const status = i.reviewStatus !== "awaiting" ? i.reviewStatus : dev ? STATUS_FOR_ACTION[dev.action] : "awaiting";
    const active = selected?.id === i.id;
    return (
      <li key={i.id}>
        <button
          type="button"
          onClick={() => setSelectedId(i.id)}
          aria-current={active ? "true" : undefined}
          className={cn(
            "grid w-full grid-cols-[1.75rem_minmax(0,1fr)_auto] items-start gap-3 border-b border-line/80 px-4 py-3 text-left transition-colors",
            active ? "bg-brand-tint/60 shadow-[inset_3px_0_0] shadow-brand" : "hover:bg-canvas",
            done && "opacity-70",
          )}
        >
          <span className="num pt-0.5 text-[12px] text-faint">{String(idx + 1).padStart(2, "0")}</span>
          <span className="min-w-0">
            <span className="block truncate text-[13.5px] font-medium text-ink">{ruleTitle(i.ruleOrCategory)}</span>
            <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-muted">
              <span className="font-medium text-ink-2">{i.entityName}</span>
              <span className="inline-flex items-center gap-1">
                <Paperclip className="size-3" aria-hidden="true" />
                <span className="num">{i.evidenceCount}</span>
                <span className="sr-only">evidence records</span>
              </span>
              <span className="num">{fmtPct(i.confidence?.overall ?? null)} conf.</span>
            </span>
          </span>
          <span className="flex flex-col items-end gap-1.5">
            {done && <ReviewStatusTag status={status} />}
            <span className="flex items-center gap-1.5" title={`Priority score ${fmtNum(i.priorityScore ?? null, 1)}`}>
              <SeverityMark severity={i.severity} />
            </span>
          </span>
        </button>
      </li>
    );
  };

  if (!items.length) return <EmptyState title="Nothing to review">No signal findings in the current period.</EmptyState>;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
      <section aria-labelledby="q-h" className="overflow-hidden rounded-md border border-line bg-paper lg:sticky lg:top-6 lg:max-h-[calc(100dvh-8.5rem)] lg:overflow-y-auto">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-paper px-4 py-3">
          <h2 id="q-h" className="text-[13.5px] font-semibold text-ink">
            Awaiting decision <span className="num ml-1 text-muted">{awaiting.length}</span>
          </h2>
          <span className="label">By priority</span>
        </div>
        {awaiting.length ? (
          <ol aria-label="Findings awaiting decision">{awaiting.map((i, idx) => row(i, idx, false))}</ol>
        ) : (
          <p className="px-4 py-6 text-[13px] text-muted">Every finding in this period has a decision.</p>
        )}
        {decided.length > 0 && (
          <>
            <h3 className="label border-b border-line bg-canvas px-4 py-2">Decided ({decided.length})</h3>
            <ol aria-label="Decided findings">{decided.map((i, idx) => row(i, idx, true))}</ol>
          </>
        )}
      </section>

      {selected ? (
        <div key={selected.id} className="min-w-0 animate-rise space-y-5">
          <article aria-labelledby="sel-h" className="rounded-md border border-line bg-paper px-5 py-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <FamilyLabel family={selected.family} />
              <Link href={`/workbench/findings/${selected.id}`} className={buttonClass("secondary", "sm")}>
                Full investigation
                <ArrowUpRight className="size-3.5" aria-hidden="true" />
              </Link>
            </div>
            <h2 id="sel-h" className="mt-3 text-[22px] leading-snug font-semibold tracking-[-0.02em] text-ink">
              {ruleTitle(selected.ruleOrCategory)}
            </h2>
            <p className="mt-1 text-[13px] text-muted">{selected.entityName}</p>
            <p className="mt-4 text-[15px] leading-relaxed text-ink">{selected.rationale}</p>
            {selected.limitations && <p className="mt-3 text-[12.5px] leading-relaxed text-muted">{selected.limitations}</p>}

            <dl className="mt-5 grid grid-cols-2 gap-5 border-t border-line pt-4 sm:grid-cols-4">
              <div>
                <dt className="label">Importance</dt>
                <dd className="mt-1.5 space-y-1.5">
                  <SeverityMark severity={selected.severity} />
                  <Meter value={selected.priorityScore} max={maxPriority} tone="attention" label="Priority relative to this queue" />
                </dd>
              </div>
              <div>
                <dt className="label">Evidence</dt>
                <dd className="num mt-1 text-[20px] font-semibold text-ink">{selected.evidenceCount}</dd>
              </div>
              <div>
                <dt className="label">Confidence</dt>
                <dd className="mt-1.5">
                  <ConfidenceInline confidence={selected.confidence} />
                </dd>
              </div>
              <div>
                <dt className="label">Next step</dt>
                <dd className="mt-1 text-[13px] font-medium text-attention-strong">
                  {selected.recommendation ? RECOMMENDATION_LABEL[selected.recommendation.action] : "Review"}
                </dd>
              </div>
            </dl>
          </article>
          <ReviewPanel
            findingId={selected.id}
            contentDigest={selected.contentDigest}
            canRecord={canRecord}
            roleLabel={roleLabel}
            sessionMode={sessionMode}
            history={selected.history}
          />
        </div>
      ) : (
        <EmptyState title="Select a finding" />
      )}
    </div>
  );
}
