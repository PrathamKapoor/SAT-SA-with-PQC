import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { RiskSignature } from "@/components/domain/entity-bits";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { RiskScore } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { offsetOf, Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/states";
import { api, orNull } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import { DIMENSION_LABEL } from "@/lib/domain/labels";
import { RUN_STATUS } from "@/lib/domain/status";
import { loadPortfolio } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Entities" };

export default async function EntitiesPage({ searchParams }: { searchParams: Promise<{ offset?: string }> }) {
  const offset = offsetOf((await searchParams).offset);
  const loaded = await load(async () => {
    const [page, portfolio] = await Promise.all([api.entities({ offset, limit: 50 }), loadPortfolio()]);
    const risks = new Map(
      await Promise.all(
        page.items.map(async (e) => {
          const p = portfolio.priority.get(e.id);
          return [e.id, p ? await orNull(api.risk(p.run_id)) : null] as const;
        }),
      ),
    );
    return { page, portfolio, risks };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Supervision"
        title="Entities"
        description="Constituent security entities of this organization. Rank and score come from the backend's priority ranking over each entity's latest analysed run; risk is a weighted sum across seven dimensions, each capped at its weight."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Entities" />
      ) : loaded.data.page.items.length === 0 ? (
        <EmptyState title="No entities registered">Entities are created when evidence is ingested for them on the Ingest page.</EmptyState>
      ) : (
        <>
          <div className="overflow-hidden rounded-md border border-line bg-paper">
            <div className="hidden grid-cols-[3rem_minmax(0,1.4fr)_9rem_8.5rem_minmax(0,1fr)_8rem_1rem] gap-x-5 border-b border-line bg-canvas px-5 py-2 lg:grid" aria-hidden="true">
              {["Rank", "Entity", "Risk", "Signature", "Attention areas", "Current run", ""].map((h) => (
                <span key={h} className="label">
                  {h}
                </span>
              ))}
            </div>
            <ul aria-label="Entities">
              {loaded.data.page.items.map((e) => {
                const p = loaded.data.portfolio.priority.get(e.id);
                const rank = loaded.data.portfolio.rank.get(e.id);
                const risk = loaded.data.risks.get(e.id)?.profile ?? null;
                return (
                  <li key={e.id} className="border-b border-line last:border-0">
                    <Link
                      href={`/workbench/entities/${e.id}`}
                      className="group grid grid-cols-1 gap-x-5 gap-y-3 px-5 py-4 hover:bg-canvas lg:grid-cols-[3rem_minmax(0,1.4fr)_9rem_8.5rem_minmax(0,1fr)_8rem_1rem] lg:items-center"
                    >
                      <span className="num text-[13px] text-faint">{rank ? String(rank).padStart(2, "0") : "n/a"}</span>
                      <span className="min-w-0">
                        <span className="block truncate text-[15px] font-semibold text-ink group-hover:text-brand-strong">{e.display_name}</span>
                        <span className="mt-0.5 block truncate text-[12.5px] text-muted">
                          <span className="capitalize">{e.sector || "Unspecified sector"}</span> · {e.environment_class || "unspecified environment"}
                        </span>
                      </span>
                      <RiskScore score={risk?.total_score ?? null} size="sm" bucket={risk?.confidence_bucket} />
                      {risk ? <RiskSignature dimensions={risk.dimensions} /> : <span className="text-[12px] text-muted">Not analysed</span>}
                      <span className="min-w-0 text-[12.5px] text-ink-2">
                        {p?.top_dimensions.length ? p.top_dimensions.map((d) => DIMENSION_LABEL[d] ?? d).join(", ") : <span className="text-muted">None weighted</span>}
                      </span>
                      <span>{p ? <Tag tone={RUN_STATUS[p.run_status].tone}>{RUN_STATUS[p.run_status].label}</Tag> : <span className="text-[12px] text-muted">No analysed run</span>}</span>
                      <ChevronRight className="hidden size-4 text-faint group-hover:text-ink lg:block" aria-hidden="true" />
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
          <Pager page={loaded.data.page} path="/workbench/entities" label="Entity pages" />
          <p className="mt-3 text-[12px] text-muted">
            Signature shows the seven dimensions left to right: execution gap, peer deviation, detection gap, negative space, anomaly, investigation quality, escalation discipline.
          </p>
        </>
      )}
    </div>
  );
}
