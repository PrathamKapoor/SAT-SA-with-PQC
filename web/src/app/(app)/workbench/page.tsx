import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight, ListChecks, Upload } from "lucide-react";
import { AutoRefresh } from "@/components/domain/auto-refresh";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { ButtonLink } from "@/components/ui/button";
import { RiskScore } from "@/components/ui/data";
import { Metric, PageHeader, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import { can, ROLE_LABEL } from "@/lib/auth/permissions";
import { fmtDateTime } from "@/lib/domain/format";
import { DIMENSION_LABEL } from "@/lib/domain/labels";
import { RUN_IN_PROGRESS, RUN_STATUS } from "@/lib/domain/status";
import { entityName, loadCurrentFindings, loadPortfolio } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Workbench" };

export default async function WorkbenchPage() {
  const ctx = await requireContext();
  const loaded = await load(async () => {
    const [portfolio, runs, current] = await Promise.all([loadPortfolio(), all((q) => api.runs(q), 400), loadCurrentFindings()]);
    return { portfolio, runs, current };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow={`${ctx.organization.name} · ${ROLE_LABEL[ctx.role] ?? ctx.role}`}
        title="Workbench"
        description="Supervision state of this organization, read live from the SAT-SA service: what awaits a decision, what is still running, and where risk is highest."
        actions={
          <>
            {can(ctx.role, "analysis.run") && (
              <ButtonLink href="/workbench/ingest" variant="primary">
                <Upload className="size-4" aria-hidden="true" />
                Ingest evidence
              </ButtonLink>
            )}
            <ButtonLink href="/workbench/review-queue">
              <ListChecks className="size-4" aria-hidden="true" />
              Review queue
            </ButtonLink>
          </>
        }
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Workbench" />
      ) : (
        (() => {
          const { portfolio, runs, current } = loaded.data;
          const awaiting = runs.filter((r) => r.status === "awaiting_review");
          const working = runs.filter((r) => RUN_IN_PROGRESS.includes(r.status));
          const signals = current.filter((r) => r.finding.state === "signal").length;
          const recent = [...runs].sort((a, b) => b.requested_at - a.requested_at).slice(0, 6);
          return (
            <>
              <AutoRefresh active={working.length > 0} label={`${working.length} run${working.length === 1 ? " is" : "s are"} processing.`} seconds={5} />
              <dl className="mt-2 mb-8 grid grid-cols-2 gap-6 border-y border-line py-5 md:grid-cols-4">
                <Metric label="Awaiting review" value={awaiting.length} tone={awaiting.length ? "attention" : "ink"} detail="Runs released to a supervisor" />
                <Metric label="In progress" value={working.length} tone={working.length ? "info" : "ink"} detail="Queued or running" />
                <Metric label="Ranked entities" value={`${portfolio.priorities.length}/${portfolio.entities.length}`} detail="With an analysed run" />
                <Metric label="Signal findings" value={signals} tone="brand" detail="In current runs" />
              </dl>

              <div className="grid gap-10 lg:grid-cols-2">
                <section aria-labelledby="priority-h">
                  <SectionHeader id="priority-h" title="Highest priority" aside={<Link className="text-brand hover:underline" href="/workbench/entities">All entities</Link>} />
                  {portfolio.priorities.length === 0 ? (
                    <EmptyState title="No analysed entities yet">Priorities appear once a run finishes its analytical stages.</EmptyState>
                  ) : (
                    <ol className="overflow-hidden rounded-md border border-line bg-paper">
                      {portfolio.priorities.slice(0, 6).map((p, i) => (
                        <li key={p.entity_id} className="border-b border-line last:border-0">
                          <Link href={`/workbench/entities/${p.entity_id}`} className="group grid grid-cols-[2rem_minmax(0,1fr)_7rem_1rem] items-center gap-4 px-4 py-3 hover:bg-canvas">
                            <span className="num text-[13px] text-faint">{String(i + 1).padStart(2, "0")}</span>
                            <span className="min-w-0">
                              <span className="block truncate text-[14px] font-semibold text-ink group-hover:text-brand-strong">{entityName(portfolio, p.entity_id)}</span>
                              <span className="block truncate text-[12px] text-muted">{p.top_dimensions.map((d) => DIMENSION_LABEL[d] ?? d).join(", ") || "No weighted dimension"}</span>
                            </span>
                            <RiskScore score={p.risk_score} size="sm" />
                            <ChevronRight className="size-4 text-faint group-hover:text-ink" aria-hidden="true" />
                          </Link>
                        </li>
                      ))}
                    </ol>
                  )}
                </section>

                <section aria-labelledby="recent-h">
                  <SectionHeader id="recent-h" title="Recent runs" aside={<Link className="text-brand hover:underline" href="/workbench/runs">All runs</Link>} />
                  {recent.length === 0 ? (
                    <EmptyState title="No analysis runs yet">
                      {can(ctx.role, "analysis.run") ? "Ingest and validate a submission, then start a run." : "An analyst starts runs from validated submissions."}
                    </EmptyState>
                  ) : (
                    <ul className="overflow-hidden rounded-md border border-line bg-paper">
                      {recent.map((r) => (
                        <li key={r.id} className="border-b border-line last:border-0">
                          <Link href={`/workbench/runs/${r.id}`} className="group grid grid-cols-[minmax(0,1fr)_8.5rem_1rem] items-center gap-4 px-4 py-3 hover:bg-canvas">
                            <span className="min-w-0">
                              <span className="block truncate text-[14px] font-medium text-ink group-hover:text-brand-strong">{entityName(portfolio, r.entity_id)}</span>
                              <span className="block text-[12px] text-muted">{fmtDateTime(r.requested_at)}</span>
                            </span>
                            <Tag tone={RUN_STATUS[r.status].tone}>{RUN_STATUS[r.status].label}</Tag>
                            <ChevronRight className="size-4 text-faint group-hover:text-ink" aria-hidden="true" />
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>
            </>
          );
        })()
      )}
    </div>
  );
}
