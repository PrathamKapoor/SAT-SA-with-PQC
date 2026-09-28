import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Upload } from "lucide-react";
import { CompletenessStrip } from "@/components/domain/entity-bits";
import { FindingList } from "@/components/domain/finding-list";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { ButtonLink } from "@/components/ui/button";
import { DataTable, RiskBreakdown, RiskScore } from "@/components/ui/data";
import { KeyValue, PageHeader, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api, orNull } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import type { Assessment, Run, Submission } from "@/lib/api/types";
import { can } from "@/lib/auth/permissions";
import { fmtDateTime, fmtNum, fmtPeriod } from "@/lib/domain/format";
import { RUN_STATUS } from "@/lib/domain/status";
import { bySignalThenConfidence, loadPortfolio, loadRunFindings } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Entity" };

export default async function EntityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ctx = await requireContext();
  const loaded = await load(async () => {
    const [entity, assessments, submissions, runs, portfolio] = await Promise.all([
      api.entity(id),
      all((q) => api.assessments({ ...q, entity_id: id })),
      all((q) => api.submissions({ ...q, entity_id: id })),
      api.runs({ entity_id: id, limit: 20 }),
      loadPortfolio(),
    ]);
    const priority = portfolio.priority.get(id) ?? null;
    const current = priority ? await api.run(priority.run_id) : null;
    const [risk, findings, counts] = current
      ? await Promise.all([orNull(api.risk(current.id)), loadRunFindings(current.id), orNull(api.summary(current.submission_version_id))])
      : [null, [], null];
    return { entity, assessments, submissions, runs, priority, rank: portfolio.rank.get(id) ?? null, current, risk, findings, counts };
  });

  if (!loaded.ok) {
    return (
      <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
        <ApiErrorPanel error={loaded.error} context="Entity" />
      </div>
    );
  }
  const d = loaded.data;
  const signals = d.findings.filter((f) => f.state === "signal").sort(bySignalThenConfidence);

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <Link href="/workbench/entities" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        Entities
      </Link>
      <PageHeader
        eyebrow={d.rank ? `Priority rank ${d.rank}` : "Not yet ranked"}
        title={d.entity.display_name}
        description={`${d.entity.sector || "Unspecified sector"} · ${d.entity.environment_class || "unspecified environment"}`}
        actions={
          can(ctx.role, "analysis.run") ? (
            <ButtonLink href={`/workbench/ingest?entity=${d.entity.id}`} variant="primary">
              <Upload className="size-4" aria-hidden="true" />
              Ingest evidence
            </ButtonLink>
          ) : undefined
        }
      />

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-8">
          <section aria-labelledby="risk-h">
            <SectionHeader id="risk-h" title="Current risk" aside={d.current ? <Link className="text-brand hover:underline" href={`/workbench/runs/${d.current.id}`}>Open run</Link> : undefined} />
            {d.risk ? (
              <div className="grid gap-6 rounded-md border border-line bg-paper p-5 md:grid-cols-[11rem_minmax(0,1fr)]">
                <div>
                  <RiskScore score={d.risk.profile.total_score} bucket={d.risk.profile.confidence_bucket} size="lg" />
                  {d.priority && (
                    <p className="mt-3 text-[12.5px] text-muted">
                      Priority score <span className="num text-ink">{fmtNum(d.priority.priority_score, 1)}</span>
                    </p>
                  )}
                </div>
                <RiskBreakdown dimensions={d.risk.profile.dimensions} />
              </div>
            ) : (
              <EmptyState title="No analysed run yet">Risk appears once a run for this entity finishes its analytical stages.</EmptyState>
            )}
            {d.priority && <p className="mt-2 text-[12.5px] text-muted">{d.priority.rationale}</p>}
          </section>

          <section aria-labelledby="findings-h">
            <SectionHeader id="findings-h" title="Signal findings in the current run" aside={`${signals.length} of ${d.findings.length}`} />
            <FindingList findings={signals} empty="No signal findings in the current run" />
          </section>

          <section aria-labelledby="runs-h">
            <SectionHeader id="runs-h" title="Analysis runs" />
            <DataTable
              caption="Analysis runs for this entity"
              rows={d.runs.items}
              rowKey={(r) => r.id}
              empty={<EmptyState title="No runs yet" />}
              columns={[
                { key: "run", header: "Run", cell: (r: Run) => <Link className="mono-id hover:text-brand-strong" href={`/workbench/runs/${r.id}`}>{r.id}</Link> },
                { key: "status", header: "Status", cell: (r: Run) => <Tag tone={RUN_STATUS[r.status].tone}>{RUN_STATUS[r.status].label}</Tag> },
                { key: "requested", header: "Requested", cell: (r: Run) => fmtDateTime(r.requested_at) },
              ]}
            />
            {d.runs.has_more && (
              <Link href={`/workbench/runs?entity=${d.entity.id}`} className="mt-2 inline-block text-[12.5px] text-brand hover:underline">
                More runs
              </Link>
            )}
          </section>
        </div>

        <aside className="space-y-8">
          <section aria-labelledby="evidence-h">
            <SectionHeader id="evidence-h" title="Evidence in the current run" />
            <CompletenessStrip counts={d.counts?.counts ?? null} showLabels />
          </section>
          <section aria-labelledby="periods-h">
            <SectionHeader id="periods-h" title="Assessment periods" />
            {d.assessments.length ? (
              <ul className="space-y-2">
                {d.assessments.map((a: Assessment) => (
                  <li key={a.id} className="flex items-center justify-between gap-2 text-[13px]">
                    <span className="text-ink">{fmtPeriod(a.period_start, a.period_end)}</span>
                    <Tag tone={a.status === "open" ? "info" : "neutral"}>{a.status}</Tag>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState title="No assessment periods" />
            )}
          </section>
          <section aria-labelledby="subs-h">
            <SectionHeader id="subs-h" title="Submissions" />
            {d.submissions.length ? (
              <KeyValue
                columns={1}
                items={d.submissions.map((s: Submission) => [
                  <span key="k" className="mono-id">{s.id}</span>,
                  <span key="v">
                    {s.ingest_status} · {fmtDateTime(s.created_at)}
                  </span>,
                ])}
              />
            ) : (
              <EmptyState title="No submissions" />
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
