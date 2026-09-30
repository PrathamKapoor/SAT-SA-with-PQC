import type { Metadata } from "next";
import { DIMENSION_LABEL, DIMENSION_ORDER, FAMILY_DESCRIPTION, FAMILY_LABEL, RECOMMENDATION_LABEL, type FindingFamily } from "@/lib/domain/labels";

export const metadata: Metadata = {
  title: "Methodology",
  description: "How SAT-SA turns periodic CSE submissions into prioritised, explainable supervisory findings.",
};

const FAMILIES: FindingFamily[] = [
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

/** Weights documented in satsa/analysis/risk.py DIMENSION_WEIGHTS. */
const WEIGHTS: Record<string, number> = {
  execution_gap: 25,
  peer_deviation: 20,
  detection_gap: 15,
  negative_space: 15,
  anomaly: 15,
  investigation_quality: 5,
  escalation_discipline: 5,
};

function Block({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-6 border-t border-line py-14 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
      <div>
        <p className="font-mono text-[12px] text-brand">{n}</p>
        <h2 className="mt-2 text-[24px] leading-tight font-semibold tracking-[-0.02em] text-ink">{title}</h2>
      </div>
      <div className="max-w-3xl text-[15px] leading-relaxed text-ink-2">{children}</div>
    </section>
  );
}

export default function MethodologyPage() {
  return (
    <div className="mx-auto max-w-[1320px] px-5 pt-16 pb-12 md:px-8">
      <p className="label">Methodology</p>
      <h1 className="mt-4 max-w-[18ch] text-[40px] leading-[1.04] font-semibold tracking-[-0.035em] text-ink md:text-[60px]">
        Transparent rules, robust statistics, human judgement.
      </h1>
      <p className="mt-6 max-w-2xl text-[17px] leading-relaxed text-muted">
        SAT-SA prefers a rule a supervisor can read over a model they cannot. Statistics are robust to outliers, thresholds are declared, and machine learning is used only where it adds
        real value.
      </p>

      <div className="mt-16">
        <Block n="01" title="A frozen snapshot per period">
          <p>
            Each CSE submits six evidence categories for an assessment period: alerts, cases, investigation steps, escalations, dispositions and assets, as CSV, JSON, JSONL or SQLite.
            Rows are validated against a declared field specification; a row missing a required field is rejected, never silently filled. Accepted records are normalized into
            canonical form, fingerprinted, and frozen as a snapshot before any analysis runs.
          </p>
        </Block>

        <Block n="02" title="Sixteen analytical workers">
          <p>Every run executes the same registered workers. Each returns a signal, no signal, or an explicit abstention when the data cannot support a conclusion.</p>
          <ul className="mt-6 grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {FAMILIES.map((f) => (
              <li key={f} className="border-t border-line pt-3">
                <p className="text-[14px] font-semibold text-ink">{FAMILY_LABEL[f]}</p>
                <p className="mt-1 text-[13.5px] text-muted">{FAMILY_DESCRIPTION[f]}</p>
              </li>
            ))}
          </ul>
        </Block>

        <Block n="03" title="Decomposable risk">
          <p>
            Each finding maps to one of seven dimensions. Contributions are weighted by the finding&rsquo;s confidence and saturate at the dimension&rsquo;s weight, so many weak signals
            cannot outweigh the ceiling. The entity score is the sum out of 100, and every point can be traced to the findings behind it.
          </p>
          <ul className="mt-6 space-y-2" aria-label="Dimension weights">
            {DIMENSION_ORDER.map((d) => (
              <li key={d} className="grid grid-cols-[minmax(0,12rem)_3rem_minmax(0,1fr)] items-center gap-4 text-[14px]">
                <span className="text-ink">{DIMENSION_LABEL[d]}</span>
                <span className="num text-right text-muted">{WEIGHTS[d]}</span>
                <span className="h-2 rounded-[1px] bg-brand" style={{ width: `${WEIGHTS[d] * 4}%` }} />
              </li>
            ))}
          </ul>
          <p className="mt-4 text-[13px] text-muted">The weights are a starting hypothesis pending domain-expert calibration, not a final model.</p>
        </Block>

        <Block n="04" title="Correlation and priority">
          <p>
            When findings from different detector families reference the same record, the agreement is marked as independent corroboration. Entities are ranked by risk,
            confidence, recency and the count of high-severity signals, and findings within a run by severity and confidence.
          </p>
        </Block>

        <Block n="05" title="Bounded recommendations">
          <p>Each finding receives one bounded hint for the supervisor. It is a pointer to what to inspect, never a decision:</p>
          <ul className="mt-4 flex flex-wrap gap-2">
            {Object.values(RECOMMENDATION_LABEL).map((r) => (
              <li key={r} className="rounded-xs border border-line px-2 py-1 text-[13px] text-ink-2">
                {r}
              </li>
            ))}
          </ul>
        </Block>

        <Block n="06" title="Validation without overclaiming">
          <p>
            Validation is layered: synthetic ground-truth scenarios generated outside the analytical path, a controlled benchmark through the real pipeline with statistical baselines,
            ablation of each worker, and a framework for expert labels. Measured results, including misses, are published in the repository&rsquo;s reports rather than summarised as a
            single accuracy number.
          </p>
        </Block>
      </div>
    </div>
  );
}
