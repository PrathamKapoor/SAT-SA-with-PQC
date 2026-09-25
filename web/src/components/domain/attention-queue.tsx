"use client";

import { ArrowRight, Paperclip } from "lucide-react";
import Link from "next/link";
import { FamilyLabel, SeverityMark } from "@/components/ui/badges";
import { buttonClass } from "@/components/ui/button";
import { ConfidenceInline } from "@/components/ui/data";
import { RECOMMENDATION_LABEL, ruleTitle } from "@/lib/domain/labels";
import { useReviewStore } from "@/lib/review-store";
import { FindingLine, type FindingRowData } from "./finding-row";

/** Hide findings a development-session decision has already been recorded for. */
export function useAwaiting(findings: FindingRowData[]) {
  const { decisions } = useReviewStore();
  const decided = new Set(decisions.map((d) => d.findingId));
  return findings.filter((f) => f.reviewStatus === "awaiting" && !decided.has(f.id));
}

export function AwaitingHeadline({ findings, entities }: { findings: FindingRowData[]; entities: number }) {
  const n = useAwaiting(findings).length;
  return (
    <>
      <span className="num">{n}</span> finding{n === 1 ? "" : "s"} await review across <span className="num">{entities}</span> entities
    </>
  );
}

export function AttentionQueue({ findings, limit }: { findings: FindingRowData[]; limit: number }) {
  const awaiting = useAwaiting(findings);
  const [lead, ...rest] = awaiting;

  if (!lead) {
    return (
      <div className="flex h-full flex-col items-start justify-center gap-2 px-5 py-8">
        <p className="text-[15px] font-medium text-ink">No findings await review.</p>
        <p className="text-[13px] text-muted">Every signal finding in the current period has a recorded decision.</p>
        <Link href="/workbench/decisions" className={buttonClass("secondary", "sm", "mt-2")}>
          Open decisions
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <article aria-labelledby="lead-finding" className="border-b border-line px-5 pt-4 pb-4">
        <div className="flex items-center justify-between gap-3">
          <p className="label text-brand">Highest priority</p>
          <div className="flex items-center gap-3">
            <SeverityMark severity={lead.severity} />
            <ConfidenceInline confidence={lead.confidence} />
          </div>
        </div>
        <FamilyLabel family={lead.family} className="mt-3" />
        <h2 id="lead-finding" className="mt-1 text-[19px] leading-snug font-semibold tracking-[-0.015em] text-ink">
          {ruleTitle(lead.ruleOrCategory)}
          <span className="font-normal whitespace-nowrap text-muted"> at {lead.entityName}</span>
        </h2>
        <p className="mt-1.5 line-clamp-2 text-[13.5px] leading-relaxed text-ink-2">{lead.rationale}</p>
        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2">
          <span className="inline-flex items-center gap-1.5 text-[12.5px] text-muted">
            <Paperclip className="size-3.5" aria-hidden="true" />
            <span className="num font-medium text-ink">{lead.evidenceCount}</span> supporting records
          </span>
          {lead.recommendation && (
            <span className="text-[12.5px] text-muted">
              Next: <span className="font-medium text-attention-strong">{RECOMMENDATION_LABEL[lead.recommendation.action]}</span>
            </span>
          )}
          <Link href={`/workbench/findings/${lead.id}`} className={buttonClass("primary", "sm", "ml-auto")}>
            Open investigation
            <ArrowRight className="size-3.5" aria-hidden="true" />
          </Link>
        </div>
      </article>

      <div className="flex items-center justify-between px-5 pt-3 pb-1">
        <h3 className="label">Next in queue</h3>
        <Link href="/workbench/review-queue" className="text-[12.5px] font-medium text-brand hover:text-brand-strong">
          All {awaiting.length} awaiting
        </Link>
      </div>
      <div className="relative min-h-0 flex-1 overflow-hidden [mask-image:linear-gradient(to_bottom,black_calc(100%-2.5rem),transparent)]">
        {rest.slice(0, limit).map((f, i) => (
          <FindingLine key={f.id} f={f} rank={i + 2} />
        ))}
      </div>
    </div>
  );
}
