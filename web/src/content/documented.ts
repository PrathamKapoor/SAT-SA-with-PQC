/**
 * DOCUMENTED measurements, transcribed verbatim from the repository's
 * measured report so the UI can show them with their source. These are
 * not computed by the UI and not live data. Update only when the report
 * is regenerated (python scripts/run_controlled_benchmark.py --out <dir>).
 *
 * Source: reports/CONTROLLED_BENCHMARK_P33.md (synthetic, controlled
 * scenarios; not real SOC/CSE/NCIIPC validation).
 */
export const CONTROLLED_BENCHMARK = {
  source: "reports/CONTROLLED_BENCHMARK_P33.md",
  name: "satsa-controlled-supervisory-benchmark v1.0.0",
  scope: "Synthetic controlled scenarios through the real pipeline. Five of ten catalog scenarios executed; five cannot be reproduced in a single-entity fixture.",
  scenarioCorpus: { tp: 5, fp: 7, fn: 0, precision: 0.4167, recall: 1.0, f1: 0.5882, actionAlignment: { correct: 4, total: 5 } },
  scenarios: [
    { name: "healthy", expected: "none", detected: true, extras: 0, actionOk: true },
    { name: "eg-fast-closure", expected: "execution_gap.fast_closure", detected: true, extras: 1, actionOk: true },
    { name: "ns-missing-investigation", expected: "negative_space.missing_investigation", detected: true, extras: 0, actionOk: true },
    { name: "mixed", expected: "execution_gap.fast_closure, negative_space.missing_monitoring", detected: true, extras: 5, actionOk: false },
    { name: "missing-evidence", expected: "evidence_completeness.missing_categories", detected: true, extras: 1, actionOk: true },
  ],
  closureBaselines: [
    { detector: "SAT-SA fast-closure worker", tp: 3, fp: 0, fn: 0, precision: 1.0 as number | null, recall: 1.0 },
    { detector: "MAD", tp: 3, fp: 0, fn: 0, precision: 1.0 as number | null, recall: 1.0 },
    { detector: "Fixed threshold (600s)", tp: 3, fp: 0, fn: 0, precision: 1.0 as number | null, recall: 1.0 },
    { detector: "Random (seeded)", tp: 1, fp: 2, fn: 2, precision: 0.33 as number | null, recall: 0.33 },
    { detector: "z-score", tp: 0, fp: 0, fn: 3, precision: null, recall: 0.0 },
    { detector: "IQR", tp: 0, fp: 0, fn: 3, precision: null, recall: 0.0 },
  ],
  closureNote: "12 records, 3 positive. Too small for any superiority claim: it demonstrates mechanics and honest comparison.",
  prioritization: [
    { k: 10, satsa: 0.25, random: 0.0975, lift: 2.56 },
    { k: 20, satsa: 0.5, random: 0.1988, lift: 2.52 },
    { k: 50, satsa: 0.75, random: 0.52, lift: 1.44 },
  ],
  prioritizationNote: "Simulated workload experiment with synthetic labels. Not a claim about real analyst time saved.",
} as const;
