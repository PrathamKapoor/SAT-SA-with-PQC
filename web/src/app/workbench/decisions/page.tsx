import type { Metadata } from "next";
import Link from "next/link";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { DataTable } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api, orNull } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import type { Decision, Run } from "@/lib/api/types";
import { fmtDateTime, shortDigest } from "@/lib/domain/format";
import { DECISION_ACTION, RUN_STATUS } from "@/lib/domain/status";
import { entityName, loadPortfolio } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Decisions" };

type Row = { run: Run; decision: Decision };

export default async function DecisionsPage() {
  const loaded = await load(async () => {
    const [runs, portfolio] = await Promise.all([all((q) => api.runs(q)), loadPortfolio()]);
    // Only runs that reached review can carry a decision.
    const candidates = runs.filter((r) => ["awaiting_review", "completed", "partial"].includes(r.status));
    const rows = (await Promise.all(candidates.map(async (run) => ({ run, decision: await orNull(api.decision(run.id)) }))))
      .filter((r): r is Row => r.decision !== null)
      .sort((a, b) => b.decision.created_at - a.decision.created_at);
    return { rows, portfolio };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Supervision"
        title="Decisions"
        description="Supervisory decisions recorded in this organization, newest first. Each is one immutable decision on one run, bound to the deciding identity and signed by TRUST-SAT when the run is finalized."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Decisions" />
      ) : (
        <DataTable
          caption="Supervisory decisions"
          rows={loaded.data.rows}
          rowKey={(r) => r.decision.id}
          empty={<EmptyState title="No decisions recorded yet">Decisions are recorded from a run in the review queue.</EmptyState>}
          columns={[
            {
              key: "entity",
              header: "Entity",
              cell: (r: Row) => (
                <Link href={`/workbench/runs/${r.run.id}`} className="font-medium text-ink hover:text-brand-strong">
                  {entityName(loaded.data.portfolio, r.run.entity_id)}
                </Link>
              ),
            },
            { key: "action", header: "Decision", cell: (r: Row) => <Tag tone={DECISION_ACTION[r.decision.action].tone}>{DECISION_ACTION[r.decision.action].label}</Tag> },
            { key: "reason", header: "Reason", cell: (r: Row) => <span className="line-clamp-2 max-w-md">{r.decision.reason || <span className="text-muted">No reason given</span>}</span> },
            { key: "when", header: "Recorded", cell: (r: Row) => fmtDateTime(r.decision.created_at) },
            { key: "by", header: "Identity", cell: (r: Row) => <span className="mono-id">{r.decision.principal_identity_id}</span> },
            { key: "run", header: "Run status", cell: (r: Row) => <Tag tone={RUN_STATUS[r.run.status].tone}>{RUN_STATUS[r.run.status].label}</Tag> },
            { key: "digest", header: "Digest", cell: (r: Row) => <span className="mono-id">{shortDigest(r.decision.content_digest)}</span> },
          ]}
        />
      )}
    </div>
  );
}
