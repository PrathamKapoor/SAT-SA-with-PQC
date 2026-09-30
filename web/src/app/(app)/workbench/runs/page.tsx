import type { Metadata } from "next";
import Link from "next/link";
import { AutoRefresh } from "@/components/domain/auto-refresh";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { DataTable } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { offsetOf, Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import type { Run, RunStatus } from "@/lib/api/types";
import { fmtDateTime } from "@/lib/domain/format";
import { RUN_IN_PROGRESS, RUN_STATUS } from "@/lib/domain/status";
import { entityName, loadPortfolio } from "@/lib/workbench/data";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Analysis runs" };

const FILTERS: Array<RunStatus | "all"> = ["all", "queued", "running", "awaiting_review", "completed", "partial", "failed", "cancelled"];

export default async function RunsPage({ searchParams }: { searchParams: Promise<{ status?: string; offset?: string }> }) {
  const sp = await searchParams;
  const status = FILTERS.includes(sp.status as RunStatus) && sp.status !== "all" ? (sp.status as RunStatus) : undefined;
  const offset = offsetOf(sp.offset);
  const loaded = await load(async () => {
    const [page, portfolio] = await Promise.all([api.runs({ status, offset, limit: 25 }), loadPortfolio()]);
    return { page, portfolio };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Analysis"
        title="Analysis runs"
        description="Every run the worker has queued, executed or finished for this organization. Status is the persisted backend state; a run stops at review until a supervisor decides."
      />
      <nav aria-label="Filter by status" className="mb-4 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => {
          const active = (f === "all" && !status) || f === status;
          return (
            <Link
              key={f}
              href={f === "all" ? "/workbench/runs" : `/workbench/runs?status=${f}`}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-sm border px-2.5 py-1 text-[12.5px]",
                active ? "border-brand bg-brand-tint text-brand-strong" : "border-line bg-paper text-ink-2 hover:border-ink/40",
              )}
            >
              {f === "all" ? "All" : RUN_STATUS[f].label}
            </Link>
          );
        })}
      </nav>
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Analysis runs" />
      ) : (
        <>
          <AutoRefresh active={loaded.data.page.items.some((r) => RUN_IN_PROGRESS.includes(r.status))} label="Some runs are still processing." />
          <DataTable
            caption="Analysis runs"
            rows={loaded.data.page.items}
            rowKey={(r) => r.id}
            empty={<EmptyState title={status ? `No ${RUN_STATUS[status].label.toLowerCase()} runs` : "No analysis runs yet"}>Runs start from a validated submission on the Ingest page.</EmptyState>}
            columns={[
              {
                key: "entity",
                header: "Entity",
                cell: (r: Run) => (
                  <Link href={`/workbench/runs/${r.id}`} className="font-medium text-ink hover:text-brand-strong">
                    {entityName(loaded.data.portfolio, r.entity_id)}
                  </Link>
                ),
              },
              { key: "status", header: "Status", cell: (r: Run) => <Tag tone={RUN_STATUS[r.status].tone}>{RUN_STATUS[r.status].label}</Tag> },
              { key: "stage", header: "Stage", cell: (r: Run) => r.current_stage },
              { key: "progress", header: "Stages", cell: (r: Run) => <span className="num">{r.progress_completed}/{r.progress_total}</span>, align: "right" },
              { key: "mode", header: "Orchestration", cell: (r: Run) => (r.execution_mode === "graph" ? "LangGraph" : "Standard") },
              { key: "requested", header: "Requested", cell: (r: Run) => fmtDateTime(r.requested_at) },
              { key: "id", header: "Run", cell: (r: Run) => <span className="mono-id">{r.id}</span> },
            ]}
          />
          <Pager page={loaded.data.page} path="/workbench/runs" params={{ status }} label="Analysis run pages" />
        </>
      )}
    </div>
  );
}
