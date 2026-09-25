import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { PrintButton } from "@/components/domain/print-button";
import { RiskBreakdown } from "@/components/ui/data";
import { getSource } from "@/lib/api";
import { can } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { fmtDate, fmtDateTime, fmtNum, fmtPct, fmtPeriod, shortDigest, sourceName } from "@/lib/domain/format";
import { CATEGORY_LABEL, CONFIDENCE_BUCKET_LABEL, FAMILY_LABEL, RECOMMENDATION_LABEL, ruleTitle } from "@/lib/domain/labels";
import { BACKEND_ACTION_LABEL } from "@/lib/domain/review";
import { loadCore, loadEntityViews } from "@/lib/model";
import { EVIDENCE_CATEGORIES } from "@/lib/types/domain";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const e = (await loadEntityViews()).find((x) => x.entity.id === id);
  return { title: e ? `Report ${e.entity.displayName}` : "Report" };
}

function H({ n, children }: { n: string; children: React.ReactNode }) {
  return (
    <h2 className="mt-10 mb-3 flex items-baseline gap-3 border-b border-ink pb-1.5 text-[15px] font-semibold text-ink break-after-avoid">
      <span className="font-mono text-[12px] text-muted">{n}</span>
      {children}
    </h2>
  );
}

export default async function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const session = (await getSession())!;
  const e = (await loadEntityViews()).find((x) => x.entity.id === id);
  if (!e) notFound();
  const core = await loadCore();
  const decisions = await getSource().listReviewDecisions();
  const v = e.run ? core.verifications.get(e.run.id) : null;
  const findingIds = new Set(e.findings.map((f) => f.id));
  const entityDecisions = decisions.filter((d) => findingIds.has(d.findingId));
  const recs = new Map<string, number>();
  for (const f of e.findings) if (f.recommendation) recs.set(f.recommendation.action, (recs.get(f.recommendation.action) ?? 0) + 1);
  const canExport = can(session.user.role, "report.export");

  return (
    <div className="mx-auto max-w-[960px] px-4 py-6 md:px-8">
      <div className="no-print mb-6 flex items-center justify-between gap-4">
        <Link href="/workbench/reports" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
          <ArrowLeft className="size-3.5" aria-hidden="true" />
          Reports
        </Link>
        <PrintButton disabled={!canExport} reason="Exporting reports requires the report.export permission" />
      </div>

      <article className="print-page rounded-md border border-line bg-paper px-8 py-10 md:px-12">
        <header className="border-b-2 border-ink pb-6">
          <p className="label">SAT-SA supervisory report</p>
          <h1 className="mt-3 text-[34px] leading-none font-semibold tracking-[-0.03em] text-ink">{e.entity.displayName}</h1>
          <dl className="mt-5 grid grid-cols-2 gap-x-8 gap-y-2 text-[12.5px] sm:grid-cols-4">
            <div>
              <dt className="text-muted">Assessment period</dt>
              <dd className="text-ink">{e.assessment ? fmtPeriod(e.assessment.periodStart, e.assessment.periodEnd) : "n/a"}</dd>
            </div>
            <div>
              <dt className="text-muted">Sector / environment</dt>
              <dd className="text-ink capitalize">
                {e.entity.sector || "n/a"} / {e.entity.environmentClass || "n/a"}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Analysis run</dt>
              <dd className="font-mono text-[11.5px] text-ink">{e.run?.id ?? "n/a"}</dd>
            </div>
            <div>
              <dt className="text-muted">Analysis completed</dt>
              <dd className="text-ink">{fmtDateTime(e.run?.finishedAt)}</dd>
            </div>
          </dl>
        </header>

        <H n="1">Summary</H>
        <p className="text-[14px] leading-relaxed text-ink">
          {e.entity.displayName} ranks {e.priorityRank ?? "n/a"} of {core.entities.length} entities by supervisory priority, with a risk score of{" "}
          <strong>{fmtNum(e.risk?.total_score ?? null, 1)}/100</strong> at {CONFIDENCE_BUCKET_LABEL[e.risk?.confidence_bucket ?? ""]?.toLowerCase() ?? "unknown"} confidence. The
          analysis raised <strong>{e.findings.length}</strong> signal finding{e.findings.length === 1 ? "" : "s"}; {entityDecisions.length} ha
          {entityDecisions.length === 1 ? "s" : "ve"} a recorded supervisory decision.
        </p>

        <H n="2">Risk</H>
        {e.risk ? <RiskBreakdown dimensions={e.risk.dimensions} compact /> : <p className="text-[13px] text-muted">No risk profile.</p>}

        <H n="3">Findings</H>
        <table className="w-full text-left text-[12.5px]">
          <thead>
            <tr className="border-b border-line text-muted">
              <th scope="col" className="py-1.5 pr-3 font-normal">
                Finding
              </th>
              <th scope="col" className="py-1.5 pr-3 font-normal">
                Family
              </th>
              <th scope="col" className="py-1.5 pr-3 font-normal">
                Severity
              </th>
              <th scope="col" className="py-1.5 pr-3 text-right font-normal">
                Confidence
              </th>
              <th scope="col" className="py-1.5 text-right font-normal">
                Evidence
              </th>
            </tr>
          </thead>
          <tbody>
            {e.findings.map((f) => (
              <tr key={f.id} className="border-b border-line/60 break-inside-avoid">
                <td className="py-1.5 pr-3 text-ink">{ruleTitle(f.ruleOrCategory)}</td>
                <td className="py-1.5 pr-3">{FAMILY_LABEL[f.family]}</td>
                <td className="py-1.5 pr-3 capitalize">{f.severity ?? "n/a"}</td>
                <td className="num py-1.5 pr-3 text-right">{fmtPct(f.confidence?.overall ?? null)}</td>
                <td className="num py-1.5 text-right">{f.evidenceCount}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <H n="4">Evidence</H>
        <p className="text-[12.5px] text-muted">
          {e.submission ? `${sourceName(e.submission.sourceSystem)}, received ${fmtDate(e.submission.receivedAt)}, snapshot ${shortDigest(e.submission.snapshotDigest, 16)}.` : "No submission."}
        </p>
        <ul className="mt-2 grid grid-cols-2 gap-x-8 gap-y-1 text-[12.5px] sm:grid-cols-3">
          {EVIDENCE_CATEGORIES.map((c) => (
            <li key={c} className="flex justify-between border-b border-line/60 py-1">
              <span>{CATEGORY_LABEL[c]}</span>
              <span className="num text-ink">{e.submission?.declaredCounts[c] ?? 0}</span>
            </li>
          ))}
        </ul>

        <H n="5">Recommendations</H>
        {recs.size ? (
          <ul className="space-y-1 text-[13px]">
            {[...recs.entries()].map(([a, n]) => (
              <li key={a}>
                <span className="font-medium text-ink">{RECOMMENDATION_LABEL[a as keyof typeof RECOMMENDATION_LABEL] ?? a}</span> <span className="text-muted">for {n} finding{n === 1 ? "" : "s"}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-muted">None.</p>
        )}
        <p className="mt-2 text-[12px] text-muted">Recommendations are bounded hints. The supervisor remains responsible for the determination.</p>

        <H n="6">Decisions</H>
        {entityDecisions.length ? (
          <ul className="space-y-1.5 text-[13px]">
            {entityDecisions.map((d) => (
              <li key={d.id}>
                <span className="font-medium text-ink">{BACKEND_ACTION_LABEL[d.action]}</span> by {d.principalIdentityId}: {d.reason}{" "}
                <span className="text-muted">({fmtDate(d.occurredAt)})</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[13px] text-muted">No supervisory decision has been recorded for this entity&rsquo;s findings.</p>
        )}

        <H n="7">Trust verification</H>
        <p className="text-[13px] leading-relaxed text-ink">
          Run signature: <strong>{v?.run?.ok ? "verified" : "not verified"}</strong>. Findings verified: <strong>{v ? `${v.findings.filter((x) => x.ok).length} of ${v.findings.length}` : "n/a"}</strong>.
          Signatures are ML-DSA-65 over SHA3-256 content digests{v ? `, checked ${fmtDateTime(v.verifiedAt)}` : ""}.
        </p>
      </article>
    </div>
  );
}
