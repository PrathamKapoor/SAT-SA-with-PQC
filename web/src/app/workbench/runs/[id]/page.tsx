import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";
import { AutoRefresh } from "@/components/domain/auto-refresh";
import { FindingList } from "@/components/domain/finding-list";
import { CancelRunButton, DecisionForm, VerifyButton } from "@/components/domain/run-controls";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { DataTable, Meter, RiskBreakdown, RiskScore } from "@/components/ui/data";
import { KeyValue, PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api, orNull } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import type { Step } from "@/lib/api/types";
import { can } from "@/lib/auth/permissions";
import { fmtDateTime, fmtNum, prose, shortDigest } from "@/lib/domain/format";
import { ABSTAIN_LABEL } from "@/lib/domain/models";
import { RECOMMENDATION_LABEL, ruleTitle, workerLabel } from "@/lib/domain/labels";
import { DECISION_ACTION, RUN_IN_PROGRESS, RUN_STATUS, STEP_STATUS } from "@/lib/domain/status";
import { bySignalThenConfidence, loadRunFindings } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Analysis run" };

function Section({ id, title, aside, children }: { id: string; title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="border-t border-line pt-6">
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 id={id} className="text-[16px] font-semibold tracking-[-0.01em] text-ink">
          {title}
        </h2>
        {aside && <div className="text-[12.5px] text-muted">{aside}</div>}
      </div>
      {children}
    </section>
  );
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ctx = await requireContext();
  const loaded = await load(async () => {
    const run = await api.run(id);
    const [entity, findings, risk, recommendations, decision, receipt, inference] = await Promise.all([
      api.entity(run.entity_id),
      loadRunFindings(id),
      orNull(api.risk(id)),
      all((q) => api.recommendations(id, q)),
      orNull(api.decision(id)),
      orNull(api.receipt(id)),
      can(ctx.role, "model.read") ? orNull(api.runInference(id)) : Promise.resolve(null),
    ]);
    return { run, entity, findings, risk, recommendations, decision, receipt, inference };
  });

  if (!loaded.ok) {
    return (
      <div className="mx-auto max-w-[1100px] px-4 py-6 md:px-8">
        <ApiErrorPanel error={loaded.error} context="Analysis run" />
      </div>
    );
  }
  const { run, entity, findings, risk, recommendations, decision, receipt, inference } = loaded.data;
  const status = RUN_STATUS[run.status];
  const finalizing = run.status === "awaiting_review" && decision !== null;
  const refreshing = RUN_IN_PROGRESS.includes(run.status) || finalizing;
  const canDecide = can(ctx.role, "review.create");
  const signals = findings.filter((f) => f.state === "signal");
  const sorted = [...findings].sort(bySignalThenConfidence);

  const steps: Step[] = run.steps;
  const stepColumns = [
    { key: "worker", header: "Worker", cell: (s: Step) => <span className="text-ink">{workerLabel(s.worker_name)}</span> },
    { key: "status", header: "Status", cell: (s: Step) => <Tag tone={STEP_STATUS[s.status] ?? "neutral"}>{s.status}</Tag> },
    { key: "attempt", header: "Attempt", cell: (s: Step) => <span className="num">{s.attempt}</span>, align: "right" as const },
    { key: "started", header: "Started", cell: (s: Step) => fmtDateTime(s.started_at) },
    { key: "finished", header: "Finished", cell: (s: Step) => fmtDateTime(s.finished_at) },
  ];

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-6 md:px-8">
      <Link href="/workbench/runs" className="mb-4 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        Analysis runs
      </Link>
      <PageHeader
        eyebrow={`Analysis run · ${run.execution_mode === "graph" ? "LangGraph orchestration" : "standard orchestration"}`}
        title={
          <Link href={`/workbench/entities/${entity.id}`} className="hover:text-brand-strong">
            {entity.display_name}
          </Link>
        }
        meta={
          <>
            <Tag tone={status.tone}>
              <span data-run-status={run.status}>{status.label}</span>
            </Tag>
            <span className="mono-id">{run.id}</span>
            <span className="text-[12.5px] text-muted">Requested {fmtDateTime(run.requested_at)}</span>
          </>
        }
        actions={!["completed", "partial", "failed", "cancelled", "cancel_requested"].includes(run.status) && canDecide ? <CancelRunButton runId={run.id} /> : undefined}
      />
      <AutoRefresh
        active={refreshing}
        label={finalizing ? "Decision recorded. The worker is finalizing the run with TRUST-SAT." : "The worker is processing this run."}
      />

      <div className="mt-4 space-y-8">
        <Section id="progress" title="Progress" aside={`${run.progress_completed} of ${run.progress_total} stages`}>
          <Meter value={run.progress_total ? run.progress_completed : 0} max={run.progress_total || 1} label="Run progress" tone="info" />
          <KeyValue
            className="mt-4"
            columns={4}
            items={[
              ["Current stage", run.current_stage],
              ["Started", fmtDateTime(run.started_at)],
              ["Finished", fmtDateTime(run.finished_at)],
              ["Retries", run.retry_count],
            ]}
          />
          {run.error && (
            <p className="mt-3 text-[13px] text-critical">
              {run.error_code ? `${run.error_code}: ` : ""}
              {run.error}
            </p>
          )}
          <details className="mt-4">
            <summary className="cursor-pointer text-[13px] text-ink-2">Worker steps ({steps.length})</summary>
            <DataTable className="mt-3" caption="Worker steps" columns={stepColumns} rows={steps} rowKey={(s) => s.worker_name} dense empty={<EmptyState title="No worker steps yet" />} />
          </details>
        </Section>

        <Section id="findings" title="Findings" aside={`${signals.length} signal${signals.length === 1 ? "" : "s"} of ${findings.length}`}>
          <FindingList findings={sorted} empty={RUN_IN_PROGRESS.includes(run.status) ? "Findings appear when the workers finish." : "This run produced no findings."} />
        </Section>

        <Section id="risk" title="Risk" aside={risk ? `${risk.algorithm_version} · ${shortDigest(risk.content_digest)}` : undefined}>
          {risk ? (
            <div className="grid gap-6 md:grid-cols-[12rem_minmax(0,1fr)]">
              <RiskScore score={risk.profile.total_score} bucket={risk.profile.confidence_bucket} size="lg" />
              <RiskBreakdown dimensions={risk.profile.dimensions} />
            </div>
          ) : (
            <EmptyState title="No risk profile yet">The worker persists the risk profile when the analytical stages finish.</EmptyState>
          )}
        </Section>

        <Section id="recommendations" title="Recommendations" aside="Bounded hints for the reviewer, never decisions">
          {recommendations.length ? (
            <ul className="space-y-3">
              {recommendations.map((r) => {
                const f = findings.find((x) => x.id === r.finding_id);
                return (
                  <li key={r.id} className="rounded-md border border-line bg-paper px-4 py-3">
                    <p className="text-[14px] font-medium text-ink">{RECOMMENDATION_LABEL[r.action as keyof typeof RECOMMENDATION_LABEL] ?? r.action}</p>
                    {r.recommendation.reason && <p className="mt-1 text-[13px] text-ink-2">{prose(String(r.recommendation.reason))}</p>}
                    <p className="mt-1 text-[12px] text-muted">
                      For{" "}
                      <Link className="text-brand hover:underline" href={`/workbench/findings/${r.finding_id}`}>
                        {f ? ruleTitle(f.rule_or_category) : r.finding_id}
                      </Link>
                      {r.recommendation.limitations ? `. ${prose(String(r.recommendation.limitations))}` : ""}
                    </p>
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState title="No recommendations">Recommendations are produced for signal findings once analysis completes.</EmptyState>
          )}
        </Section>

        {inference && (
          <Section id="model" title="Advisory model score" aside="Orders the review queue; never a decision">
            <div className="rounded-md border border-line bg-paper px-4 py-3" data-inference={inference.status}>
              {inference.status === "scored" ? (
                <p className="text-[14px] text-ink">
                  Estimated likelihood a supervisor confirms or escalates: <span className="font-semibold">{fmtNum((inference.score ?? 0) * 100, 0)}%</span>
                </p>
              ) : (
                <p className="text-[14px] text-ink">
                  <Tag>abstained</Tag> {inference.abstain_reason ? ABSTAIN_LABEL[inference.abstain_reason] : "No score"}
                </p>
              )}
              <p className="mt-1 text-[12px] text-muted">
                {inference.model_id ? (
                  <>
                    Model{" "}
                    <Link className="text-brand hover:underline" href={`/workbench/models/${inference.model_id}`}>
                      {inference.model_id}
                    </Link>{" "}
                    · artifact <span className="mono-id">{shortDigest(inference.artifact_digest, 12)}</span> ·{" "}
                  </>
                ) : null}
                {inference.feature_version} · record <span className="mono-id">{shortDigest(inference.content_digest, 12)}</span>, bound into the TRUST-SAT
                finalization of this run
              </p>
            </div>
          </Section>
        )}

        <Section id="decision" title="Supervisory decision">
          {decision ? (
            <div className="rounded-md border border-line bg-paper px-4 py-3" data-decision={decision.action}>
              <div className="flex flex-wrap items-center gap-2">
                <Tag tone={DECISION_ACTION[decision.action].tone}>{DECISION_ACTION[decision.action].label}</Tag>
                <span className="text-[12.5px] text-muted">Recorded {fmtDateTime(decision.created_at)}</span>
              </div>
              {decision.reason && <p className="mt-2 text-[13.5px] text-ink">{decision.reason}</p>}
              <KeyValue
                className="mt-3"
                columns={2}
                items={[
                  ["Decided by identity", <span key="p" className="mono-id">{decision.principal_identity_id}</span>],
                  ["Decision digest", <span key="d" className="mono-id">{shortDigest(decision.content_digest, 20)}</span>],
                ]}
              />
            </div>
          ) : run.status === "awaiting_review" ? (
            canDecide ? (
              <DecisionForm runId={run.id} />
            ) : (
              <EmptyState title="Awaiting a supervisor">A supervisor or organization administrator records the decision for this run.</EmptyState>
            )
          ) : (
            <EmptyState title="No decision">
              {RUN_IN_PROGRESS.includes(run.status) ? "The run reaches review when the analytical stages finish." : "This run ended without a supervisory decision."}
            </EmptyState>
          )}
        </Section>

        <Section id="trust" title="TRUST-SAT">
          {receipt ? (
            <div className="space-y-4">
              <KeyValue
                columns={2}
                items={[
                  ["Receipt state", <Tag key="s" tone={receipt.state === "verified" ? "brand" : "neutral"}>{receipt.state}</Tag>],
                  ["Algorithm", receipt.algorithm_id],
                  ["Signing key", <span key="k" className="mono-id">{receipt.key_id}</span>],
                  ["Signed", fmtDateTime(receipt.created_at)],
                  ["Supervisory digest", <span key="c" className="mono-id">{shortDigest(receipt.content_digest, 24)}</span>],
                  ["Ledger entry", <span key="l" className="mono-id">{shortDigest(receipt.ledger_entry_hash, 24)}</span>],
                ]}
              />
              {can(ctx.role, "trust.verify") && <VerifyButton runId={run.id} />}
            </div>
          ) : (
            <EmptyState title="Not finalized">
              {decision ? "The worker signs the decided record after the decision." : "A receipt is issued after the supervisory decision is recorded and the run is finalized."}
            </EmptyState>
          )}
        </Section>
      </div>
    </div>
  );
}
