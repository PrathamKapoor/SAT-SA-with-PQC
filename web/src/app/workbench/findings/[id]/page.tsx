import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Info, Lightbulb, Paperclip, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { EvidenceLifecycle } from "@/components/domain/evidence-lifecycle";
import { ProvenanceChain, type ProvenanceNode } from "@/components/domain/provenance-chain";
import { ReviewPanel } from "@/components/domain/review-panel";
import { WhyFlagged } from "@/components/domain/why-flagged";
import { FamilyLabel, ReviewStatusTag, SeverityMark, TrustTag } from "@/components/ui/badges";
import { ConfidenceDisplay, DataTable } from "@/components/ui/data";
import { getSource } from "@/lib/api";
import { can, ROLE_LABEL } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { fmtDate, fmtDateTime, fmtNum, fmtPct, shortDigest, sourceName } from "@/lib/domain/format";
import { DIMENSION_LABEL, RECOMMENDATION_LABEL, ruleTitle, workerLabel } from "@/lib/domain/labels";
import { BACKEND_ACTION_LABEL } from "@/lib/domain/review";
import { loadCore, loadFindingViews } from "@/lib/model";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const f = (await loadFindingViews()).find((x) => x.id === id);
  return { title: f ? ruleTitle(f.ruleOrCategory) : "Finding" };
}

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

export default async function FindingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = await getSession();
  const src = getSource();
  const views = await loadFindingViews();
  const f = views.find((x) => x.id === id);
  if (!f || !session) notFound();

  const core = await loadCore();
  const [data, sourceRecords, observations, receipts, risk, audit, history] = await Promise.all([
    src.getSecurityData(f.entityId),
    src.listSourceRecords(f.evidenceRefs),
    src.listObservations(f.runId),
    src.listTrustReceipts(f.id),
    src.getRiskProfile(f.entityId),
    src.getMetaAudit(),
    src.listReviewDecisions(f.id),
  ]);
  const submission = core.submissions.find((s) => s.assessmentId === f.assessmentId) ?? null;
  const assessment = core.assessments.find((a) => a.id === f.assessmentId) ?? null;
  const observation = observations.find((o) => o.id === f.observationId) ?? null;
  const receipt = receipts.find((r) => r.subjectType === "finding") ?? null;
  const runVerification = core.verifications.get(f.runId);
  const dimension = risk?.dimensions.find((d) => d.name === f.riskDimension) ?? null;

  const subjectFor = (srId: string) => {
    const a = data.alerts.find((x) => x.sourceRecordRef === srId);
    if (a) return { kind: "Alert", native: a.nativeId };
    const c = data.cases.find((x) => x.sourceRecordRef === srId);
    if (c) return { kind: "Case", native: c.nativeId };
    return { kind: "Record", native: "" };
  };

  const decision = history.at(-1) ?? null;
  const provenance: ProvenanceNode[] = [
    {
      key: "source",
      stage: "Source",
      title: submission ? sourceName(submission.sourceSystem) : "Submission not found",
      ref: submission ? `${Object.keys(submission.fileDigests).length} files · SHA3-256 per file` : undefined,
      state: submission?.ingestStatus === "accepted" ? "present" : "pending",
      note: submission ? `Received ${fmtDate(submission.receivedAt)}` : undefined,
    },
    {
      key: "record",
      stage: "Record",
      title: `${sourceRecords.length} source record${sourceRecords.length === 1 ? "" : "s"}`,
      ref: sourceRecords[0] ? `record digest ${shortDigest(sourceRecords[0].originalRecordDigest)}${sourceRecords.length > 1 ? " and others" : ""}` : "none attached",
      state: sourceRecords.length ? "present" : "pending",
    },
    {
      key: "observation",
      stage: "Observation",
      title: `${workerLabel(f.workerName)} worker v${f.detectorVersion}`,
      ref: observation ? `${observation.id} · ${observation.state}` : f.observationId,
      state: "present",
    },
    {
      key: "finding",
      stage: "Finding",
      title: receipt ? `${receipt.algorithmId} signature over SHA3-256` : "No trust receipt",
      ref: `digest ${shortDigest(f.contentDigest, 16)}`,
      state: f.trust === "verified" ? "verified" : f.trust === "failed" ? "failed" : "pending",
      note: f.trustReason,
    },
    {
      key: "risk",
      stage: "Risk",
      title: dimension ? `${DIMENSION_LABEL[dimension.name]}: ${fmtNum(dimension.score, 1)} of ${dimension.weight}` : DIMENSION_LABEL[f.riskDimension],
      ref: risk ? `entity risk ${fmtNum(risk.total_score, 1)}/100 · run ${runVerification?.run?.ok ? "signature verified" : "not verified"}` : undefined,
      state: runVerification?.run?.ok ? "verified" : "present",
    },
    {
      key: "recommendation",
      stage: "Recommendation",
      title: f.recommendation ? RECOMMENDATION_LABEL[f.recommendation.action] : "None",
      ref: f.recommendation ? f.recommendation.action : undefined,
      state: f.recommendation ? "present" : "pending",
    },
    {
      key: "decision",
      stage: "Decision",
      title: decision ? `${BACKEND_ACTION_LABEL[decision.action]} by ${decision.principalIdentityId}` : "Awaiting human decision",
      ref: decision ? `bound to digest ${shortDigest(decision.findingContentDigest)}` : "A supervisor records the decision",
      state: decision ? "present" : "pending",
    },
  ];

  const evidenceRows = sourceRecords.map((sr) => ({ ...sr, subject: subjectFor(sr.id) }));

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-6 md:px-8">
      <Link href="/workbench/findings" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        Findings
      </Link>

      <header className="mt-4 grid gap-6 pb-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <FamilyLabel family={f.family} />
            <Link href={`/workbench/entities/${f.entityId}`} className="text-[13px] font-medium text-ink-2 hover:text-brand">
              {f.entityName}
            </Link>
            {assessment && <span className="text-[12.5px] text-muted">{fmtDate(assessment.periodStart)} to {fmtDate(assessment.periodEnd)}</span>}
          </div>
          <h1 className="mt-3 max-w-4xl text-[30px] leading-[1.1] font-semibold tracking-[-0.025em] text-ink md:text-[36px]">{ruleTitle(f.ruleOrCategory)}</h1>
          <p className="mono-id mt-2">{f.ruleOrCategory}</p>
        </div>
        <dl className="grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-4 lg:flex lg:gap-8">
          <div>
            <dt className="label">Severity</dt>
            <dd className="mt-1.5">
              <SeverityMark severity={f.severity} />
            </dd>
          </div>
          <div>
            <dt className="label">Confidence</dt>
            <dd className="num mt-1 text-[18px] font-semibold text-ink">{fmtPct(f.confidence?.overall ?? null)}</dd>
          </div>
          <div>
            <dt className="label">Evidence</dt>
            <dd className="mt-1 inline-flex items-center gap-1 text-[18px] font-semibold text-ink">
              <Paperclip className="size-4 text-faint" aria-hidden="true" />
              <span className="num">{f.evidenceCount}</span>
            </dd>
          </div>
          <div>
            <dt className="label">Status</dt>
            <dd className="mt-1.5 flex flex-wrap gap-1.5">
              <ReviewStatusTag status={f.reviewStatus} />
              <TrustTag state={f.trust} />
            </dd>
          </div>
        </dl>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_21rem] xl:gap-12">
        <div className="min-w-0 space-y-8">
          <Section id="s-why" label="01" title="Why this matters">
            <p className="max-w-3xl text-[19px] leading-[1.45] tracking-[-0.01em] text-ink">{f.rationale}</p>
            {f.limitations && (
              <p className="mt-4 flex max-w-3xl items-start gap-2 text-[13px] leading-relaxed text-muted">
                <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                <span>
                  <span className="font-medium text-ink-2">What this does not show. </span>
                  {f.limitations}
                </span>
              </p>
            )}
          </Section>

          <Section id="s-life" label="02" title="Evidence lifecycle" aside={`${f.scopedSubjects.length} scoped record${f.scopedSubjects.length === 1 ? "" : "s"}`}>
            <EvidenceLifecycle subjects={f.scopedSubjects} data={data} submission={submission} />
          </Section>

          <Section id="s-flag" label="03" title="Why this was flagged" aside={`${workerLabel(f.workerName)} v${f.detectorVersion}`}>
            <WhyFlagged finding={f} />
          </Section>

          <Section id="s-evidence" label="04" title="Supporting evidence" aside={`${evidenceRows.length} source record${evidenceRows.length === 1 ? "" : "s"}`}>
            <DataTable
              caption="Source records supporting this finding"
              rows={evidenceRows}
              rowKey={(r) => r.id}
              empty={<p className="text-[13px] text-muted">The detector attached no source records to this finding.</p>}
              columns={[
                {
                  key: "rec",
                  header: "Record",
                  cell: (r) => (
                    <span>
                      <span className="font-mono text-[12.5px] font-medium text-ink">{r.subject.native || r.id.slice(0, 14)}</span>
                      <span className="ml-1.5 text-[11.5px] text-muted">{r.subject.kind}</span>
                    </span>
                  ),
                },
                { key: "loc", header: "Location", cell: (r) => <span className="font-mono text-[12px]">{`${r.format.toUpperCase()} ${r.locator}`}</span> },
                { key: "rd", header: "Record digest", cell: (r) => <span className="font-mono text-[12px]">{shortDigest(r.originalRecordDigest, 16)}</span> },
                { key: "fd", header: "File digest", cell: (r) => <span className="font-mono text-[12px] text-muted">{shortDigest(r.fileDigest, 10)}</span> },
              ]}
            />
          </Section>

          <Section id="s-rec" label="05" title="Recommendation">
            {f.recommendation ? (
              <div className="flex max-w-3xl items-start gap-3">
                <Lightbulb className="mt-1 size-4 shrink-0 text-attention" aria-hidden="true" />
                <div>
                  <p className="text-[17px] font-semibold text-ink">{RECOMMENDATION_LABEL[f.recommendation.action]}</p>
                  <p className="mt-1 text-[14px] leading-relaxed text-ink-2">{f.recommendation.reason}</p>
                  <p className="mt-2 text-[12.5px] text-muted">{f.recommendation.limitations}</p>
                </div>
              </div>
            ) : (
              <p className="text-[13px] text-muted">The recommendation engine produced no hint for this finding.</p>
            )}
          </Section>

          <Section
            id="s-trust"
            label="06"
            title="TRUST-SAT verification"
            aside={runVerification ? `checked ${fmtDateTime(runVerification.verifiedAt)}` : undefined}
          >
            <div className="grid gap-8 2xl:grid-cols-[minmax(0,1fr)_16rem]">
              <ProvenanceChain nodes={provenance} label="Provenance chain for this finding" />
              <dl className="grid gap-x-6 gap-y-3 border-line text-[12.5px] sm:grid-cols-2 2xl:block 2xl:space-y-3 2xl:border-l 2xl:pl-6">
                {[
                  ["Signature", receipt ? `${receipt.algorithmId}, ${receipt.signatureBytes} bytes` : "No receipt", f.trust === "verified"],
                  ["Digest", f.trust === "verified" ? "Live row matches signed digest" : f.trustReason, f.trust === "verified"],
                  ["Run", runVerification?.run?.ok ? "Run signature verified" : "Run not verified", Boolean(runVerification?.run?.ok)],
                  ["Ledger", audit?.ledger_integrity?.chain_ok ? "Decision ledger chain intact" : "Ledger not checked", Boolean(audit?.ledger_integrity?.chain_ok)],
                ].map(([k, v, ok]) => (
                  <div key={k as string}>
                    <dt className="label flex items-center gap-1.5">
                      {ok ? <ShieldCheck className="size-3.5 text-brand" aria-hidden="true" /> : null}
                      {k}
                    </dt>
                    <dd className="mt-0.5 text-ink-2">{v}</dd>
                  </div>
                ))}
                <p className="pt-1 text-[11.5px] leading-relaxed text-muted">
                  Verification detects tampering at the time it runs. It does not make stored records tamper-proof.
                </p>
              </dl>
            </div>
          </Section>
        </div>

        <aside aria-label="Assessment and decision" className="space-y-4 lg:sticky lg:top-6 lg:self-start">
          <section aria-labelledby="conf-h" className="rounded-md border border-line bg-paper px-4 py-4">
            <h2 id="conf-h" className="label mb-3">
              Confidence
            </h2>
            <ConfidenceDisplay confidence={f.confidence} />
          </section>
          <ReviewPanel
            findingId={f.id}
            contentDigest={f.contentDigest}
            canRecord={can(session.user.role, "decision.record")}
            roleLabel={ROLE_LABEL[session.user.role]}
            sessionMode={session.mode}
            history={history}
          />
        </aside>
      </div>
    </div>
  );
}
