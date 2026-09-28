import type { Metadata } from "next";
import Link from "next/link";
import { FileText } from "lucide-react";
import { Tag } from "@/components/ui/badges";
import { DataTable } from "@/components/ui/data";
import { Metric, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { CONTROLLED_BENCHMARK as CB } from "@/content/documented";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { load } from "@/lib/api/guard";
import type { Finding } from "@/lib/api/types";
import { fmtNum, fmtPct } from "@/lib/domain/format";
import { familyOf } from "@/lib/domain/labels";
import { fmtMeasure, measureFor } from "@/lib/domain/measures";
import { entityName, loadCurrentFindings, loadPortfolio } from "@/lib/workbench/data";

type PeerRow = { finding: Finding; entity: string };

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
  const loaded = await load(async () => ({ current: await loadCurrentFindings(), portfolio: await loadPortfolio() }));
  const peer: PeerRow[] = loaded.ok
    ? loaded.data.current
        .filter((r) => familyOf(r.finding.rule_or_category) === "peer_benchmark" && r.finding.state === "signal")
        .map((r) => ({ finding: r.finding, entity: entityName(loaded.data.portfolio, r.priority.entity_id) }))
    : [];

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Analytics"
        title="Benchmarks"
        description="Peer comparison from each entity's current run, read live, and the documented controlled benchmark. Each is labelled with what it does and does not show."
      />

      <section aria-labelledby="peer-h">
        <SectionHeader id="peer-h" label="Current period" title="Peer deviation" aside="trimmed cohort median, same sector" />
        {!loaded.ok ? (
          <ApiErrorPanel error={loaded.error} context="Peer deviation" />
        ) : peer.length ? (
          <Panel className="px-5 py-2">
            <DataTable
              caption="Peer deviation findings"
              rows={peer}
              rowKey={(r) => r.finding.id}
              columns={[
                { key: "e", header: "Entity", cell: (r: PeerRow) => <span className="font-medium text-ink">{r.entity}</span> },
                {
                  key: "m",
                  header: "Metric",
                  cell: (r: PeerRow) => (
                    <Link href={`/workbench/findings/${r.finding.id}`} className="hover:text-brand">
                      {r.finding.rule_or_category.split(".")[1]?.replaceAll("_", " ")}
                    </Link>
                  ),
                },
                {
                  key: "o",
                  header: "Entity value",
                  align: "right",
                  cell: (r: PeerRow) => <span className="num font-medium text-ink">{fmtMeasure(r.finding.statistic, measureFor(r.finding.rule_or_category).unit)}</span>,
                },
                {
                  key: "p",
                  header: "Peer median",
                  align: "right",
                  cell: (r: PeerRow) => <span className="num">{fmtMeasure(r.finding.threshold, measureFor(r.finding.rule_or_category).unit)}</span>,
                },
                {
                  key: "d",
                  header: "Deviation",
                  align: "right",
                  cell: (r: PeerRow) =>
                    r.finding.statistic != null && r.finding.threshold ? (
                      <span className="num text-attention-strong">
                        {r.finding.statistic >= r.finding.threshold ? "+" : ""}
                        {fmtPct((r.finding.statistic - r.finding.threshold) / r.finding.threshold)}
                      </span>
                    ) : (
                      "n/a"
                    ),
                },
              ]}
            />
          </Panel>
        ) : (
          <EmptyState title="No peer deviation in current runs">Peer comparison needs at least three entities in the cohort.</EmptyState>
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
        <SectionHeader id="val-h" label="Offline tool" title="Synthetic ground-truth checks" aside="sat-sa validate" />
        <EmptyState title="Available in the offline tool">
          The scenario-catalogue consistency checks run with <span className="font-mono">sat-sa validate</span> against a local SQLite store. The hosted SAT-SA API does not serve
          them, so they are not shown here.
        </EmptyState>
      </section>
    </div>
  );
}
