import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, ShieldAlert, ShieldCheck } from "lucide-react";
import { TrustTag } from "@/components/ui/badges";
import { DataTable } from "@/components/ui/data";
import { KeyValue, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { getSource } from "@/lib/api";
import { fmtDateTime, shortDigest } from "@/lib/domain/format";
import { loadCore } from "@/lib/model";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "TRUST-SAT" };

const MECHANISM = [
  { k: "Canonical record", d: "Each run and finding is serialized to a canonical form" },
  { k: "SHA3-256 digest", d: "The canonical form is hashed into a content digest" },
  { k: "ML-DSA-65 signature", d: "The digest is signed; the receipt stores algorithm, key and signature" },
  { k: "Re-derivation", d: "Verification rebuilds the digest from the live database row" },
  { k: "Verdict", d: "The live digest must match the signed one and the signature must verify" },
];

export default async function TrustPage() {
  const src = getSource();
  const [core, receipts, audit, sourceRecords, observations] = await Promise.all([
    loadCore(),
    src.listTrustReceipts(),
    src.getMetaAudit(),
    src.listSourceRecords(),
    src.listObservations(),
  ]);
  const names = new Map(core.entities.map((e) => [e.id, e.displayName]));
  const verifications = [...core.verifications.entries()];
  const findingChecks = verifications.flatMap(([, v]) => v?.findings ?? []);
  const findingsOk = findingChecks.filter((f) => f.ok).length;
  const runsOk = verifications.filter(([, v]) => v?.run?.ok).length;
  const allOk = runsOk === core.runs.length && findingsOk === findingChecks.length && (audit?.fully_compliant ?? true);
  const checkedAt = Math.max(0, ...verifications.map(([, v]) => v?.verifiedAt ?? 0));
  const algorithms = [...new Set(receipts.map((r) => r.algorithmId))];
  const signal = core.findings.filter((f) => f.state === "signal");

  const chain = [
    { stage: "Source", n: core.submissions.length, what: "submissions, SHA3-256 per file" },
    { stage: "Record", n: sourceRecords.length, what: "source records with record digests" },
    { stage: "Observation", n: observations.length, what: "worker observations" },
    { stage: "Finding", n: signal.length, what: `findings, ${receipts.filter((r) => r.subjectType === "finding").length} signed` },
    { stage: "Risk", n: core.runs.length, what: `runs, ${receipts.filter((r) => r.subjectType === "run").length} signed` },
    { stage: "Recommendation", n: signal.filter((f) => f.recommendation).length, what: "bounded recommendations" },
    { stage: "Decision", n: core.decisions.length, what: "human decisions, digest-bound" },
  ];

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Trust"
        title="TRUST-SAT"
        description="Can this result be verified? Every run and finding carries a post-quantum signature over its content digest. Verification recomputes the digest from the stored record and checks the signature."
      />

      <Panel className="grid gap-6 px-6 py-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="flex items-start gap-4">
          <span className={cn("flex size-12 shrink-0 items-center justify-center rounded-md", allOk ? "bg-brand text-white" : "bg-critical text-white")}>
            {allOk ? <ShieldCheck className="size-6" aria-hidden="true" /> : <ShieldAlert className="size-6" aria-hidden="true" />}
          </span>
          <div>
            <p className="text-[24px] leading-tight font-semibold tracking-[-0.02em] text-ink">
              {allOk ? "Every signed record verifies" : "Verification found exceptions"}
            </p>
            <p className="mt-1 text-[13px] text-muted">
              {runsOk}/{core.runs.length} runs and {findingsOk}/{findingChecks.length} findings verified · checked {fmtDateTime(checkedAt)}
            </p>
          </div>
        </div>
        <dl className="flex gap-8">
          <div>
            <dt className="label">Receipts</dt>
            <dd className="num mt-1 text-[22px] font-semibold text-ink">{receipts.length}</dd>
          </div>
          <div>
            <dt className="label">Algorithm</dt>
            <dd className="mt-1 text-[15px] font-semibold text-ink">{algorithms.join(", ") || "none"}</dd>
          </div>
          <div>
            <dt className="label">Digest</dt>
            <dd className="mt-1 text-[15px] font-semibold text-ink">SHA3-256</dd>
          </div>
        </dl>
      </Panel>

      <section aria-labelledby="mech-h" className="mt-10">
        <SectionHeader id="mech-h" title="How a record is verified" />
        <ol className="grid gap-px overflow-hidden rounded-md border border-line bg-line sm:grid-cols-2 lg:grid-cols-5">
          {MECHANISM.map((m, i) => (
            <li key={m.k} className="relative bg-paper px-4 py-4">
              <span className="label text-faint">{String(i + 1).padStart(2, "0")}</span>
              <p className="mt-1 text-[14px] font-semibold text-ink">{m.k}</p>
              <p className="mt-1 text-[12.5px] leading-snug text-muted">{m.d}</p>
              {i < MECHANISM.length - 1 && <ArrowRight className="absolute top-4 right-3 hidden size-3.5 text-faint lg:block" aria-hidden="true" />}
            </li>
          ))}
        </ol>
        <p className="mt-3 text-[12.5px] text-muted">
          The claim is detection of tampering at verification time, not tamper-proof storage: someone with write access to the database file and the key could replace both. Changing any
          signed column, including the stored digest itself, is detected.
        </p>
      </section>

      <div className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <section aria-labelledby="runs-h">
          <SectionHeader id="runs-h" title="Verification by run" />
          <Panel className="px-5 py-2">
            <DataTable
              caption="Verification result for each analysis run"
              rows={core.runs}
              rowKey={(r) => r.id}
              columns={[
                {
                  key: "e",
                  header: "Entity",
                  cell: (r) => (
                    <Link href={`/workbench/entities/${r.entityId}`} className="font-medium text-ink hover:text-brand">
                      {names.get(r.entityId)}
                    </Link>
                  ),
                },
                {
                  key: "run",
                  header: "Run signature",
                  cell: (r) => <TrustTag state={core.verifications.get(r.id)?.run?.ok ? "verified" : core.verifications.get(r.id) ? "failed" : "unknown"} />,
                },
                {
                  key: "f",
                  header: "Findings",
                  align: "right",
                  cell: (r) => {
                    const v = core.verifications.get(r.id);
                    return (
                      <span className="num">
                        {v?.findings.filter((f) => f.ok).length ?? 0}/{v?.findings.length ?? 0}
                      </span>
                    );
                  },
                },
                { key: "d", header: "Run digest", cell: (r) => <span className="font-mono text-[12px]">{shortDigest(r.contentDigest, 14)}</span> },
              ]}
            />
          </Panel>
        </section>

        <section aria-labelledby="chain-h">
          <SectionHeader id="chain-h" title="Evidence chain coverage" />
          <Panel className="px-5 py-4">
            <ol className="space-y-2.5">
              {chain.map((c, i) => (
                <li key={c.stage} className="grid grid-cols-[7rem_2.5rem_minmax(0,1fr)] items-baseline gap-3 text-[12.5px]">
                  <span className="label">
                    <span className="mr-1.5 text-faint">{i + 1}</span>
                    {c.stage}
                  </span>
                  <span className="num text-right text-[14px] font-semibold text-ink">{c.n}</span>
                  <span className="text-muted">{c.what}</span>
                </li>
              ))}
            </ol>
          </Panel>
        </section>
      </div>

      <div className="mt-10 grid gap-6 lg:grid-cols-2">
        <Panel className="px-5 py-5" aria-labelledby="ledger-h">
          <SectionHeader id="ledger-h" title="Decision ledger" />
          {audit?.ledger_integrity ? (
            <KeyValue
              items={[
                ["Hash chain", audit.ledger_integrity.chain_ok ? "Intact" : `Broken: ${audit.ledger_integrity.chain_error}`],
                ["Consistency", audit.ledger_integrity.fully_consistent ? "Ledger matches database" : "Mismatch"],
                ["Ledger entries", audit.ledger_integrity.ledger_entries],
                ["Database rows", audit.ledger_integrity.db_rows],
              ]}
            />
          ) : (
            <p className="text-[13px] text-muted">No ledger report.</p>
          )}
          <p className="mt-4 text-[12px] leading-relaxed text-muted">
            Decisions are mirrored into an append-only, hash-chained ledger, so deleting or reordering a decision row is detectable, not only editing one.
          </p>
        </Panel>
        <Panel className="px-5 py-5" aria-labelledby="key-h">
          <SectionHeader id="key-h" title="Keys and limits" />
          <KeyValue
            columns={1}
            items={[
              ["Signing key", `${algorithms[0] ?? "ML-DSA-65"} keypair in a local software keystore`],
              ["Hardware", "No HSM: no PKCS#11 token supports ML-DSA today; the platform fails closed"],
              ["Implementation", "Pure-Python ML-DSA / ML-KEM, not side-channel hardened"],
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}
