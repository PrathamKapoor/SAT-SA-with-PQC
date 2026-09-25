import type { Metadata } from "next";
import Link from "next/link";
import { ChevronRight, ShieldCheck, ShieldAlert } from "lucide-react";
import { AttentionQueue, AwaitingHeadline } from "@/components/domain/attention-queue";
import { toRowData } from "@/components/domain/finding-row";
import { PipelineStrip, type PipelineStage } from "@/components/domain/pipeline-strip";
import { Meter } from "@/components/ui/data";
import { getSource } from "@/lib/api";
import { DIMENSION_LABEL } from "@/lib/domain/labels";
import { fmtDateTime, fmtNum } from "@/lib/domain/format";
import { byPriority, loadCore, loadEntityViews, loadFindingViews } from "@/lib/model";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Workbench" };

function PanelTitle({ children, href, linkLabel }: { children: React.ReactNode; href?: string; linkLabel?: string }) {
  return (
    <div className="flex h-11 shrink-0 items-center justify-between border-b border-line px-5">
      <h2 className="text-[13.5px] font-semibold text-ink">{children}</h2>
      {href && (
        <Link href={href} className="inline-flex items-center gap-0.5 text-[12.5px] text-muted hover:text-ink">
          {linkLabel}
          <ChevronRight className="size-3.5" aria-hidden="true" />
        </Link>
      )}
    </div>
  );
}

export default async function WorkbenchPage() {
  const src = getSource();
  const [core, findings, entities, audit] = await Promise.all([loadCore(), loadFindingViews(), loadEntityViews(), src.getMetaAudit()]);
  const signal = findings.filter((f) => f.state === "signal").sort(byPriority);
  const rows = signal.map(toRowData);

  const accepted = core.submissions.filter((s) => s.ingestStatus === "accepted").length;
  const records = core.submissions.reduce((n, s) => n + Object.values(s.declaredCounts).reduce((a, b) => a + (b ?? 0), 0), 0);
  const failedJobs = (await src.listJobs()).filter((j) => j.status === "failed").length;
  const jobs = core.runs.reduce((n, r) => n + (r.summary.workers?.length ?? 0), 0);
  const receipts = (await src.listTrustReceipts()).length;
  const completedRuns = core.runs.filter((r) => r.status === "completed").length;

  const pipeline: PipelineStage[] = [
    { key: "sub", label: "Submissions accepted", value: `${accepted}/${core.submissions.length}`, state: accepted === core.submissions.length ? "ok" : "attention" },
    { key: "rec", label: "Records normalized", value: records, state: "ok" },
    { key: "run", label: "Analysis runs completed", value: `${completedRuns}/${core.runs.length}`, state: completedRuns === core.runs.length ? "ok" : "attention" },
    { key: "job", label: "Worker jobs", value: jobs, detail: failedJobs ? `${failedJobs} failed` : "none failed", state: failedJobs ? "failed" : "ok" },
    { key: "fnd", label: "Signal findings", value: signal.length, state: "ok" },
    { key: "sig", label: "Trust receipts signed", value: receipts, state: "ok" },
    { key: "dec", label: "Recorded decisions", value: core.decisions.length, detail: "backend record", state: core.decisions.length ? "ok" : "idle" },
  ];

  const trustOk = audit?.fully_compliant ?? false;
  const verifiedAt = Math.max(0, ...[...core.verifications.values()].map((v) => v?.verifiedAt ?? 0));

  return (
    <div className="flex flex-col gap-4 p-4 md:p-5 lg:h-full lg:min-h-0 lg:overflow-hidden">
      <section aria-labelledby="posture" className="flex shrink-0 flex-wrap items-end justify-between gap-x-8 gap-y-3">
        <div className="min-w-0">
          <p className="label">Supervisory posture</p>
          <h1 id="posture" className="mt-1 text-[24px] leading-tight font-semibold tracking-[-0.025em] text-ink xl:text-[28px]">
            <AwaitingHeadline findings={rows} entities={entities.length} />
          </h1>
        </div>
        <dl className="flex gap-7">
          {[
            ["Entities", entities.length],
            ["Signal findings", signal.length],
            ["High severity", signal.filter((f) => f.severity === "high").length],
          ].map(([k, v]) => (
            <div key={k}>
              <dt className="label">{k}</dt>
              <dd className="num mt-0.5 text-[22px] leading-none font-semibold text-ink">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="grid gap-4 lg:min-h-0 lg:flex-1 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)] xl:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)_minmax(0,0.72fr)]">
        <section aria-label="Attention queue" className="relative flex min-h-[26rem] flex-col overflow-hidden rounded-md border border-line bg-paper lg:min-h-0">
          <PanelTitle href="/workbench/findings" linkLabel="Findings">
            Attention queue
          </PanelTitle>
          <div className="min-h-0 flex-1">
            <AttentionQueue findings={rows} limit={12} />
          </div>
        </section>

        <section aria-label="Entities requiring attention" className="relative flex flex-col overflow-hidden rounded-md border border-line bg-paper lg:min-h-0">
          <PanelTitle href="/workbench/entities" linkLabel="Entities">
            Entities by priority
          </PanelTitle>
          <ol className="relative min-h-0 flex-1 overflow-hidden">
            {entities.map((e) => {
              const top = e.risk?.dimensions.filter((d) => d.score > 0).sort((a, b) => b.score - a.score).slice(0, 2) ?? [];
              return (
                <li key={e.entity.id} className="border-b border-line/80 last:border-0">
                  <Link href={`/workbench/entities/${e.entity.id}`} className="group grid grid-cols-[1.25rem_minmax(0,1fr)_auto] items-center gap-x-3 px-5 py-3 hover:bg-canvas">
                    <span className="num text-[11.5px] text-faint">{String(e.priorityRank ?? "").padStart(2, "0")}</span>
                    <span className="min-w-0">
                      <span className="flex items-center gap-2">
                        <span className="truncate text-[13.5px] font-medium text-ink group-hover:text-brand-strong">{e.entity.displayName}</span>
                        {e.trust === "verified" ? (
                          <ShieldCheck className="size-3.5 shrink-0 text-brand" aria-label="Trust verified" />
                        ) : (
                          <ShieldAlert className="size-3.5 shrink-0 text-critical" aria-label="Trust not verified" />
                        )}
                      </span>
                      <span className="mt-1 block truncate text-[12px] text-muted">
                        {top.length ? top.map((d) => DIMENSION_LABEL[d.name]).join(", ") : "No weighted risk"}
                      </span>
                    </span>
                    <span className="w-24 text-right">
                      <span className="num text-[15px] font-semibold text-ink">{fmtNum(e.risk?.total_score ?? null, 1)}</span>
                      <span className="text-[11px] text-muted">/100</span>
                      <Meter value={e.risk?.total_score ?? null} max={100} label={`${e.entity.displayName} risk score`} tone={(e.risk?.total_score ?? 0) >= 30 ? "attention" : "brand"} className="mt-1" />
                    </span>
                  </Link>
                </li>
              );
            })}
          </ol>
          <p className="shrink-0 border-t border-line px-5 py-2.5 text-[11.5px] text-muted">
            Order is the backend entity priority: risk, confidence, recency and high-severity count.
          </p>
        </section>

        <div className="flex flex-col gap-4 lg:col-span-2 lg:grid lg:grid-cols-2 lg:min-h-0 xl:col-span-1 xl:flex xl:flex-col">
          <section aria-label="Pipeline state" className="flex flex-col rounded-md border border-line bg-paper xl:min-h-0 xl:flex-1">
            <PanelTitle href="/workbench/pipeline" linkLabel="Pipeline">
              Pipeline
            </PanelTitle>
            <div className="px-5 py-4">
              <PipelineStrip stages={pipeline} orientation="vertical" label="Assessment cycle" />
            </div>
          </section>

          <section aria-label="Trust state" className="rounded-md border border-line bg-paper">
            <PanelTitle href="/workbench/trust" linkLabel="TRUST-SAT">
              Trust
            </PanelTitle>
            <div className="px-5 py-4">
              <p className={cn("flex items-center gap-2 text-[14px] font-semibold", trustOk ? "text-brand-strong" : "text-critical")}>
                {trustOk ? <ShieldCheck className="size-4" aria-hidden="true" /> : <ShieldAlert className="size-4" aria-hidden="true" />}
                {trustOk ? "All records verify" : "Verification exceptions"}
              </p>
              {audit && (
                <dl className="mt-3 grid grid-cols-3 gap-2 text-[12px]">
                  <div>
                    <dt className="text-muted">Runs</dt>
                    <dd className="num font-semibold text-ink">
                      {audit.runs_ok}/{audit.runs_checked}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Findings</dt>
                    <dd className="num font-semibold text-ink">
                      {audit.findings_ok}/{audit.findings_checked}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-muted">Ledger</dt>
                    <dd className="font-semibold text-ink">{audit.ledger_integrity?.chain_ok ? "Intact" : "Broken"}</dd>
                  </div>
                </dl>
              )}
              <p className="mt-3 text-[11.5px] text-muted">ML-DSA-65 over SHA3-256 · checked {fmtDateTime(verifiedAt)}</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
