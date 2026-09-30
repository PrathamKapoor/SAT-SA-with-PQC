import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { AutoRefresh } from "@/components/domain/auto-refresh";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { RiskScore } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api, orNull } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import { can } from "@/lib/auth/permissions";
import { fmtDateTime } from "@/lib/domain/format";
import { entityName, loadPortfolio, loadRunFindings } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Review queue" };

export default async function ReviewQueuePage() {
  const ctx = await requireContext();
  const loaded = await load(async () => {
    const [runs, portfolio, running] = await Promise.all([
      all((q) => api.runs({ ...q, status: "awaiting_review" })),
      loadPortfolio(),
      api.runs({ status: "running", limit: 1 }),
    ]);
    const rows = await Promise.all(
      runs.map(async (run) => {
        const [findings, risk] = await Promise.all([loadRunFindings(run.id), orNull(api.risk(run.id))]);
        return { run, signals: findings.filter((f) => f.state === "signal").length, risk };
      }),
    );
    rows.sort((a, b) => (b.risk?.profile.total_score ?? 0) - (a.risk?.profile.total_score ?? 0) || a.run.requested_at - b.run.requested_at);
    return { rows, portfolio, working: running.items.length > 0 };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Supervision"
        title="Review queue"
        description={`Runs the worker released for human review, highest risk first. ${
          can(ctx.role, "review.create") ? "Open a run to inspect its evidence and record the decision." : "A supervisor or organization administrator records the decision."
        }`}
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Review queue" />
      ) : (
        <>
          <AutoRefresh active={loaded.data.working} label="Runs are still processing and may join the queue." />
          {loaded.data.rows.length === 0 ? (
            <EmptyState title="Nothing awaiting review">Runs appear here when their analytical stages finish.</EmptyState>
          ) : (
            <ul aria-label="Runs awaiting review" className="overflow-hidden rounded-md border border-line bg-paper">
              {loaded.data.rows.map(({ run, signals, risk }) => (
                <li key={run.id} className="border-b border-line last:border-0">
                  <Link href={`/workbench/runs/${run.id}`} className="group grid grid-cols-1 gap-x-5 gap-y-2 px-5 py-4 hover:bg-canvas md:grid-cols-[minmax(0,1fr)_9rem_8rem_12rem_1rem] md:items-center">
                    <span className="min-w-0">
                      <span className="block truncate text-[15px] font-semibold text-ink group-hover:text-brand-strong">{entityName(loaded.data.portfolio, run.entity_id)}</span>
                      <span className="mono-id">{run.id}</span>
                    </span>
                    <RiskScore score={risk?.profile.total_score ?? null} bucket={risk?.profile.confidence_bucket} size="sm" />
                    <span className="text-[13px] text-ink-2">
                      <span className="num font-medium text-ink">{signals}</span> signal{signals === 1 ? "" : "s"}
                    </span>
                    <span className="text-[12.5px] text-muted">Ready since {fmtDateTime(run.finished_at ?? run.started_at)}</span>
                    <ChevronRight className="hidden size-4 text-faint group-hover:text-ink md:block" aria-hidden="true" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
