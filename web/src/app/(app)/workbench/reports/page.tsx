import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight, FileText } from "lucide-react";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { RiskScore } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { load } from "@/lib/api/guard";
import { RUN_STATUS } from "@/lib/domain/status";
import { entityName, loadPortfolio } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Reports" };

export default async function ReportsPage() {
  const loaded = await load(() => loadPortfolio());
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Intelligence"
        title="Reports"
        description="A printable supervisory report per entity, assembled from its current run: risk, signal findings with their evidence counts, recommendations, the supervisor's decision and the TRUST-SAT receipt."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Reports" />
      ) : loaded.data.priorities.length === 0 ? (
        <EmptyState title="No reports yet">A report becomes available when an entity has an analysed run.</EmptyState>
      ) : (
        <ul className="overflow-hidden rounded-md border border-line bg-paper">
          {loaded.data.priorities.map((p) => (
            <li key={p.entity_id} className="border-b border-line last:border-0">
              <Link href={`/workbench/reports/${p.entity_id}`} className="group grid grid-cols-[1.5rem_minmax(0,1fr)_8rem_8.5rem_1rem] items-center gap-4 px-5 py-3 hover:bg-canvas">
                <FileText className="size-4 text-muted" aria-hidden="true" />
                <span className="truncate text-[14px] font-medium text-ink group-hover:text-brand-strong">{entityName(loaded.data, p.entity_id)}</span>
                <RiskScore score={p.risk_score} size="sm" />
                <Tag tone={RUN_STATUS[p.run_status].tone}>{RUN_STATUS[p.run_status].label}</Tag>
                <ChevronRight className="size-4 text-faint group-hover:text-ink" aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
