import type { Metadata } from "next";
import Link from "next/link";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { PageHeader, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import { AGENT_LAYER, AGENT_WORKERS } from "@/lib/domain/agents";
import { fmtDateTime } from "@/lib/domain/format";
import { workerLabel } from "@/lib/domain/labels";
import { STEP_STATUS } from "@/lib/domain/status";
import { entityName, loadPortfolio } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Agents" };

const agentTitle = (id: string) =>
  id
    .replace(/^satsa\./, "")
    .split("_")
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");

export default async function AgentsPage() {
  const loaded = await load(async () => {
    const [recent, portfolio] = await Promise.all([api.runs({ limit: 50 }), loadPortfolio()]);
    const run = recent.items.find((r) => ["awaiting_review", "completed", "partial"].includes(r.status)) ?? null;
    return { run, portfolio };
  });

  const layers = ["Ingestion", "Detection", "Assessment", "Trust", "Human authority"] as const;

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Intelligence"
        title="Agents"
        description="The registered SAT-SA agents are deterministic components, not language models. Eleven analytical agents group the sixteen default workers; the rest are pipeline stages. Worker status below is read from the most recent analysed run."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Agents" />
      ) : (
        (() => {
          const { run, portfolio } = loaded.data;
          const steps = new Map((run?.steps ?? []).map((s) => [s.worker_name, s]));
          return (
            <div className="space-y-10">
              <p className="text-[13px] text-muted">
                {run ? (
                  <>
                    Live worker status from the run for{" "}
                    <Link className="text-brand hover:underline" href={`/workbench/runs/${run.id}`}>
                      {entityName(portfolio, run.entity_id)}
                    </Link>{" "}
                    requested {fmtDateTime(run.requested_at)}.
                  </>
                ) : (
                  "No analysed run yet: worker status appears after the first run finishes its analytical stages."
                )}
              </p>
              {layers.map((layer) => {
                const agents = Object.entries(AGENT_LAYER)
                  .filter(([, l]) => l === layer)
                  .map(([id]) => id);
                return (
                  <section key={layer} aria-labelledby={`layer-${layer}`}>
                    <SectionHeader id={`layer-${layer}`} title={layer} aside={`${agents.length} agent${agents.length === 1 ? "" : "s"}`} />
                    <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                      {agents.map((id) => {
                        const workers = AGENT_WORKERS[id] ?? [];
                        return (
                          <li key={id} className="rounded-md border border-line bg-paper px-4 py-3">
                            <p className="text-[14px] font-semibold text-ink">{agentTitle(id)}</p>
                            <p className="mono-id">{id}</p>
                            {workers.length ? (
                              <ul className="mt-2 space-y-1">
                                {workers.map((w) => {
                                  const s = steps.get(w);
                                  return (
                                    <li key={w} className="flex items-center justify-between gap-2 text-[12.5px]">
                                      <span className="text-ink-2">{workerLabel(w)}</span>
                                      {s ? <Tag tone={STEP_STATUS[s.status] ?? "neutral"}>{s.status}</Tag> : <span className="text-faint">not run</span>}
                                    </li>
                                  );
                                })}
                              </ul>
                            ) : (
                              <p className="mt-2 text-[12.5px] text-muted">Pipeline stage: observed through the records it produces.</p>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </section>
                );
              })}
              {!run && <EmptyState title="No worker activity yet" />}
            </div>
          );
        })()
      )}
    </div>
  );
}
