import type { Metadata } from "next";
import Link from "next/link";
import { Gavel, ShieldCheck, ShieldAlert } from "lucide-react";
import { DevDecisions } from "@/components/domain/dev-decisions";
import { DataTable } from "@/components/ui/data";
import { Metric, PageHeader, Panel } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { getSource } from "@/lib/api";
import { fmtDateTime, shortDigest } from "@/lib/domain/format";
import { ruleTitle } from "@/lib/domain/labels";
import { BACKEND_ACTION_LABEL } from "@/lib/domain/review";
import { loadFindingViews } from "@/lib/model";

export const metadata: Metadata = { title: "Decisions" };

export default async function DecisionsPage() {
  const src = getSource();
  const [decisions, findings, audit] = await Promise.all([src.listReviewDecisions(), loadFindingViews(), src.getMetaAudit()]);
  const titles = Object.fromEntries(findings.map((f) => [f.id, { title: ruleTitle(f.ruleOrCategory), entity: f.entityName }]));
  const ledger = audit?.ledger_integrity;
  const counts = decisions.reduce<Record<string, number>>((m, d) => ((m[d.action] = (m[d.action] ?? 0) + 1), m), {});

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Supervision"
        title="Decisions"
        description="The append-only record of human supervisory decisions. Corrections are new entries; history is never rewritten."
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Panel className="px-5 py-5">
          <dl className="grid grid-cols-2 gap-6 sm:grid-cols-4">
            <Metric label="Recorded" value={decisions.length} />
            <Metric label="Confirmed" value={counts.confirm ?? 0} />
            <Metric label="Escalated" value={counts.escalate ?? 0} tone={counts.escalate ? "attention" : "ink"} />
            <Metric label="Rejected" value={counts.dismiss ?? 0} />
          </dl>
        </Panel>
        <Panel className="px-5 py-5">
          <p className="label">Decision ledger</p>
          {ledger ? (
            <>
              <p className={`mt-2 flex items-center gap-2 text-[14px] font-semibold ${ledger.fully_consistent ? "text-brand-strong" : "text-critical"}`}>
                {ledger.fully_consistent ? <ShieldCheck className="size-4" aria-hidden="true" /> : <ShieldAlert className="size-4" aria-hidden="true" />}
                {ledger.fully_consistent ? "Consistent with database" : "Inconsistent"}
              </p>
              <p className="mt-1 text-[12.5px] text-muted">
                {ledger.ledger_entries} ledger entries · {ledger.db_rows} database rows · chain {ledger.chain_ok ? "intact" : "broken"}
              </p>
            </>
          ) : (
            <p className="mt-2 text-[13px] text-muted">Ledger integrity not reported.</p>
          )}
        </Panel>
      </div>

      <section aria-labelledby="rec-h" className="mt-8">
        <h2 id="rec-h" className="mb-3 text-[15px] font-semibold text-ink">
          Recorded decisions
        </h2>
        {decisions.length ? (
          <Panel className="px-5 py-2">
            <DataTable
              caption="Recorded supervisory decisions"
              rows={[...decisions].sort((a, b) => b.occurredAt - a.occurredAt)}
              rowKey={(d) => d.id}
              columns={[
                {
                  key: "f",
                  header: "Finding",
                  cell: (d) => (
                    <Link href={`/workbench/findings/${d.findingId}`} className="font-medium text-ink hover:text-brand">
                      {titles[d.findingId]?.title ?? d.findingId}
                    </Link>
                  ),
                },
                { key: "a", header: "Decision", cell: (d) => BACKEND_ACTION_LABEL[d.action] },
                { key: "p", header: "Supervisor", cell: (d) => d.principalIdentityId },
                { key: "r", header: "Rationale", cell: (d) => d.reason },
                { key: "b", header: "Bound digest", cell: (d) => <span className="font-mono text-[12px]">{shortDigest(d.findingContentDigest)}</span> },
                { key: "t", header: "Recorded", cell: (d) => fmtDateTime(d.occurredAt) },
              ]}
            />
          </Panel>
        ) : (
          <EmptyState title="No decisions recorded" icon={<Gavel className="size-5" />}>
            The backend holds no supervisory decisions for this period. A decision is recorded from a finding or the review queue by a supervisor, and is then
            mirrored into the hash-chained decision ledger.
          </EmptyState>
        )}
      </section>

      <DevDecisions titles={titles} />
    </div>
  );
}
