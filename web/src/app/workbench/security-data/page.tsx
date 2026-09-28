import type { Metadata } from "next";
import Link from "next/link";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { DataTable } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { offsetOf, Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/states";
import { api, orNull } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import { EVIDENCE_CATEGORIES, type CanonicalRecord, type EvidenceCategory } from "@/lib/api/types";
import { shortDigest } from "@/lib/domain/format";
import { CATEGORY_LABEL } from "@/lib/domain/labels";
import { entityName, loadPortfolio } from "@/lib/workbench/data";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Security data" };

const cell = (v: unknown) => (v === null || v === undefined || v === "" ? "" : typeof v === "object" ? JSON.stringify(v) : String(v));

export default async function SecurityDataPage({ searchParams }: { searchParams: Promise<{ version?: string; category?: string; offset?: string }> }) {
  const sp = await searchParams;
  const category = (EVIDENCE_CATEGORIES as readonly string[]).includes(sp.category ?? "") ? (sp.category as EvidenceCategory) : "alerts";
  const offset = offsetOf(sp.offset);

  const loaded = await load(async () => {
    const portfolio = await loadPortfolio();
    const current = await Promise.all(portfolio.priorities.map(async (p) => ({ priority: p, run: await api.run(p.run_id) })));
    const version = sp.version ?? current[0]?.run.submission_version_id ?? null;
    const [page, summary] = version ? await Promise.all([api.records(version, { category, offset, limit: 50 }), orNull(api.summary(version))]) : [null, null];
    return { portfolio, current, version, page, summary };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Data"
        title="Security data"
        description="Canonical records of a validated submission version, exactly as the SAT-SA service stored them after validation. Findings cite these records by source record ID."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Security data" />
      ) : !loaded.data.version ? (
        <EmptyState title="No analysed submission yet">Records are listed for submission versions that have been validated and analysed.</EmptyState>
      ) : (
        (() => {
          const { current, version, page, summary, portfolio } = loaded.data;
          const rows = page?.items ?? [];
          const keys = [...new Set(rows.flatMap((r) => Object.keys(r.payload)))].filter((k) => !["entity_id", "assessment_id", "submission_id", "source_record_ref"].includes(k)).slice(0, 6);
          const href = (c: EvidenceCategory, v = version) => `/workbench/security-data?version=${encodeURIComponent(v)}&category=${c}`;
          return (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-1.5">
                <span className="label mr-1">Version</span>
                {current.map(({ priority, run }) => (
                  <Link
                    key={run.id}
                    href={href(category, run.submission_version_id)}
                    aria-current={run.submission_version_id === version ? "page" : undefined}
                    className={cn(
                      "rounded-sm border px-2.5 py-1 text-[12.5px]",
                      run.submission_version_id === version ? "border-brand bg-brand-tint text-brand-strong" : "border-line bg-paper text-ink-2 hover:border-ink/40",
                    )}
                  >
                    {entityName(portfolio, priority.entity_id)}
                  </Link>
                ))}
                {!current.some((c) => c.run.submission_version_id === version) && <span className="mono-id">{version}</span>}
              </div>
              <nav aria-label="Evidence category" className="mb-4 flex flex-wrap gap-1.5">
                {EVIDENCE_CATEGORIES.map((c) => (
                  <Link
                    key={c}
                    href={href(c)}
                    aria-current={c === category ? "page" : undefined}
                    className={cn("rounded-sm border px-2.5 py-1 text-[12.5px]", c === category ? "border-ink bg-ink text-white" : "border-line bg-paper text-ink-2 hover:border-ink/40")}
                  >
                    {CATEGORY_LABEL[c] ?? c} <span className="num opacity-70">{summary?.counts[c] ?? 0}</span>
                  </Link>
                ))}
              </nav>
              {page && (
                <>
                  <DataTable
                    caption={`${CATEGORY_LABEL[category]} records`}
                    rows={rows}
                    rowKey={(r) => r.record_id}
                    dense
                    empty={<EmptyState title={`No ${(CATEGORY_LABEL[category] ?? category).toLowerCase()} in this version`} />}
                    columns={[
                      { key: "locator", header: "Locator", cell: (r: CanonicalRecord) => <span className="mono-id">{r.locator}</span> },
                      ...keys.map((k) => ({ key: k, header: k, cell: (r: CanonicalRecord) => <span className="block max-w-[14rem] truncate">{cell(r.payload[k])}</span> })),
                      { key: "digest", header: "Digest", cell: (r: CanonicalRecord) => <span className="mono-id">{shortDigest(r.content_digest)}</span> },
                    ]}
                  />
                  <Pager page={page} path="/workbench/security-data" params={{ version, category }} label="Record pages" />
                </>
              )}
            </>
          );
        })()
      )}
    </div>
  );
}
