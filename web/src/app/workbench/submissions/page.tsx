import type { Metadata } from "next";
import Link from "next/link";
import { Upload } from "lucide-react";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { ButtonLink } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { offsetOf, Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/states";
import { all, api, orNull } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import type { Assessment, Submission, Validation, Version } from "@/lib/api/types";
import { can } from "@/lib/auth/permissions";
import { fmtDateTime, fmtPeriod } from "@/lib/domain/format";
import { VERSION_STATUS } from "@/lib/domain/status";
import { entityName, loadPortfolio } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Submissions" };

type Row = { submission: Submission; assessment: Assessment | null; latest: Version | null; versions: number; validation: Validation | null };

export default async function SubmissionsPage({ searchParams }: { searchParams: Promise<{ offset?: string }> }) {
  const ctx = await requireContext();
  const offset = offsetOf((await searchParams).offset);
  const loaded = await load(async () => {
    const [page, portfolio, assessments] = await Promise.all([api.submissions({ offset, limit: 25 }), loadPortfolio(), all((q) => api.assessments(q))]);
    const byId = new Map(assessments.map((a) => [a.id, a]));
    const rows: Row[] = await Promise.all(
      page.items.map(async (submission) => {
        const versions = await all((q) => api.versions(submission.id, q), 400);
        const latest = versions.sort((a, b) => b.version - a.version)[0] ?? null;
        const validated = latest && ["valid", "invalid", "failed"].includes(latest.status);
        return {
          submission,
          assessment: byId.get(submission.assessment_id) ?? null,
          latest,
          versions: versions.length,
          validation: validated ? await orNull(api.validation(latest.id)) : null,
        };
      }),
    );
    return { page, portfolio, rows };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Data"
        title="Submissions"
        description="Evidence submissions per assessment period. Each upload creates an immutable version; validation parses every record and resolves references before any analysis can run."
        actions={
          can(ctx.role, "analysis.run") ? (
            <ButtonLink href="/workbench/ingest" variant="primary">
              <Upload className="size-4" aria-hidden="true" />
              Ingest evidence
            </ButtonLink>
          ) : undefined
        }
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Submissions" />
      ) : (
        <>
          <DataTable
            caption="Submissions"
            rows={loaded.data.rows}
            rowKey={(r) => r.submission.id}
            empty={<EmptyState title="No submissions yet">Submissions are created on the Ingest page.</EmptyState>}
            columns={[
              {
                key: "entity",
                header: "Entity",
                cell: (r: Row) => (
                  <Link href={`/workbench/entities/${r.submission.entity_id}`} className="font-medium text-ink hover:text-brand-strong">
                    {entityName(loaded.data.portfolio, r.submission.entity_id)}
                  </Link>
                ),
              },
              { key: "period", header: "Period", cell: (r: Row) => (r.assessment ? fmtPeriod(r.assessment.period_start, r.assessment.period_end) : "Unknown") },
              {
                key: "status",
                header: "Latest version",
                cell: (r: Row) =>
                  r.latest ? (
                    <span className="inline-flex items-center gap-2">
                      <Tag tone={VERSION_STATUS[r.latest.status].tone}>{VERSION_STATUS[r.latest.status].label}</Tag>
                      <span className="num text-[12px] text-muted">v{r.latest.version}</span>
                    </span>
                  ) : (
                    <span className="text-muted">No version</span>
                  ),
              },
              {
                key: "records",
                header: "Records",
                cell: (r: Row) =>
                  r.validation ? (
                    <span className="num">
                      {r.validation.totals.accepted ?? 0} accepted · {r.validation.totals.rejected ?? 0} rejected
                    </span>
                  ) : (
                    <span className="text-muted">Not validated</span>
                  ),
              },
              {
                key: "data",
                header: "Data",
                cell: (r: Row) =>
                  r.latest?.status === "valid" ? (
                    <Link className="text-brand hover:underline" href={`/workbench/security-data?version=${r.latest.id}`}>
                      Records
                    </Link>
                  ) : null,
              },
              { key: "created", header: "Created", cell: (r: Row) => fmtDateTime(r.submission.created_at) },
            ]}
          />
          <Pager page={loaded.data.page} path="/workbench/submissions" label="Submission pages" />
        </>
      )}
    </div>
  );
}
