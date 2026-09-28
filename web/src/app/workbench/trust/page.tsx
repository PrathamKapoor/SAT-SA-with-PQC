import type { Metadata } from "next";
import Link from "next/link";
import { VerifyButton } from "@/components/domain/run-controls";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { Metric, PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api, orNull } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import { fmtDateTime, shortDigest } from "@/lib/domain/format";
import { entityName, loadPortfolio } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "TRUST-SAT" };

export default async function TrustPage() {
  const loaded = await load(async () => {
    const [runs, portfolio] = await Promise.all([all((q) => api.runs(q)), loadPortfolio()]);
    const finalized = runs.filter((r) => r.status === "completed" || r.status === "partial");
    const rows = await Promise.all(finalized.map(async (run) => ({ run, receipt: await orNull(api.receipt(run.id)) })));
    return { rows: rows.sort((a, b) => (b.receipt?.created_at ?? 0) - (a.receipt?.created_at ?? 0)), portfolio, awaiting: runs.filter((r) => r.status === "awaiting_review").length };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Trust"
        title="TRUST-SAT"
        description="After a supervisor decides, the worker binds the decided record: canonical supervisory digest, ML-DSA-65 signature and a hash-chained ledger entry. Verification rebuilds the canonical state from the database and checks both. Only public key material is shown."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="TRUST-SAT" />
      ) : (
        <>
          <dl className="mb-6 grid grid-cols-2 gap-6 md:grid-cols-3">
            <Metric label="Finalized runs" value={loaded.data.rows.length} />
            <Metric label="With a receipt" value={loaded.data.rows.filter((r) => r.receipt).length} tone="brand" />
            <Metric label="Awaiting decision" value={loaded.data.awaiting} tone={loaded.data.awaiting ? "attention" : "ink"} />
          </dl>
          {loaded.data.rows.length === 0 ? (
            <EmptyState title="No finalized runs yet">A receipt is issued when a supervisor decides a run and the worker finalizes it.</EmptyState>
          ) : (
            <ul className="space-y-3" aria-label="Signed runs">
              {loaded.data.rows.map(({ run, receipt }) => (
                <li key={run.id} className="grid gap-4 rounded-md border border-line bg-paper px-5 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)_12rem]">
                  <div className="min-w-0">
                    <Link href={`/workbench/runs/${run.id}#trust`} className="text-[14.5px] font-semibold text-ink hover:text-brand-strong">
                      {entityName(loaded.data.portfolio, run.entity_id)}
                    </Link>
                    <p className="mono-id mt-0.5">{run.id}</p>
                  </div>
                  {receipt ? (
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[12.5px]">
                      <dt className="text-muted">State</dt>
                      <dd>
                        <Tag tone={receipt.state === "verified" ? "brand" : "neutral"}>{receipt.state}</Tag>
                      </dd>
                      <dt className="text-muted">Algorithm</dt>
                      <dd className="text-ink">{receipt.algorithm_id}</dd>
                      <dt className="text-muted">Signed</dt>
                      <dd className="text-ink">{fmtDateTime(receipt.created_at)}</dd>
                      <dt className="text-muted">Ledger entry</dt>
                      <dd className="mono-id">{shortDigest(receipt.ledger_entry_hash, 20)}</dd>
                    </dl>
                  ) : (
                    <p className="text-[13px] text-attention-strong">No receipt was found for this finalized run.</p>
                  )}
                  <div>{receipt && <VerifyButton runId={run.id} />}</div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
