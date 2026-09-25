"use client";

import { FlaskConical } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data";
import { fmtDateTime, shortDigest } from "@/lib/domain/format";
import { BACKEND_ACTION_LABEL } from "@/lib/domain/review";
import { useReviewStore } from "@/lib/review-store";

/** Development-session decisions (fixture mode). Never presented as backend records. */
export function DevDecisions({ titles }: { titles: Record<string, { title: string; entity: string }> }) {
  const { decisions, clear } = useReviewStore();
  if (!decisions.length) return null;
  return (
    <section aria-labelledby="dev-dec-h" className="mt-8 rounded-md border border-attention/30 bg-paper">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-attention/20 bg-attention-tint/50 px-5 py-3">
        <h2 id="dev-dec-h" className="flex items-center gap-2 text-[14px] font-semibold text-ink">
          <FlaskConical className="size-4 text-attention" aria-hidden="true" />
          Development session decisions
          <span className="num font-normal text-muted">{decisions.length}</span>
        </h2>
        <Button variant="ghost" size="sm" onClick={clear}>
          Clear from this browser
        </Button>
      </div>
      <div className="px-5 py-2">
        <DataTable
          caption="Decisions recorded in this browser during a development session"
          rows={[...decisions].reverse()}
          rowKey={(d) => d.id}
          columns={[
            {
              key: "f",
              header: "Finding",
              cell: (d) => (
                <Link href={`/workbench/findings/${d.findingId}`} className="font-medium text-ink hover:text-brand">
                  {titles[d.findingId]?.title ?? d.findingId}
                  <span className="block text-[12px] font-normal text-muted">{titles[d.findingId]?.entity}</span>
                </Link>
              ),
            },
            { key: "a", header: "Decision", cell: (d) => <span className="font-medium text-ink">{BACKEND_ACTION_LABEL[d.action]}</span> },
            { key: "r", header: "Rationale", cell: (d) => <span className="line-clamp-2">{d.reason}</span> },
            { key: "b", header: "Bound digest", cell: (d) => <span className="font-mono text-[12px]">{shortDigest(d.findingContentDigest)}</span> },
            { key: "t", header: "Recorded", cell: (d) => <span className="text-[12px] whitespace-nowrap">{fmtDateTime(d.occurredAt)}</span> },
          ]}
        />
      </div>
    </section>
  );
}
