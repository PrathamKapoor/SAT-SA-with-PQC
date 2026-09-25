import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, GitMerge, TrendingUp } from "lucide-react";
import { CompletenessStrip } from "@/components/domain/entity-bits";
import { FindingRow, toRowData } from "@/components/domain/finding-row";
import { FamilyLabel, TrustTag } from "@/components/ui/badges";
import { RiskBreakdown, RiskScore } from "@/components/ui/data";
import { KeyValue, Panel, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { getSource } from "@/lib/api";
import { fmtDate, fmtDateTime, fmtNum, prose, shortDigest, sourceName } from "@/lib/domain/format";
import { DIMENSION_LABEL, FAMILY_LABEL, familyOf, SUPERVISOR_ACTION_LABEL, type FindingFamily } from "@/lib/domain/labels";
import { loadEntityViews } from "@/lib/model";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const e = (await loadEntityViews()).find((x) => x.entity.id === id);
  return { title: e?.entity.displayName ?? "Entity" };
}

export default async function EntityDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const all = await loadEntityViews();
  const e = all.find((x) => x.entity.id === id);
  if (!e) notFound();
  const src = getSource();
  const [data, supervisor, runs] = await Promise.all([
    src.getSecurityData(id),
    e.run ? src.getSupervisorDecision(e.run.id) : Promise.resolve(null),
    src.listRuns(id),
  ]);

  const byFamily = new Map<FindingFamily, number>();
  for (const f of e.findings) byFamily.set(f.family, (byFamily.get(f.family) ?? 0) + 1);
  const families = [...byFamily.entries()].sort((a, b) => b[1] - a[1]);
  const peer = e.findings.filter((f) => f.family === "peer_benchmark");
  const corroborated = (e.risk?.correlation_clusters ?? []).filter((c) => c.corroborated);
  const nativeOf = (subject: string) =>
    data.alerts.find((a) => a.id === subject)?.nativeId ?? data.cases.find((c) => c.id === subject)?.nativeId ?? data.assets.find((a) => a.id === subject)?.nativeId ?? subject;
  const top = (e.risk?.dimensions ?? []).filter((d) => d.score > 0).sort((a, b) => b.score - a.score);

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <Link href="/workbench/entities" className="inline-flex items-center gap-1.5 text-[13px] text-muted hover:text-ink">
        <ArrowLeft className="size-3.5" aria-hidden="true" />
        Entities
      </Link>

      <header className="mt-4 grid gap-6 pb-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
        <div>
          <p className="label">
            Priority {e.priorityRank ?? "n/a"} of {all.length}
            {e.assessment && ` · ${fmtDate(e.assessment.periodStart)} to ${fmtDate(e.assessment.periodEnd)}`}
          </p>
          <h1 className="mt-2 text-[34px] leading-none font-semibold tracking-[-0.03em] text-ink md:text-[44px]">{e.entity.displayName}</h1>
          <p className="mt-3 text-[13.5px] text-muted">
            <span className="capitalize">{e.entity.sector || "Unspecified sector"}</span> · {e.entity.environmentClass || "unspecified environment"} · {e.findings.length} signal findings
          </p>
        </div>
        <div className="flex items-end gap-8">
          <div>
            <p className="label">Risk</p>
            <div className="mt-1">
              <RiskScore score={e.risk?.total_score ?? null} size="lg" bucket={e.risk?.confidence_bucket} />
            </div>
          </div>
          <TrustTag state={e.trust} />
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <Panel className="px-5 py-5" aria-labelledby="posture-h">
          <SectionHeader id="posture-h" title="Risk posture" aside="score / dimension weight" />
          {e.risk ? <RiskBreakdown dimensions={e.risk.dimensions} /> : <EmptyState title="No risk profile">No completed analysis run for this entity.</EmptyState>}
          {top.length > 0 && (
            <div className="mt-5 border-t border-line pt-4">
              <p className="label mb-2">Where the risk comes from</p>
              <ul className="space-y-1.5 text-[13px] text-ink-2">
                {top.slice(0, 3).map((d) => (
                  <li key={d.name}>
                    <span className="font-medium text-ink">{DIMENSION_LABEL[d.name]}</span> <span className="num text-muted">{fmtNum(d.score, 1)}/{d.weight}</span>: {prose(d.rationale)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Panel>

        <div className="grid gap-6">
          <Panel className="px-5 py-5" aria-labelledby="areas-h">
            <SectionHeader id="areas-h" title="Operational weaknesses" aside="by finding family" />
            {families.length ? (
              <ul className="space-y-2">
                {families.map(([fam, n]) => (
                  <li key={fam} className="flex items-center justify-between gap-3">
                    <FamilyLabel family={fam} />
                    <span className="flex flex-1 items-center gap-2">
                      <span aria-hidden="true" className="h-px flex-1 border-t border-dotted border-line-2" />
                      <span className="num text-[13px] font-semibold text-ink">{n}</span>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-muted">No signal findings.</p>
            )}
          </Panel>
          <Panel className="px-5 py-5" aria-labelledby="evid-h">
            <SectionHeader id="evid-h" title="Evidence completeness" aside={`${e.completeness.present.length} of 6 categories`} />
            <CompletenessStrip submission={e.submission} showLabels />
          </Panel>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Panel className="px-5 py-5" aria-labelledby="peer-h">
          <SectionHeader id="peer-h" title="Peer comparison" />
          {peer.length ? (
            <ul className="space-y-3">
              {peer.map((f) => (
                <li key={f.id}>
                  <Link href={`/workbench/findings/${f.id}`} className="text-[13px] leading-relaxed text-ink-2 hover:text-brand">
                    {f.rationale}
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] leading-relaxed text-muted">
              No peer-deviation finding. Either the entity sits within its cohort, or the cohort was too small for the peer benchmark worker to compare.
            </p>
          )}
        </Panel>

        <Panel className="px-5 py-5" aria-labelledby="corr-h">
          <SectionHeader id="corr-h" title="Corroborated records" aside={<GitMerge className="size-4 text-faint" aria-hidden="true" />} />
          {corroborated.length ? (
            <ul className="space-y-2.5">
              {corroborated.slice(0, 5).map((c) => (
                <li key={c.subject} className="text-[13px]">
                  <span className="font-mono font-medium text-ink">{nativeOf(c.subject)}</span>
                  <span className="text-muted">
                    {" "}
                    flagged by {c.rule_families.map((r) => FAMILY_LABEL[familyOf(r)] ?? r).join(", ")}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] leading-relaxed text-muted">No record was flagged by more than one independent detector family.</p>
          )}
          <p className="mt-3 text-[11.5px] text-muted">Independent detector families agreeing on one record strengthens the evidence.</p>
        </Panel>

        <Panel className="px-5 py-5" aria-labelledby="trend-h">
          <SectionHeader id="trend-h" title="Trend" aside={<TrendingUp className="size-4 text-faint" aria-hidden="true" />} />
          {runs.length > 1 ? (
            <p className="text-[13px] text-muted">{runs.length} analysis runs on record.</p>
          ) : (
            <p className="text-[13px] leading-relaxed text-muted">
              One assessment period on record. Drift against a previous period becomes available after this entity&rsquo;s next submission; the drift worker abstains until then.
            </p>
          )}
        </Panel>
      </div>

      <section aria-labelledby="ef-h" className="mt-8">
        <SectionHeader id="ef-h" title="Findings" aside={`${e.findings.length} in the latest run`} />
        {e.findings.length ? (
          <ul className="rounded-md border border-line bg-paper">
            {e.findings.map((f) => (
              <FindingRow key={f.id} f={toRowData(f)} />
            ))}
          </ul>
        ) : (
          <EmptyState title="No signal findings for this entity" />
        )}
      </section>

      <section aria-labelledby="run-h" className="mt-8 grid gap-6 lg:grid-cols-2">
        <Panel className="px-5 py-5">
          <SectionHeader id="run-h" title="Latest analysis run" />
          {e.run ? (
            <KeyValue
              items={[
                ["Run", <span key="r" className="font-mono text-[12.5px]">{e.run.id}</span>],
                ["Status", e.run.status],
                ["Completed", fmtDateTime(e.run.finishedAt)],
                ["Workers", `${e.run.summary.workers?.length ?? 0} (${e.run.summary.failed_jobs?.length ?? 0} failed)`],
                ["Snapshot digest", <span key="d" className="font-mono text-[12.5px]">{shortDigest(e.run.snapshotDigest, 16)}</span>],
                ["Supervisor proposal", supervisor ? `${SUPERVISOR_ACTION_LABEL[supervisor.action] ?? supervisor.action} (human decides)` : "None"],
              ]}
            />
          ) : (
            <p className="text-[13px] text-muted">No analysis run.</p>
          )}
        </Panel>
        <Panel className="px-5 py-5">
          <SectionHeader title="Submission" as="h3" />
          {e.submission ? (
            <KeyValue
              items={[
                ["Source", sourceName(e.submission.sourceSystem)],
                ["Received", fmtDate(e.submission.receivedAt)],
                ["Ingest", e.submission.ingestStatus],
                ["Files", `${Object.keys(e.submission.fileDigests).length} (SHA3-256 each)`],
              ]}
            />
          ) : (
            <p className="text-[13px] text-muted">No submission.</p>
          )}
        </Panel>
      </section>
    </div>
  );
}
