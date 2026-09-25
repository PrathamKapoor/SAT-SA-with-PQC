import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { CompletenessStrip, RiskSignature } from "@/components/domain/entity-bits";
import { TrustTag } from "@/components/ui/badges";
import { RiskScore } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { DIMENSION_LABEL } from "@/lib/domain/labels";
import { loadEntityViews } from "@/lib/model";

export const metadata: Metadata = { title: "Entities" };

export default async function EntitiesPage() {
  const entities = await loadEntityViews();
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Supervision"
        title="Entities"
        description="Constituent security entities in the current assessment period, in the backend's priority order. Risk is a weighted sum across seven dimensions, each capped at its weight."
      />
      {entities.length === 0 ? (
        <EmptyState title="No entities registered">Entities appear here once a CSE submission has been ingested.</EmptyState>
      ) : (
        <div className="overflow-hidden rounded-md border border-line bg-paper">
          <div className="hidden grid-cols-[2.5rem_minmax(0,1.4fr)_9rem_8.5rem_minmax(0,1fr)_7rem_1rem] gap-x-5 border-b border-line bg-canvas px-5 py-2 lg:grid" aria-hidden="true">
            {["Rank", "Entity", "Risk", "Signature", "Attention areas", "Evidence", ""].map((h) => (
              <span key={h} className="label">
                {h}
              </span>
            ))}
          </div>
          <ul aria-label="Entities by priority">
            {entities.map((e) => {
              const top = (e.risk?.dimensions ?? []).filter((d) => d.score > 0).sort((a, b) => b.score - a.score).slice(0, 3);
              return (
                <li key={e.entity.id} className="border-b border-line last:border-0">
                  <Link
                    href={`/workbench/entities/${e.entity.id}`}
                    className="group grid grid-cols-1 gap-x-5 gap-y-3 px-5 py-4 hover:bg-canvas lg:grid-cols-[2.5rem_minmax(0,1.4fr)_9rem_8.5rem_minmax(0,1fr)_7rem_1rem] lg:items-center"
                  >
                    <span className="num text-[13px] text-faint">{String(e.priorityRank ?? "").padStart(2, "0")}</span>
                    <span className="min-w-0">
                      <span className="block truncate text-[15px] font-semibold text-ink group-hover:text-brand-strong">{e.entity.displayName}</span>
                      <span className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[12.5px] text-muted">
                        <span className="capitalize">{e.entity.sector || "Unspecified sector"}</span>
                        <span aria-hidden="true">·</span>
                        <span>{e.entity.environmentClass || "unspecified environment"}</span>
                        <span aria-hidden="true">·</span>
                        <span>
                          <span className="num">{e.findings.length}</span> finding{e.findings.length === 1 ? "" : "s"}
                        </span>
                      </span>
                    </span>
                    <RiskScore score={e.risk?.total_score ?? null} size="sm" bucket={e.risk?.confidence_bucket} />
                    <RiskSignature dimensions={e.risk?.dimensions ?? []} />
                    <span className="min-w-0 text-[12.5px] text-ink-2">{top.length ? top.map((d) => DIMENSION_LABEL[d.name]).join(", ") : <span className="text-muted">None weighted</span>}</span>
                    <span className="flex flex-col gap-1.5">
                      <CompletenessStrip submission={e.submission} />
                      {e.trust !== "verified" && <TrustTag state={e.trust} />}
                    </span>
                    <ChevronRight className="hidden size-4 text-faint group-hover:text-ink lg:block" aria-hidden="true" />
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <p className="mt-3 text-[12px] text-muted">
        Signature shows the seven dimensions left to right: execution gap, peer deviation, detection gap, negative space, anomaly, investigation quality, escalation discipline.
        Evidence squares are the six submission categories; a dashed square is a category that was not submitted.
      </p>
    </div>
  );
}
