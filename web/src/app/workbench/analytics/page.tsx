import type { Metadata } from "next";
import Link from "next/link";
import { FamilyLabel } from "@/components/ui/badges";
import { PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { getSource } from "@/lib/api";
import { fmtNum } from "@/lib/domain/format";
import { DIMENSION_LABEL, DIMENSION_ORDER, FAMILY_DESCRIPTION, workerLabel, type FindingFamily } from "@/lib/domain/labels";
import { loadCore, loadFindingViews } from "@/lib/model";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Analytics" };

/** Which family each of the 16 default workers reports into (satsa/analysis/run.py _default_workers). */
const WORKER_FAMILY: Record<string, FindingFamily> = {
  "fast-closure": "execution_gap",
  "ack-without-investigation": "execution_gap",
  "critical-without-escalation": "execution_gap",
  "repeated-investigation-pattern": "execution_gap",
  "recurring-without-remediation": "execution_gap",
  "potential-metric-gaming": "execution_gap",
  "negative-space": "negative_space",
  anomaly: "anomaly",
  "peer-benchmark": "peer_benchmark",
  "coverage-gap": "coverage_gap",
  drift: "drift",
  "cross-entity-insights": "cross_entity",
  "case-similarity": "case_similarity",
  "evidence-completeness": "evidence_completeness",
  "workflow-reconstruction": "workflow_reconstruction",
  "entity-asset-resolution": "entity_asset_resolution",
};

const FAMILY_ORDER: FindingFamily[] = [
  "execution_gap",
  "negative_space",
  "anomaly",
  "peer_benchmark",
  "coverage_gap",
  "drift",
  "cross_entity",
  "evidence_completeness",
  "case_similarity",
  "workflow_reconstruction",
  "entity_asset_resolution",
];

export default async function AnalyticsPage() {
  const src = getSource();
  const [core, findings, observations, weights] = await Promise.all([loadCore(), loadFindingViews(), src.listObservations(), src.getRiskWeights()]);
  const risks = (await Promise.all(core.entities.map((e) => src.getRiskProfile(e.id)))).filter((r) => r !== null);
  const signal = findings.filter((f) => f.state === "signal");
  const maxFamily = Math.max(1, ...FAMILY_ORDER.map((fam) => signal.filter((f) => f.family === fam).length));

  const families = FAMILY_ORDER.map((fam) => {
    const workers = Object.entries(WORKER_FAMILY)
      .filter(([, f]) => f === fam)
      .map(([w]) => w);
    const obs = observations.filter((o) => workers.includes(o.workerName));
    const fs = signal.filter((f) => f.family === fam);
    return {
      fam,
      workers,
      findings: fs.length,
      entities: new Set(fs.map((f) => f.entityId)).size,
      signal: obs.filter((o) => o.state === "signal").length,
      clear: obs.filter((o) => o.state === "no_signal").length,
      abstained: obs.filter((o) => o.state === "insufficient_data").length,
      runs: obs.length,
    };
  });

  const dimTotals = DIMENSION_ORDER.map((d) => ({
    d,
    weight: weights[d] ?? 0,
    contributed: risks.reduce((n, r) => n + (r.dimensions.find((x) => x.name === d)?.score ?? 0), 0),
  }));
  const maxContrib = Math.max(1, ...dimTotals.map((x) => x.contributed));
  const clusters = risks.flatMap((r) => r.correlation_clusters ?? []);

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Analytics"
        title="How findings are produced"
        description="Sixteen analytical workers run over each frozen submission. Each one is a transparent rule or robust statistic with a declared threshold. A worker either raises a signal, reports no signal, or abstains when the data cannot support a conclusion."
      />

      <section aria-labelledby="fam-h">
        <SectionHeader id="fam-h" title="Detector families" aside={`${signal.length} signal findings across ${core.runs.length} runs`} />
        <div className="overflow-hidden rounded-md border border-line bg-paper">
          <div className="hidden grid-cols-[minmax(0,16rem)_minmax(0,1fr)_minmax(0,14rem)_minmax(0,11rem)] gap-6 border-b border-line bg-canvas px-5 py-2 lg:grid" aria-hidden="true">
            {["Family", "What it detects", "Findings", "Run outcomes"].map((h) => (
              <span key={h} className="label">
                {h}
              </span>
            ))}
          </div>
          <ul>
            {families.map((x) => (
              <li key={x.fam} className="grid grid-cols-1 gap-x-6 gap-y-2 border-b border-line px-5 py-4 last:border-0 lg:grid-cols-[minmax(0,16rem)_minmax(0,1fr)_minmax(0,14rem)_minmax(0,11rem)] lg:items-center">
                <span>
                  <FamilyLabel family={x.fam} />
                  <span className="mt-1 block text-[11.5px] text-muted">{x.workers.map(workerLabel).join(", ")}</span>
                </span>
                <span className="text-[13px] text-ink-2">{FAMILY_DESCRIPTION[x.fam]}</span>
                <span className="flex items-center gap-3">
                  <span className="num w-6 text-right text-[15px] font-semibold text-ink">{x.findings}</span>
                  <span className="h-2 flex-1 rounded-[1px] bg-sunken">
                    <span className="block h-full rounded-[1px] bg-brand" style={{ width: `${(x.findings / maxFamily) * 100}%` }} />
                  </span>
                  <span className="w-16 text-[11.5px] text-muted">{x.entities} entit{x.entities === 1 ? "y" : "ies"}</span>
                </span>
                <span className="text-[12px] text-muted">
                  <span className="text-ink-2">{x.signal} signal</span> · {x.clear} clear
                  {x.abstained > 0 && <span className="font-medium text-info"> · {x.abstained} abstained</span>}
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className="mt-2 text-[12px] text-muted">
          Abstained means the worker lacked the data to conclude (for example drift with no previous period, or cross-entity insight for the first entity processed). It is reported, never
          scored as zero.
        </p>
      </section>

      <div className="mt-10 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel className="px-5 py-5" aria-labelledby="risk-h">
          <SectionHeader id="risk-h" title="Risk model" aside="weights are a starting hypothesis" />
          <p className="mb-4 text-[13px] leading-relaxed text-ink-2">
            Each finding is mapped to one of seven dimensions. Within a dimension, contributions are weighted by confidence and saturate at the dimension&rsquo;s weight, so many weak
            findings cannot outweigh the ceiling. The entity score is the sum, out of 100.
          </p>
          <ul className="space-y-2.5" aria-label="Dimension weights and total contribution">
            {dimTotals.map(({ d, weight, contributed }) => (
              <li key={d} className="grid grid-cols-[minmax(0,10rem)_2.5rem_minmax(0,1fr)_3.5rem] items-center gap-3 text-[12.5px]">
                <span className="truncate text-ink">{DIMENSION_LABEL[d]}</span>
                <span className="num text-right text-muted">{weight}</span>
                <span className="h-2 rounded-[1px] bg-sunken">
                  <span className={cn("block h-full rounded-[1px]", contributed ? "bg-brand" : "")} style={{ width: `${(contributed / maxContrib) * 100}%` }} />
                </span>
                <span className="num text-right text-ink-2">{fmtNum(contributed, 1)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11.5px] text-muted">Second column: weight. Bar: total score contributed across all entities in the period.</p>
        </Panel>

        <Panel className="px-5 py-5" aria-labelledby="corr-h">
          <SectionHeader id="corr-h" title="Correlation" />
          <dl className="grid grid-cols-2 gap-5">
            <div>
              <dt className="label">Subject clusters</dt>
              <dd className="num mt-1 text-[26px] font-semibold text-ink">{clusters.length}</dd>
            </div>
            <div>
              <dt className="label">Corroborated</dt>
              <dd className="num mt-1 text-[26px] font-semibold text-brand">{clusters.filter((c) => c.corroborated).length}</dd>
            </div>
          </dl>
          <p className="mt-4 text-[13px] leading-relaxed text-ink-2">
            A cluster is a record referenced by more than one finding. It is corroborated when the findings come from different detector families, which is independent agreement
            rather than one detector firing twice.
          </p>
          <Link href="/workbench/entities" className="mt-3 inline-block text-[12.5px] font-medium text-brand hover:text-brand-strong">
            See corroborated records per entity
          </Link>
        </Panel>
      </div>
    </div>
  );
}
