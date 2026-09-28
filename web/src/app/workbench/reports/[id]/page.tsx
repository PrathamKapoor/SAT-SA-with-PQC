import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { PrintButton } from "@/components/domain/print-button";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { RiskBreakdown, RiskScore } from "@/components/ui/data";
import { KeyValue, PageHeader, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api, orNull } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import { fmtDateTime, fmtPeriod, prose, shortDigest } from "@/lib/domain/format";
import { RECOMMENDATION_LABEL, ruleTitle } from "@/lib/domain/labels";
import { DECISION_ACTION, RUN_STATUS } from "@/lib/domain/status";
import { bySignalThenConfidence, loadPortfolio, loadRunFindings } from "@/lib/workbench/data";

export const metadata: Metadata = { title: "Report" };

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const ctx = await requireContext();
  const loaded = await load(async () => {
    const [entity, portfolio] = await Promise.all([api.entity(id), loadPortfolio()]);
    const priority = portfolio.priority.get(id) ?? null;
    if (!priority) return { entity, priority, rank: null, run: null, assessment: null, risk: null, findings: [], recommendations: [], decision: null, receipt: null };
    const run = await api.run(priority.run_id);
    const [assessment, risk, findings, recommendations, decision, receipt] = await Promise.all([
      api.assessment(run.assessment_id),
      orNull(api.risk(run.id)),
      loadRunFindings(run.id),
      all((q) => api.recommendations(run.id, q)),
      orNull(api.decision(run.id)),
      orNull(api.receipt(run.id)),
    ]);
    return { entity, priority, rank: portfolio.rank.get(id) ?? null, run, assessment, risk, findings, recommendations, decision, receipt };
  });

  if (!loaded.ok) {
    return (
      <div className="mx-auto max-w-[900px] px-4 py-6 md:px-8">
        <ApiErrorPanel error={loaded.error} context="Report" />
      </div>
    );
  }
  const d = loaded.data;
  const signals = d.findings.filter((f) => f.state === "signal").sort(bySignalThenConfidence);

  return (
    <div className="mx-auto max-w-[900px] px-4 py-6 md:px-8">
      <Link href="/workbench/reports" className="no-print mb-4 inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        Reports
      </Link>
      <PageHeader
        eyebrow={`Supervisory report · ${ctx.organization.name}`}
        title={d.entity.display_name}
        description={d.assessment ? `Assessment period ${fmtPeriod(d.assessment.period_start, d.assessment.period_end)}` : undefined}
        actions={<PrintButton disabled={!d.run} reason="No analysed run to report" />}
      />
      {!d.run ? (
        <EmptyState title="No analysed run">This entity has no run with a persisted risk profile yet.</EmptyState>
      ) : (
        <div className="space-y-8">
          <KeyValue
            columns={4}
            items={[
              ["Priority rank", d.rank ?? "n/a"],
              ["Run status", <Tag key="s" tone={RUN_STATUS[d.run.status].tone}>{RUN_STATUS[d.run.status].label}</Tag>],
              ["Analysed", fmtDateTime(d.run.finished_at ?? d.run.started_at)],
              ["Run", <span key="r" className="mono-id">{d.run.id}</span>],
            ]}
          />
          <section aria-labelledby="r-risk">
            <SectionHeader id="r-risk" title="Risk" />
            {d.risk ? (
              <div className="grid gap-6 md:grid-cols-[11rem_minmax(0,1fr)]">
                <RiskScore score={d.risk.profile.total_score} bucket={d.risk.profile.confidence_bucket} size="lg" />
                <RiskBreakdown dimensions={d.risk.profile.dimensions} />
              </div>
            ) : (
              <p className="text-[13px] text-muted">No risk profile persisted.</p>
            )}
            {d.priority && <p className="mt-2 text-[12.5px] text-muted">{d.priority.rationale}</p>}
          </section>
          <section aria-labelledby="r-findings">
            <SectionHeader id="r-findings" title="Signal findings" aside={`${signals.length}`} />
            {signals.length ? (
              <ol className="space-y-3">
                {signals.map((f) => {
                  const rec = d.recommendations.find((r) => r.finding_id === f.id);
                  return (
                    <li key={f.id} className="break-inside-avoid border-b border-line pb-3 last:border-0">
                      <p className="text-[14px] font-medium text-ink">{ruleTitle(f.rule_or_category)}</p>
                      <p className="mt-1 text-[13px] text-ink-2">{prose(f.rationale)}</p>
                      <p className="mt-1 text-[12px] text-muted">
                        {f.evidence_refs.length} cited record(s)
                        {rec ? ` · Recommendation: ${RECOMMENDATION_LABEL[rec.action as keyof typeof RECOMMENDATION_LABEL] ?? rec.action}` : ""}
                      </p>
                    </li>
                  );
                })}
              </ol>
            ) : (
              <p className="text-[13px] text-muted">No signal findings in this run.</p>
            )}
          </section>
          <section aria-labelledby="r-decision">
            <SectionHeader id="r-decision" title="Supervisory decision and trust" />
            <KeyValue
              columns={2}
              items={[
                ["Decision", d.decision ? `${DECISION_ACTION[d.decision.action].label}, ${fmtDateTime(d.decision.created_at)}` : "Not recorded"],
                ["Reason", d.decision?.reason || "n/a"],
                ["TRUST-SAT receipt", d.receipt ? `${d.receipt.algorithm_id}, ${d.receipt.state}` : "Not finalized"],
                ["Ledger entry", d.receipt ? <span key="l" className="mono-id">{shortDigest(d.receipt.ledger_entry_hash, 24)}</span> : "n/a"],
              ]}
            />
          </section>
        </div>
      )}
    </div>
  );
}
