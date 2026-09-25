import type { Metadata } from "next";
import Link from "next/link";
import { Check, FileText, X } from "lucide-react";
import { Tag } from "@/components/ui/badges";
import { DataTable } from "@/components/ui/data";
import { Metric, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { CONTROLLED_BENCHMARK as CB } from "@/content/documented";
import { getSource } from "@/lib/api";
import { fmtNum, fmtPct } from "@/lib/domain/format";
import { fmtMeasure, measureFor } from "@/lib/domain/measures";
import { loadFindingViews } from "@/lib/model";

export const metadata: Metadata = { title: "Benchmarks" };

function Source({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-3 flex items-center gap-1.5 text-[11.5px] text-muted">
      <FileText className="size-3.5" aria-hidden="true" />
      {children}
    </p>
  );
}

export default async function BenchmarksPage() {
  const [findings, validation] = await Promise.all([loadFindingViews(), getSource().getValidation()]);
  const peer = findings.filter((f) => f.family === "peer_benchmark" && f.state === "signal");
  const comp = validation?.composition ?? [];

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Analytics"
        title="Benchmarks"
        description="Peer comparison from the current period, the synthetic ground-truth checks the backend runs, and the documented controlled benchmark. Each is labelled with what it does and does not show."
      />

      <section aria-labelledby="peer-h">
        <SectionHeader id="peer-h" label="Current period" title="Peer deviation" aside="trimmed cohort median, same sector" />
        {peer.length ? (
          <Panel className="px-5 py-2">
            <DataTable
              caption="Peer deviation findings"
              rows={peer}
              rowKey={(f) => f.id}
              columns={[
                { key: "e", header: "Entity", cell: (f) => <span className="font-medium text-ink">{f.entityName}</span> },
                {
                  key: "m",
                  header: "Metric",
                  cell: (f) => (
                    <Link href={`/workbench/findings/${f.id}`} className="hover:text-brand">
                      {f.ruleOrCategory.split(".")[1]?.replaceAll("_", " ")}
                    </Link>
                  ),
                },
                { key: "o", header: "Entity value", align: "right", cell: (f) => <span className="num font-medium text-ink">{fmtMeasure(f.statistic, measureFor(f.ruleOrCategory).unit)}</span> },
                { key: "p", header: "Peer median", align: "right", cell: (f) => <span className="num">{fmtMeasure(f.threshold, measureFor(f.ruleOrCategory).unit)}</span> },
                {
                  key: "d",
                  header: "Deviation",
                  align: "right",
                  cell: (f) =>
                    f.statistic != null && f.threshold ? (
                      <span className="num text-attention-strong">
                        {f.statistic >= f.threshold ? "+" : ""}
                        {fmtPct((f.statistic - f.threshold) / f.threshold)}
                      </span>
                    ) : (
                      "n/a"
                    ),
                },
              ]}
            />
          </Panel>
        ) : (
          <EmptyState title="No peer deviation in this period" />
        )}
      </section>

      <section aria-labelledby="cb-h" className="mt-10">
        <SectionHeader id="cb-h" label="Documented" title="Controlled supervisory benchmark" aside={<Tag tone="neutral">Synthetic</Tag>} />
        <Panel className="px-5 py-5">
          <p className="max-w-3xl text-[13px] leading-relaxed text-ink-2">{CB.scope}</p>
          <dl className="mt-5 grid grid-cols-2 gap-6 md:grid-cols-5">
            <Metric label="Precision" value={fmtNum(CB.scenarioCorpus.precision, 2)} detail={`${CB.scenarioCorpus.tp} tp, ${CB.scenarioCorpus.fp} fp`} />
            <Metric label="Recall" value={fmtNum(CB.scenarioCorpus.recall, 2)} detail={`${CB.scenarioCorpus.fn} missed`} />
            <Metric label="F1" value={fmtNum(CB.scenarioCorpus.f1, 2)} />
            <Metric label="Action alignment" value={`${CB.scenarioCorpus.actionAlignment.correct}/${CB.scenarioCorpus.actionAlignment.total}`} detail="mixed scenario missed" />
            <Metric label="Recall at top 10%" value={fmtNum(CB.prioritization[0].satsa, 2)} detail={`random ${CB.prioritization[0].random}`} />
          </dl>
          <p className="mt-4 text-[12.5px] text-muted">
            Precision is depressed by other detectors firing on the same fixtures. Those extra families are counted as false positives and reported, not suppressed.
          </p>

          <div className="mt-6 grid gap-8 lg:grid-cols-2">
            <div>
              <h3 className="label mb-2">Closure-time baselines</h3>
              <DataTable
                dense
                caption="Closure-time detector comparison"
                rows={[...CB.closureBaselines]}
                rowKey={(r) => r.detector}
                columns={[
                  { key: "d", header: "Detector", cell: (r) => <span className="text-ink">{r.detector}</span> },
                  { key: "t", header: "TP / FP / FN", cell: (r) => <span className="num">{`${r.tp} / ${r.fp} / ${r.fn}`}</span> },
                  { key: "p", header: "Precision", align: "right", cell: (r) => <span className="num">{r.precision == null ? "undefined" : fmtNum(r.precision, 2)}</span> },
                  { key: "r", header: "Recall", align: "right", cell: (r) => <span className="num">{fmtNum(r.recall, 2)}</span> },
                ]}
              />
              <p className="mt-2 text-[12px] text-muted">{CB.closureNote}</p>
            </div>
            <div>
              <h3 className="label mb-2">Prioritization lift</h3>
              <DataTable
                dense
                caption="Recall at top K percent against a random ordering"
                rows={[...CB.prioritization]}
                rowKey={(r) => String(r.k)}
                columns={[
                  { key: "k", header: "Top K", cell: (r) => `${r.k}%` },
                  { key: "s", header: "SAT-SA recall", align: "right", cell: (r) => <span className="num font-medium text-ink">{fmtNum(r.satsa, 2)}</span> },
                  { key: "r", header: "Random mean", align: "right", cell: (r) => <span className="num">{fmtNum(r.random, 4)}</span> },
                  { key: "l", header: "Lift", align: "right", cell: (r) => <span className="num">{r.lift}x</span> },
                ]}
              />
              <p className="mt-2 text-[12px] text-muted">{CB.prioritizationNote}</p>
            </div>
          </div>
          <Source>Source: {CB.source}</Source>
        </Panel>
      </section>

      <section aria-labelledby="val-h" className="mt-10">
        <SectionHeader id="val-h" label="Backend" title="Synthetic ground-truth checks" aside="sat-sa validate" />
        {comp.length ? (
          <Panel className="px-5 py-2">
            <DataTable
              dense
              caption="Composition validation cases"
              rows={comp}
              rowKey={(c) => c.case_id}
              columns={[
                { key: "c", header: "Scenario", cell: (c) => <span className="font-mono text-[12.5px] text-ink">{c.case_id}</span> },
                { key: "e", header: "Expected signal", cell: (c) => <span className="text-[12.5px]">{c.expected_signals.join(", ") || "none"}</span> },
                { key: "a", header: "Expected action", cell: (c) => <span className="font-mono text-[12px]">{c.expected_action}</span> },
                {
                  key: "ok",
                  header: "Agrees",
                  align: "right",
                  cell: (c) =>
                    c.signals_ok && c.action_ok ? (
                      <Check className="ml-auto size-4 text-brand" aria-label="agrees" />
                    ) : (
                      <X className="ml-auto size-4 text-critical" aria-label="disagrees" />
                    ),
                },
              ]}
            />
          </Panel>
        ) : (
          <EmptyState title="No validation report" />
        )}
        <p className="mt-2 text-[12px] text-muted">
          These cases check the scenario catalogue against its declared expectations. They are a consistency check, not an accuracy measurement; the controlled benchmark above is the
          measured result.
        </p>
      </section>
    </div>
  );
}
