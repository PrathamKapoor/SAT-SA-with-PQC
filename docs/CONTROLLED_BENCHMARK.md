# Controlled Supervisory Benchmark — methodology

Benchmark: `satsa-controlled-supervisory-benchmark` **v1.0.0**
Runner: `scripts/run_controlled_benchmark.py`
Implementation: `evaluation/controlled_benchmark/` (manifest.py, runner.py)

## Purpose

Turn "we have synthetic tests" into a **versioned, seeded,
ground-truth-controlled supervisory benchmark, measured through the
real SAT-SA pipeline, with stated limits and reproducible commands**.
It is release/evaluation *readiness* evidence — it is **not** real
SOC/CSE/NCIIPC validation (see "Forbidden conclusions").

## Synthetic provenance

Every scenario is a deterministic hand-built single-entity fixture
(`satsa/analysis/compval.py::SCENARIO_MAP`) or a seeded synthetic
generator population (`evaluation/workload/experiment.py`). Nothing in
this benchmark processes real CIC-IDS2017, Splunk BOTS, CSE, SOC, or
NCIIPC data. Every result file records this statement and the
benchmark version, code version, seeds, and per-input SHA-256 digests.

## Scenario and ground-truth design

Ground truth comes from exactly one place:
`satsa/analysis/validate.py::synthetic_ground_truth()` — the canonical
10-scenario catalog. Each case declares `expected_signals` (finding
families) and `expected_action` (supervisor decision vocabulary),
**authored before any pipeline run; no analytical code imports it
during a run**. The manifest (`evaluation/controlled_benchmark/
manifest.py`) re-declares the catalog and `validate_manifest()` fails
loudly if a manifest entry disagrees with the catalog — so labels can
never be edited to flatter detector output.

Five scenarios are executable in single-entity fixtures:
`healthy` (negative control), `eg-fast-closure`,
`ns-missing-investigation`, `mixed`, `missing-evidence`.
Five are declared **not_executable** with documented reasons
(anomaly-rate, peer-deviation, borderline, noisy,
conflicting-evidence) and are never scored as zero.

The workload population's labels (pathological vs clean) come from the
*generator configuration* chosen by a seeded shuffle before any
detector or ranking runs. The closure-time corpus's labels come from
construction (fast closures were built fast). No label is ever
derived from detector output — scoring a detector against itself is
forbidden by this project's ground-truth rule.

## Metrics

- **Scenario corpus** (executable scenarios): at the declared
  signal-family level, per scenario `tp=|expected∩emitted|`,
  `fn=|expected−emitted|`, `fp=|emitted−expected|`, micro-averaged to
  corpus precision/recall/F1. The catalog does not declare family
  exclusivity, so emitted-but-unexpected families count as false
  positives AND are listed per-scenario as `extra_families`.
- **Action alignment**: fraction of executed scenarios whose emitted
  supervisor decision equals the catalog's `expected_action`.
- **Coverage**: executed vs not_executed counts with reasons; unknown
  is reported as unknown, never as 0% or 100%.
- **Prioritization (simulated)**: recall@K and
  review-volume-to-find-all for SAT-SA entity prioritization vs a
  measured random-order baseline (200 trials).
- **Closure-time baselines**: z-score / MAD / IQR / fixed-threshold /
  random vs the real `FastClosureWorker`, all scored against the same
  construction-defined labels.
- **Ablation**: which finding families disappear when exactly one
  default worker is removed, measured through the real `RunService`.

Metrics that the fixtures cannot honestly support (per-record
precision/recall for negative-space/anomaly/peer/drift/similarity;
entity-level ordering ground truth beyond the workload population) are
not reported. A metric that cannot be computed is reported
`not_applicable` with a reason.

## Baselines and ablation scope

The baseline and ablation sections reuse `evaluation/baselines/` and
`evaluation/ablation/` as-is. The three result classes — detector
benchmark, baseline comparison, ablation — are reported in separate
top-level sections and are never mixed.

## Reproducible command

```bash
python scripts/run_controlled_benchmark.py --out <output-dir> [--seed 42]
```

Writes `controlled-benchmark-results.json` (benchmark version, code
version, seeds, timestamps, per-scenario labels/emissions, metrics,
limitations) to the explicitly chosen output directory. Results are
never written into tracked source directories by default. Determinism
is enforced by fixed seeds and verified by
`tests/test_phase88_controlled_benchmark.py::test_runner_is_deterministic_for_fixed_seed`
(two full runs must produce identical `metrics`).

## Allowed conclusions

- On the controlled synthetic corpus (versioned v1.0.0, declared
  seeds), the real SAT-SA pipeline detected 5/5 declared signal
  families (corpus recall 1.0) with 7 extra family emissions (corpus
  precision 0.4167), aligned the supervisor action for 4/5 scenarios,
  prioritized synthetically-pathological entities ahead of a measured
  random baseline (2.56x recall lift at top-10%), matched the best
  statistical baseline (MAD / fixed-threshold) on the closure-time
  corpus, and showed 5 workers with unique family contributions on the
  ablation scope.

## Forbidden conclusions

- NOT real SOC/CSE/NCIIPC validation; NOT equivalent to real SOC
  operations; no real examiner data was used.
- NOT validated on CIC-IDS2017 or Splunk BOTS (adapters have not been
  run against real dataset files).
- NOT a claim that SAT-SA is superior to human expert review — the
  "baseline" here is a statistical/naive control, not a human.
- NOT evidence of target-machine (air-gapped) deployment.
- The `mixed` scenario's action mismatch is a measured miss, not a
  passing score to be explained away.
