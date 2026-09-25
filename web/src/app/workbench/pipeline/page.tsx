import type { Metadata } from "next";
import { PipelineStrip, type PipelineStage } from "@/components/domain/pipeline-strip";
import { PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { getSource } from "@/lib/api";
import { fmtDateTime, fmtDuration } from "@/lib/domain/format";
import { workerLabel } from "@/lib/domain/labels";
import { loadCore } from "@/lib/model";
import type { ObservationState } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Pipeline" };

const CELL: Record<ObservationState | "failed" | "none", { cls: string; label: string; short: string }> = {
  signal: { cls: "bg-attention text-white", label: "Signal", short: "S" },
  no_signal: { cls: "bg-sunken text-muted", label: "Clear", short: "" },
  insufficient_data: { cls: "border border-dashed border-info/60 text-info", label: "Abstained", short: "A" },
  not_applicable: { cls: "bg-canvas text-faint", label: "Not applicable", short: "" },
  error: { cls: "bg-critical text-white", label: "Error", short: "E" },
  failed: { cls: "bg-critical text-white", label: "Failed", short: "F" },
  none: { cls: "bg-paper text-faint", label: "Not run", short: "" },
};

export default async function PipelinePage() {
  const src = getSource();
  const [core, observations, jobs, receipts] = await Promise.all([loadCore(), src.listObservations(), src.listJobs(), src.listTrustReceipts()]);
  const names = new Map(core.entities.map((e) => [e.id, e.displayName]));
  const workers = [...new Set(core.runs.flatMap((r) => r.summary.workers ?? []))];
  const records = core.submissions.reduce((n, s) => n + Object.values(s.declaredCounts).reduce((a, b) => a + (b ?? 0), 0), 0);
  const signal = core.findings.filter((f) => f.state === "signal").length;

  const stages: PipelineStage[] = [
    { key: "s", label: "Submission", value: core.submissions.length, detail: "received", state: "ok" },
    { key: "i", label: "Ingestion", value: core.submissions.filter((s) => s.ingestStatus === "accepted").length, detail: "accepted", state: "ok" },
    { key: "n", label: "Normalization", value: records, detail: "canonical records", state: "ok" },
    { key: "w", label: "Workers", value: jobs.length, detail: `${jobs.filter((j) => j.status === "failed").length} failed`, state: jobs.some((j) => j.status === "failed") ? "failed" : "ok" },
    { key: "c", label: "Correlation and risk", value: core.runs.length, detail: "risk profiles", state: "ok" },
    { key: "f", label: "Findings", value: signal, detail: "signal", state: "ok" },
    { key: "t", label: "Trust", value: receipts.length, detail: "receipts signed", state: "ok" },
    { key: "r", label: "Human review", value: core.decisions.length, detail: "decisions", state: core.decisions.length ? "ok" : "idle" },
  ];

  const state = (runId: string, worker: string): keyof typeof CELL => {
    const job = jobs.find((j) => j.runId === runId && j.workerName === worker);
    if (job?.status === "failed") return "failed";
    const o = observations.find((x) => x.runId === runId && x.workerName === worker);
    return o ? o.state : "none";
  };

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Analytics"
        title="Pipeline"
        description="The periodic assessment cycle, from submission to human review. Every run executes the same registered workers in a single transaction, then signs its outputs."
      />

      <Panel className="px-5 py-5">
        <PipelineStrip stages={stages} label="Assessment pipeline" />
      </Panel>

      <section aria-labelledby="mx-h" className="mt-10">
        <SectionHeader id="mx-h" title="Worker outcomes by run" aside={`${core.runs.length} runs × ${workers.length} workers`} />
        <Panel className="overflow-x-auto px-5 py-4">
          <table className="border-separate border-spacing-[3px] text-left">
            <caption className="sr-only">Outcome of each analytical worker in each run</caption>
            <thead>
              <tr>
                <th scope="col" className="label pr-4 align-bottom font-normal">
                  Entity
                </th>
                {workers.map((w) => (
                  <th key={w} scope="col" className="h-36 w-7 align-bottom font-normal">
                    <span className="block origin-bottom-left translate-x-3.5 -rotate-60 text-[11.5px] whitespace-nowrap text-ink-2">{workerLabel(w)}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {core.runs.map((r) => (
                <tr key={r.id}>
                  <th scope="row" className="pr-4 text-[13px] font-medium whitespace-nowrap text-ink">
                    {names.get(r.entityId)}
                  </th>
                  {workers.map((w) => {
                    const s = CELL[state(r.id, w)];
                    return (
                      <td key={w} title={`${workerLabel(w)}: ${s.label}`} className={cn("size-7 rounded-[3px] text-center font-mono text-[10.5px] font-semibold", s.cls)}>
                        {s.short}
                        <span className="sr-only">{s.label}</span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-[12px] text-muted" aria-label="Legend">
            {(["signal", "no_signal", "insufficient_data", "failed"] as const).map((k) => (
              <li key={k} className="flex items-center gap-1.5">
                <span aria-hidden="true" className={cn("flex size-4 items-center justify-center rounded-[3px] font-mono text-[9px] font-semibold", CELL[k].cls)}>
                  {CELL[k].short}
                </span>
                {CELL[k].label}
              </li>
            ))}
          </ul>
        </Panel>
      </section>

      <section aria-labelledby="runs-h" className="mt-10">
        <SectionHeader id="runs-h" title="Runs" />
        <Panel className="px-5 py-3">
          <ul className="divide-y divide-line">
            {core.runs.map((r) => (
              <li key={r.id} className="grid gap-x-6 gap-y-1 py-2.5 text-[12.5px] sm:grid-cols-[minmax(0,10rem)_minmax(0,1fr)_8rem_8rem_8rem]">
                <span className="font-medium text-ink">{names.get(r.entityId)}</span>
                <span className="mono-id truncate">{r.id}</span>
                <span className="capitalize text-ink-2">{r.status}</span>
                <span className="text-muted">{r.startedAt && r.finishedAt ? fmtDuration(r.finishedAt - r.startedAt) : "n/a"}</span>
                <span className="text-muted">{fmtDateTime(r.finishedAt)}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </section>
    </div>
  );
}
