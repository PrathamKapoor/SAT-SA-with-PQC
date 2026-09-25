import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";
import { TrustTag } from "@/components/ui/badges";
import { PageHeader } from "@/components/ui/layout";
import { fmtNum, fmtPeriod } from "@/lib/domain/format";
import { loadEntityViews } from "@/lib/model";

export const metadata: Metadata = { title: "Reports" };

export default async function ReportsPage() {
  const entities = await loadEntityViews();
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Intelligence"
        title="Reports"
        description="One supervisory report per entity and assessment period: findings, evidence, risk, recommendations, decisions and trust verification, ready to print."
      />
      <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {entities.map((e) => (
          <li key={e.entity.id}>
            <Link href={`/workbench/reports/${e.entity.id}`} className="group flex h-full flex-col rounded-md border border-line bg-paper px-5 py-5 transition-colors hover:border-ink/30">
              <div className="flex items-start justify-between gap-3">
                <FileText className="size-5 text-brand" aria-hidden="true" />
                <TrustTag state={e.trust} />
              </div>
              <p className="mt-4 text-[16px] font-semibold text-ink">{e.entity.displayName}</p>
              <p className="mt-1 text-[12.5px] text-muted">{e.assessment ? fmtPeriod(e.assessment.periodStart, e.assessment.periodEnd) : "No assessment"}</p>
              <dl className="mt-4 flex gap-6 text-[12.5px]">
                <div>
                  <dt className="text-muted">Risk</dt>
                  <dd className="num font-semibold text-ink">{fmtNum(e.risk?.total_score ?? null, 1)}</dd>
                </div>
                <div>
                  <dt className="text-muted">Findings</dt>
                  <dd className="num font-semibold text-ink">{e.findings.length}</dd>
                </div>
              </dl>
              <span className="mt-auto flex items-center gap-1 pt-4 text-[13px] font-medium text-brand group-hover:text-brand-strong">
                Open report <ArrowRight className="size-3.5" aria-hidden="true" />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
