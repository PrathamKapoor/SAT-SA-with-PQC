# SAT-SA Research Evaluation Protocol

This document defines experiments that can measure the implemented SAT-SA
system without presenting synthetic evidence as operational validation. The
claims boundary is maintained in [RESEARCH_CLAIMS.md](RESEARCH_CLAIMS.md).

## Existing evaluation infrastructure

The implementation already contains a versioned controlled benchmark
(`evaluation/controlled_benchmark`), real-pipeline scenario runs, a declared
synthetic ground-truth catalog, independent closure-time baselines,
seeded synthetic population prioritization, and one-worker-at-a-time
ablations. Public-data adapters exist but the actual CIC-IDS2017 and BOTS data
files have not been run. Expert-label files are templates, not collected
labels. This phase reuses those components.

The evaluation command uses an isolated temporary SQLite database and local
test signing keys. It does not read the configured SaaS database, production
organizations, production object storage, or API data. Research result
artifacts are written only to the caller-selected output root. Demo fixtures
remain separately marked synthetic and are not loaded by production API
requests.

## Questions and executable experiments

1. **RQ1, supported-case signal behavior:** execute the five deterministic
   single-entity scenarios in the catalog through actual SAT-SA ingestion and
   analysis; compare emitted families/actions with the declared labels.
2. **RQ2, baselines and contribution:** compare the actual fast-closure worker
   to z-score, MAD, IQR, fixed-threshold and seeded random baselines; run the
   existing worker ablation and synthetic prioritization comparison.
3. **RQ3, review traceability:** measure a limited, predeclared checklist on
   one real scratch workflow: finding evidence references resolve to source
   records, findings have recommendations, an authorized decision exists, and
   the final receipt verifies. This single-run mechanism measurement is
   implemented; missing-reference perturbation and examiner reviewability
   studies remain unexecuted.
4. **RQ4, imperfect evidence:** `run_evidence_robustness_experiment.py`
   perturbs every executable catalog scenario across five families
   (missingness at 10/25/50 percent with five seeds, duplication,
   malformation, staleness, cross-record conflict) through hosted validation
   and the analysis worker, comparing each condition with its paired control
   (EXP-R01b in [EXPERIMENTS.md](EXPERIMENTS.md)). Staleness and
   cross-record contradictions are measured as undetected limitations, not
   as detectors.
5. **RQ5, TRUST-SAT integrity:** run a real isolated SQLite submission,
   analysis, authorized supervisory decision and finalization, verify the
   valid state, then mutate decision, finding, risk, recommendation, source
   provenance, canonical payload, receipt signature and ledger chain one at a
   time. Restore each mutation and verify the valid state again. This reports
   outcomes for one controlled run; it is not a general detection-rate
   estimate.
6. **RQ6, peer sensitivity:** run the real peer worker over separate exact
   match synthetic cohorts with two, three and four peers, then vary subject
   closure at 30, 400 and 750 seconds against the fixed peer profile. In the
   executed pilot, peer counts 2 and 3 emitted no finding and count 4 did;
   with four peers, only the 30-second subject was flagged. At three peers,
   the 30-second subject was 1.9 MAD from the peer median, below the configured
   2-MAD threshold. These are controlled mechanism observations, not evidence
   about real population distributions.

Phase 9 added seed-replicated prioritization with matched data-only
baselines (EXP-PR01), scenario- and population-level ablation (EXP-A01), a
factorial peer sweep (EXP-P01), an expanded TRUST-SAT mutation matrix with a
negative control (EXP-T01), and direct-vs-LangGraph overhead and recovery
experiments (EXP-O01/O02). Paired comparisons use
`evaluation/research/statistics.py`: medians, p95 only when n ≥ 20, and a
seeded percentile bootstrap interval only when n ≥ 10; smaller samples are
labelled exploratory. No p-values are produced.

RQ1/RQ2/RQ3/RQ5/RQ6 runs are descriptive pilot evidence. Five fixtures, one
synthetic population, and one trust/traceability run are not adequate for
broad generalization or statistical significance. The workload comparator
retains its finite seeded randomization distribution (raw samples, mean,
quartiles and range); these summaries are not confidence intervals. No
inferential tests or significance claims are emitted by the current harness.

## External-data questions (UCI-498, not SOC)

- **EXT-1 feasibility:** the unchanged pipeline on a real IT incident log
  (EXP-X02b: 134,888 rows, 0 rejected, 50/50 analyses completed).
- **EXT-2 detector behaviour:** firing rates on real distributions
  (EXP-X03: four families fire for all 50 groups).
- **EXT-3 external association:** entity risk vs an organisation-recorded SLA
  outcome against data-only baselines (EXP-X02b: ρ −0.11, interval includes 0).
- **EXT-4 failure analysis:** why EXT-3 differed (EXP-X03; construct mismatch
  primary). The evaluation data was not used to tune anything.

## Ground truth, labels, and baseline discipline

- Scenario labels come from `satsa.analysis.validate.synthetic_ground_truth`
  and are validated against the catalog before execution.
- Workload labels are assigned from generator profiles using a recorded seed
  before analysis/ranking.
- Closure labels are fixed by construction before detector execution.
- Emitted predictions are read from real SAT-SA output, never copied from
  expected labels.
- Unsupported catalog scenarios retain an explicit not-executed reason; they
  are not counted as false negatives.
- Do not use `satsa.analysis.validate.run_validation()`'s legacy composition
  scaffold as experimental output. That compatibility path compares catalog
  expectations to themselves; use the controlled benchmark runner or the
  pipeline-bound `run_composition_validation()` instead.

## Metrics

See the precise definitions and unit of analysis in
[RESEARCH_CLAIMS.md](RESEARCH_CLAIMS.md). Primary pilot metrics are micro
family precision/recall/F1, exact action alignment, execution coverage,
closure-time baseline confusion counts, synthetic recall@K/lift, and ablation
family loss. Null means undefined or not measured; it is never filled with
zero. Latency from this harness is local synchronous SQLite runtime and must
not be attributed to PostgreSQL, S3, API, worker or hosted deployment.

## Experimental controls and analysis

Record all workload seeds, profiles, trial counts, benchmark version, code
revision, configuration digest, dataset descriptor digest, and artifact
digests. Fixed-seed repetitions test deterministic metrics, not independent
statistical replication. For future comparative studies, use matched inputs,
replicate across independent seeds, select the independent unit before
analysis, report effect sizes and uncertainty, and pre-specify any
multiple-comparison correction. Do not run tests chosen after examining
favorable outputs and call them confirmatory.

## Trust and human-review evaluation boundary

The controlled trust runner creates an actual scratch workflow and reports a
valid control plus one-at-a-time mutations and verification latency. It is one
SQLite run, not a general tamper-detection probability estimate. A
cryptographic receipt establishes integrity/authenticity of the recorded
canonical state according to the implementation; it does not prove that
real-world evidence was true.

The traceability runner reports one controlled finding-to-reference and
recommendation checklist alongside an authorized decision and verified trust
receipt. This does not measure examiner comprehension, review time, agreement,
or decision quality. No examiner study or collected expert labels are
available.

The peer sweep uses an isolated legacy SQLite store that intentionally
contains only the generated research entities. Production tenant data and
cross-organization raw records are not read; the documented two-MAD rule and
minimum peer count are evaluated only within each explicitly named synthetic
cohort.

## Operational performance boundary

The existing scaling script evaluates a legacy local SQLite path. The
controlled benchmark records local synchronous submission, analysis,
baseline, workload and ablation timings. The trust integrity runner records
verification latency per mutation. The orchestration experiments (EXP-O01,
EXP-O02) measure LangGraph overhead, TRUST-SAT finalization/verification cost
and in-process recovery on local SQLite. None of these measures multi-service
hosted performance: production API latency, PostgreSQL pool behavior, worker
throughput and S3 transfer remain unmeasured. Docker and live services were unavailable during Phase 7
verification; Phase 8 does not claim deployment or production performance
evidence.
