import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { FamilyLabel, Tag } from "@/components/ui/badges";
import { ConfidenceDisplay, RiskScore, Timeline } from "@/components/ui/data";
import { KeyValue, PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api, orNull } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import type { CanonicalRecord } from "@/lib/api/types";
import { fmtDateTime, fmtNum, prose, shortDigest } from "@/lib/domain/format";
import { CATEGORY_LABEL, DIMENSION_LABEL, familyOf, RECOMMENDATION_LABEL, ruleTitle } from "@/lib/domain/labels";
import { DECISION_ACTION, FINDING_STATE_LABEL, RUN_STATUS } from "@/lib/domain/status";

export const metadata: Metadata = { title: "Finding" };

/** Records read to resolve citations; a version larger than this is reported, not truncated silently. */
const RECORD_SCAN_LIMIT = 4000;

function Section({ id, label, title, children, aside }: { id: string; label: string; title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section aria-labelledby={id} className="border-t border-line pt-6">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <div className="flex items-baseline gap-3">
          <span className="label w-6 shrink-0 text-faint">{label}</span>
          <h2 id={id} className="text-[16px] font-semibold tracking-[-0.01em] text-ink">
            {title}
          </h2>
        </div>
        {aside && <div className="text-[12.5px] text-muted">{aside}</div>}
      </div>
      <div className="sm:pl-9">{children}</div>
    </section>
  );
}

function RecordPayload({ record }: { record: CanonicalRecord }) {
  const entries = Object.entries(record.payload).filter(([, v]) => v !== null && v !== "" && !(Array.isArray(v) && !v.length));
  return (
    <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
      {entries.map(([k, v]) => (
        <div key={k} className="flex min-w-0 gap-2 text-[12.5px]">
          <dt className="shrink-0 font-mono text-muted">{k}</dt>
          <dd className="min-w-0 truncate text-ink">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

export default async function FindingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const loaded = await load(async () => {
    const finding = await api.finding(id);
    const run = await api.run(finding.run_id);
    const [entity, evidence, risk, recommendations, decision, receipt, priorities] = await Promise.all([
      api.entity(run.entity_id),
      all((q) => api.evidence(run.id, q)),
      orNull(api.risk(run.id)),
      all((q) => api.recommendations(run.id, q)),
      orNull(api.decision(run.id)),
      orNull(api.receipt(run.id)),
      all((q) => api.priorities(q)),
    ]);
    const cited = new Set(finding.evidence_refs);
    const citedEvidence = evidence.filter((e) => cited.has(e.source_record_id));
    const records = citedEvidence.length ? await all((q) => api.records(run.submission_version_id, q), RECORD_SCAN_LIMIT) : [];
    return { finding, run, entity, citedEvidence, records, risk, recommendations, decision, receipt, priorities };
  });

  if (!loaded.ok) {
    return (
      <div className="mx-auto max-w-[1100px] px-4 py-6 md:px-8">
        <ApiErrorPanel error={loaded.error} context="Finding" />
      </div>
    );
  }
  const { finding: f, run, entity, citedEvidence, records, risk, recommendations, decision, receipt, priorities } = loaded.data;
  const recordBySource = new Map(records.map((r) => [r.source_record_id, r]));
  const unresolved = citedEvidence.filter((e) => !recordBySource.has(e.source_record_id)).length;
  const dimension = risk?.profile.dimensions.find((d) => d.finding_ids.includes(f.id)) ?? null;
  const priority = priorities.find((p) => p.run_id === run.id) ?? null;
  const rank = priority ? priorities.indexOf(priority) + 1 : null;
  const recommendation = recommendations.find((r) => r.finding_id === f.id) ?? null;

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-6 md:px-8">
      <Link href={`/workbench/runs/${run.id}`} className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        Run for {entity.display_name}
      </Link>
      <PageHeader
        eyebrow={<FamilyLabel family={familyOf(f.rule_or_category)} />}
        title={ruleTitle(f.rule_or_category)}
        meta={
          <>
            <Tag tone={f.state === "signal" ? "attention" : "neutral"}>{FINDING_STATE_LABEL[f.state] ?? f.state}</Tag>
            <span className="mono-id">{f.rule_or_category}</span>
            <span className="mono-id">{f.id}</span>
          </>
        }
      />

      <div className="space-y-8">
        <Section id="why" label="01" title="Why it was flagged">
          <p className="max-w-3xl text-[14px] leading-relaxed text-ink">{prose(f.rationale) || "The detector recorded no rationale."}</p>
          <KeyValue
            className="mt-4"
            columns={3}
            items={[
              ["Statistic", fmtNum(f.statistic, 2)],
              ["Effect", fmtNum(f.effect, 2)],
              ["Threshold", fmtNum(f.threshold, 2)],
            ]}
          />
          {f.limitations && <p className="mt-4 text-[13px] text-muted">Limitations: {prose(f.limitations)}</p>}
          <div className="mt-6 max-w-md">
            <ConfidenceDisplay confidence={f.confidence} />
          </div>
        </Section>

        <Section id="evidence" label="02" title="Evidence" aside={`${f.evidence_refs.length} cited record${f.evidence_refs.length === 1 ? "" : "s"}`}>
          {citedEvidence.length === 0 ? (
            <EmptyState title="No cited source records">This finding does not cite individual records; it describes the submission as a whole.</EmptyState>
          ) : (
            <ul className="space-y-3">
              {citedEvidence.map((e) => {
                const record = recordBySource.get(e.source_record_id);
                return (
                  <li key={e.source_record_id} className="rounded-md border border-line bg-paper px-4 py-3" data-evidence={e.source_record_id}>
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-[13.5px] font-medium text-ink">
                        {CATEGORY_LABEL[e.category] ?? e.category} · {e.locator}
                      </span>
                      <span className="mono-id">{e.record_id}</span>
                    </div>
                    {record ? (
                      <RecordPayload record={record} />
                    ) : (
                      <p className="mt-1 text-[12.5px] text-muted">Record content not loaded (the submission holds more records than this page reads).</p>
                    )}
                    <p className="mt-2 font-mono text-[11px] text-faint">
                      canonical {shortDigest(e.canonical_record_digest, 16)} · file {shortDigest(e.file_digest, 16)}
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
          {unresolved > 0 && <p className="mt-2 text-[12px] text-attention-strong">{unresolved} cited record(s) could not be matched within the first {RECORD_SCAN_LIMIT} records.</p>}
        </Section>

        <Section id="provenance" label="03" title="Provenance">
          <Timeline
            label="Provenance of this finding"
            items={[
              { id: "src", title: "Submitted evidence", detail: `${citedEvidence.length} source record(s) in submission version ${run.submission_version_id}` },
              { id: "run", title: `Analysis run (${RUN_STATUS[run.status].label})`, at: fmtDateTime(run.started_at), detail: <span className="mono-id">{run.id}</span> },
              { id: "finding", title: "Finding recorded", at: fmtDateTime(f.created_at), detail: <span className="mono-id">digest {shortDigest(f.content_digest, 20)}</span> },
              decision
                ? { id: "decision", title: `Supervisor decision: ${DECISION_ACTION[decision.action].label}`, at: fmtDateTime(decision.created_at) }
                : { id: "decision", title: "Supervisor decision", state: "missing" as const, detail: "Not recorded yet" },
              receipt
                ? { id: "trust", title: "TRUST-SAT receipt", at: fmtDateTime(receipt.created_at), detail: <span className="mono-id">{receipt.algorithm_id} · {shortDigest(receipt.ledger_entry_hash, 16)}</span> }
                : { id: "trust", title: "TRUST-SAT receipt", state: "missing" as const, detail: "Issued after the decision is finalized" },
            ]}
          />
        </Section>

        <Section id="risk" label="04" title="Risk and priority">
          <div className="grid gap-6 md:grid-cols-3">
            <div>
              <p className="label mb-1">Entity risk (this run)</p>
              {risk ? <RiskScore score={risk.profile.total_score} bucket={risk.profile.confidence_bucket} /> : <p className="text-[13px] text-muted">Not persisted yet</p>}
            </div>
            <div>
              <p className="label mb-1">Dimension</p>
              {dimension ? (
                <p className="text-[13.5px] text-ink">
                  {DIMENSION_LABEL[dimension.name]} <span className="num text-muted">{fmtNum(dimension.score, 1)}/{dimension.weight}</span>
                </p>
              ) : (
                <p className="text-[13px] text-muted">This finding does not contribute to a weighted dimension.</p>
              )}
            </div>
            <div>
              <p className="label mb-1">Entity priority</p>
              {priority ? (
                <p className="text-[13.5px] text-ink">
                  Rank <span className="num">{rank}</span> · score <span className="num">{fmtNum(priority.priority_score, 1)}</span>
                </p>
              ) : (
                <p className="text-[13px] text-muted">This run is not the entity&apos;s current ranked run.</p>
              )}
            </div>
          </div>
          {priority && <p className="mt-3 text-[12.5px] text-muted">{priority.rationale}</p>}
        </Section>

        <Section id="recommendation" label="05" title="Recommendation">
          {recommendation ? (
            <div className="rounded-md border border-line bg-paper px-4 py-3">
              <p className="text-[14px] font-medium text-ink">{RECOMMENDATION_LABEL[recommendation.action as keyof typeof RECOMMENDATION_LABEL] ?? recommendation.action}</p>
              {recommendation.recommendation.reason && <p className="mt-1 text-[13px] text-ink-2">{prose(String(recommendation.recommendation.reason))}</p>}
              {recommendation.recommendation.limitations && <p className="mt-1 text-[12.5px] text-muted">{prose(String(recommendation.recommendation.limitations))}</p>}
            </div>
          ) : (
            <EmptyState title="No recommendation for this finding" />
          )}
        </Section>

        <Section id="review" label="06" title="Review and trust">
          <p className="mb-3 text-[13px] text-muted">The supervisor decides on the whole run, with this finding as part of its evidence.</p>
          <KeyValue
            columns={2}
            items={[
              ["Decision", decision ? <Tag key="d" tone={DECISION_ACTION[decision.action].tone}>{DECISION_ACTION[decision.action].label}</Tag> : run.status === "awaiting_review" ? "Awaiting a supervisor" : "Not recorded"],
              ["TRUST-SAT", receipt ? `Signed, ${receipt.state}` : "Not finalized"],
            ]}
          />
          <Link href={`/workbench/runs/${run.id}#decision`} className="mt-4 inline-block text-[13px] text-brand hover:underline">
            Open the run to review, decide and verify
          </Link>
        </Section>
      </div>
    </div>
  );
}
