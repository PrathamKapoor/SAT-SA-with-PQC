# SAT-SA Experiment Registry

Every experiment below is a command in `scripts/` that writes a write-once
bundle (`manifest.json`, `config.json`, `raw/results.json`,
`processed/metrics.json`, `processed/metrics.csv`, `summary.md`) through
`evaluation.research.artifacts.write_experiment_bundle`. Numbers quoted here
are copied from the named bundle; the bundle is the source of truth. Bundles
live outside the repository (Phase 9 runs: `C:\tmp\satsa-phase9\`; Phase 8
runs: `C:\tmp\satsa-phase8-final\`) and must be archived with the commit they
name before being cited.

Status vocabulary: **MEASURED** (executed, completed bundle, clean source
tree), **IMPLEMENTED — NOT EXECUTED**, **BLOCKED: reason**, **PROTOCOL READY —
NOT EXECUTED**. All data is synthetic or controlled unless stated otherwise.
Timings are local synchronous runs on one Windows machine with SQLite unless
stated otherwise; they are not production-topology measurements.

## Registry

| ID | Purpose | Dataset | Sample size / unit | Baseline or control | Command | Status |
| --- | --- | --- | --- | --- | --- | --- |
| EXP-C01 | Controlled detection, baselines, workload, ablation (Phase 8) | 5 catalog scenarios; 6-entity population | 5 scenarios; 1 population, 25 random orders | Catalog labels; z/MAD/IQR/fixed/random closure baselines; random order | `run_controlled_benchmark.py` | MEASURED (Phase 8, `controlled-final-seed-17`, commit `82085d2`) |
| EXP-R01b | Robustness to imperfect evidence | 5 catalog scenarios × declared perturbations | 248 conditions (245 with a declared expectation, 3 not applicable) | Paired unperturbed control per scenario | `run_evidence_robustness_experiment.py` | MEASURED (commit `400f2d6`) |
| EXP-R01 | Same, before the workflow-reconstruction fix | as above | as above | as above | as above | MEASURED, superseded by EXP-R01b (commit `e7aedd8`) |
| EXP-O01 | Direct vs LangGraph overhead; TRUST-SAT cost | `mixed` catalog scenario | 30 trials per mode × 3 modes, rotated order, 1 warm-up each | Direct execution; unreviewed configuration | `run_orchestration_experiment.py overhead` | MEASURED (commit `698b507`) |
| EXP-O02 | Interruption and recovery | `mixed` catalog scenario | 6 interruption points × 2 modes × 3 trials = 36 runs | Uninterrupted reference run per mode | `run_orchestration_experiment.py recovery` | MEASURED (commit `698b507`) |
| EXP-T01 | TRUST-SAT mutation matrix | one controlled synthetic workflow | 14 mutations (13 expected tampered, 1 negative control) | Valid control, restored after each mutation | `run_trust_integrity_experiment.py` | MEASURED (commit `9325fdd`) |
| EXP-P01 | Peer sensitivity sweep | engineered cohorts | 96 cells: 6 cohort sizes × 2 spreads × 8 subject values | Same peer policy (≥3 peers, 2 MAD) | `run_peer_sensitivity_experiment.py --sweep` | MEASURED (commit `9325fdd`) |
| EXP-A01 | Component ablation | 5 catalog scenarios; 5 generated populations of 20 | 17 workers × (5 scenarios + 5 population seeds) | Full default worker set | `run_ablation_experiment.py` | MEASURED (commit `9325fdd`) |
| EXP-PR01 | Replicated prioritization with matched baselines | 20 generated populations of 20 entities (5 pathological) | 20 independent seeds | Random order; critical-alert volume; fastest median closure | `run_prioritization_experiment.py` | MEASURED (commit `9325fdd`) |
| EXP-D01 | HTTP smoke across local API and worker processes (SQLite, local storage) | one smoke tenant | 18 checks, 1 run | — | `scripts/deployment_smoke.py --provision --report …` | MEASURED: 18/18 PASS (commit `aa79109`; report `EXP-D01-local-process-smoke.json`) |
| EXP-H01 | Evidence-only vs SAT-SA-assisted human review | frozen case set (to be drawn) | not recruited | Evidence-only condition | — | PROTOCOL READY — NOT EXECUTED (`docs/HUMAN_REVIEW_PROTOCOL.md`) |
| EXP-X01 | External public data (CIC-IDS2017, BOTS, GUIDE) | real public data | — | — | adapters in `public_benchmarks/` | BLOCKED: datasets not downloaded; see below |

## Measured results

### EXP-R01b — robustness to imperfect evidence

Hosted submission validation and the analysis worker, one fresh SQLite
tenant per condition. Every perturbation declares its family, severity,
affected records, expected validation outcome and expected effect before it
runs.

- Validation matched the declared contract in **245 of 245** conditions
  with an expectation; 3 conditions were not applicable (the fixture lacked
  the records they need).
- Hosted validation is all-or-nothing. Independent record omission produced
  dangling references (investigation steps whose case was removed) and was
  rejected in 3/25, 11/25 and 14/25 replicates at 10/25/50% omission.
  Referentially consistent omission (a removed case takes its steps) was
  never rejected and changed the emitted finding-family set versus control in
  1/25, 11/25 and 15/25 replicates.
- Omitting a whole category: omitting escalations added
  `execution_gap.critical_without_escalation` and
  `negative_space.missing_escalation` in `eg-fast-closure` and `mixed` (the
  scenarios with critical alerts); omitting assets removed both
  monitoring-coverage families in `mixed` and lowered its risk score from
  27.21 to 14.92; omitting cases was rejected in every scenario because
  investigation steps reference cases.
- Exact duplicates of alerts, cases and steps, conflicting duplicates of
  alerts and cases, malformed timestamps, chronology violations, missing
  required columns and case status/closure conflicts were rejected (15
  malformation and 25 duplication conditions, 5 conflict conditions).
- Near-duplicate records without native ids (a re-sequenced investigation
  step, a repeated disposition) were accepted. The re-sequenced step now
  surfaces `workflow_reconstruction.sequence_chronology_mismatch` in all five
  scenarios; before the fix in commit `da80046` that finding was withheld as
  invalid (EXP-R01).
- **Staleness is a limitation, not a detector:** alerts shifted 1 day or 40
  days before, or 1 day after, the assessment period were accepted with zero
  warnings and changed no family, finding count or risk value (15/15).
  SAT-SA implements no assessment-period or recency validation.
- Contradictory dispositions for one alert and a closed case with an open
  alert were accepted with no warning and no change to findings or risk.
  Removing the investigation steps of an escalated case changed the family
  set in all 4 applicable scenarios: it added
  `negative_space.missing_investigation` (healthy) or
  `execution_gap.ack_without_investigation` (eg-fast-closure, mixed); in
  ns-missing-investigation the existing missing-investigation finding was
  replaced by `case_similarity.template_cluster`.

### EXP-O01 — direct vs LangGraph orchestration and TRUST-SAT cost

30 matched trials per mode on the `mixed` fixture. Outputs (families, finding
and recommendation counts, risk score) were identical for direct and graph in
every trial; findings and risk were identical across all three modes.

| Quantity (median, n=30) | direct | graph | unreviewed |
| --- | ---: | ---: | ---: |
| Processing time excluding the human decision (s) | 1.276 | 1.433 | 0.976 |
| p95 of processing time (s) | 2.010 | 2.206 | 1.655 |
| Time outside domain stages (s) | 0.055 | 0.115 | 0.029 |
| Database calls per workflow | 420 | 458 | 253 |
| LangGraph checkpoints per run | — | 7 | — |

- Graph minus direct, paired by trial: median +0.096 s processing time
  (+7.5% of the direct median), 95% percentile-bootstrap interval −0.020 to
  +0.211 s (graph slower in 19/30 pairs). Outside-domain overhead +0.059 s
  (interval +0.057 to +0.061 s). +38 database calls in every pair.
- TRUST-SAT, direct mode: supervisory finalization median 0.288 s (p95
  0.504 s), about 23% of reviewed processing time; receipt verification
  median 0.062 s; 5 ML-DSA signatures per workflow; run/finding attestation
  median 0.853 s is the largest single cost in the workflow.
- Reviewed and finalized vs unreviewed: median +0.318 s (interval +0.176 to
  +0.569 s).
- These are repeated measurements on one machine; intervals describe that
  variability and no significance test is made.

### EXP-O02 — interruption and recovery

Transient failures (`RetryableAnalysisError`) and simulated crashes (a
`BaseException` that bypasses the worker's handler, then lease expiry) were
injected during analysis stages, before recommendations, at the review
checkpoint (worker restart) and during TRUST-SAT finalization.

- **36 of 36** interrupted runs recovered to completion in both modes, with
  outputs identical to the uninterrupted reference, no completed stage
  repeated, exactly one review decision and one finalization, and a verifying
  receipt. The interrupted stage itself re-ran, as designed.
- Median recovery latency: ~0.09–0.12 s for analysis-stage interruptions,
  0.03–0.06 s for recommendation failures, ~0.9–1.4 s for finalization
  failures and 1.3 s (direct) / 1.9 s (graph) for a worker restart at review
  (these include the remaining work).
- The graph mode's checkpoint existed in every graph run.
- Limitation: interruptions are injected at worker-method boundaries in one
  process; real process kills, network partitions and database failover were
  not exercised.

### EXP-T01 — TRUST-SAT mutation matrix

One finalized synthetic workflow; each mutation applied, verified, restored
and re-verified. **Detected all 13 tested canonical-state mutations**
(decision action and reason, finding, risk, recommendation, observation
scope, source provenance, submission record payload, artifact digest,
canonical payload, receipt signature, receipt public key, ledger chain). The
negative control — the unsigned operational `lease_owner` queue field —
still verified, as the design intends. This is not a tamper-detection rate.

### EXP-P01 — peer sensitivity sweep

The worker compares creation-to-close time (configured closure + 10 s
acknowledgement). Peer values are evenly spaced around a 610 s median.

- Cohorts of 2 peers never emitted a peer finding (minimum 3 peers).
- Tight spread (540–660 s): from 3 peers upward every subject except the one
  at the median was flagged (7 of 8 subject values).
- Wide spread (150–1050 s): only 1500 s and 3000 s subjects were flagged at
  3–4 peers; fast subjects (30 s, and 150 s at 5 peers) were flagged only from
  5 peers upward, as the MAD narrows.
- A flagged subject ranked first by risk within its own cohort in every cell.

### EXP-A01 — component ablation

- Scenario level (5 fixtures, one database each): full set micro TP 5, FP 4,
  FN 0 (precision 0.556, recall 1.0, F1 0.714). Removing `fast-closure` or
  `negative-space` dropped recall to 0.6; removing `evidence-completeness` to
  0.8; removing `recurring-without-remediation` or `coverage-gap` raised
  precision (0.714, 0.625) because those workers emitted only unlabelled
  families here. Other workers changed nothing on these fixtures.
- Population level (5 seeds × 20 entities, recall@20%; n=5 is exploratory):
  full-set mean 0.76. Removing `fast-closure` lowered it to 0.60 and
  `negative-space` to 0.64; removing `peer-benchmark` or `case-similarity`
  to 0.72. Removing `recurring-without-remediation`, `anomaly`,
  `coverage-gap` or `workflow-reconstruction` *raised* it to 0.80 — these
  workers added ranking noise on these generated populations.
- The full set here differs from EXP-C01 (FP 7) because EXP-C01 runs all
  scenarios in one shared database, where cross-entity workers see each
  other's data.

### EXP-PR01 — replicated prioritization

20 independent generated populations (seeds 100–119), 20 entities each, 5
generator-labelled pathological. All four methods rank the same universe
with the same top-k (top 2/4/6 entities at 10/20/30%). With 20 entities the
per-population estimates are coarse. A first attempt ended with shell exit
code 127 before writing any bundle (log kept as
`EXP-PR01.attempt1-exit127.log`); the recorded bundle is the re-run.

| Median over 20 populations | SAT-SA | fastest median closure | critical/high alert volume | random (expectation) |
| --- | ---: | ---: | ---: | ---: |
| precision@10% | 1.0 | 1.0 | 0.5 | 0.245 |
| recall@20% | 0.8 | 0.6 | 0.2 | 0.20 |
| NDCG@20% | 1.0 | 0.832 | 0.246 | 0.248 |
| recall@30% | 0.8 | 0.8 | 0.4 | 0.295 |
| NDCG@30% | 0.869 | 0.837 | 0.318 | 0.276 |
| Entities reviewed to find all 5 | 7 | 11.5 | 18 | 17.5 |

- Versus random order SAT-SA was higher in 20/20 populations on every
  metric (recall@20% median paired difference +0.59, 95% bootstrap interval
  +0.41 to +0.60).
- Versus critical/high alert volume it was higher in 20/20 populations at
  20% and 30% and in 18/20 at 10%.
- Versus the fastest-median-closure heuristic the result is mixed: recall@20%
  was higher in 8, equal in 11 and lower in 1 population (median difference
  0, interval 0 to 0.2); NDCG@30% higher in 12, equal in 3, lower in 5. SAT-SA
  needed fewer reviews to find every pathological entity in 12 populations
  and more in 6. A simple closure-speed rule captures much of what separates
  these generator profiles.
- Intervals are descriptive and uncorrected for the 27 comparisons reported;
  no significance claim is made. Populations come from SAT-SA's own
  generator, whose pathological profile injects the behaviours SAT-SA's
  detectors target.

## External data (EXP-X01)

| Dataset | Source / licence | What maps to SAT-SA | What does not | Status |
| --- | --- | --- | --- | --- |
| CIC-IDS2017 | UNB CIC | flows → alerts/assets via `public_benchmarks/cicids2017` | no cases, steps, escalations, dispositions or analyst workflow | adapter tested on documented schema; real files not downloaded — BLOCKED |
| Splunk BOTS | Splunk research release | notable events → alerts via `public_benchmarks/bots` | no analyst workflow | adapter tested; real export not downloaded — BLOCKED |
| Microsoft GUIDE (Freitas et al., arXiv 2407.09017) | Kaggle, CDLA-Permissive-2.0 | alerts (`AlertId`, `Timestamp`, `Category`), incidents → cases, incident triage grade (TP/BP/FP), remediation actions | only alert creation time: no acknowledgement or closure times, no investigation steps, no escalations, no analyst identities | identified, **not integrated**: supports alert/incident triage questions, not execution-gap or negative-space detection |

No external dataset has been run. Workflow-augmented public benchmarks
(`public_benchmarks/workflow_augmentation`) inject synthetic workflow and must
not be described as real-world validation (see `docs/PUBLIC_BENCHMARKS.md`).

## Expert labels

Schema, import and layer validation exist (`sat-sa validate --expert-labels`,
`docs/demo/EXPERT_LABELS.md`). The only label file is a template tagged
`sample-template`. No expert has labelled SAT-SA output: expert validation is
**NOT EXECUTED**.
