# SAT-SA Research Claims and Evidence Matrix

This is the working boundary for claims in a future paper. An implemented
component is not, by itself, evidence of novelty or effectiveness.
“Measured” means a result artifact exists from an executed protocol;
“candidate” means an experiment could test it, not that it has passed.

## Contribution map

| Aspect | Current classification | What code establishes | What remains to establish |
| --- | --- | --- | --- |
| Periodic supervisory analytics over structured cyber/workflow evidence | Implemented capability; engineering contribution; research candidate | Deterministic ingest, normalization, workers, findings and risk exist | Evaluation on independent real or practitioner-labelled submissions |
| Execution-gap and negative-space detection | Implemented capability; research candidate | Workers detect selected declared synthetic conditions | Broader independent labels, sensitivity to missingness, false-positive behavior |
| Multi-detector correlation, risk and prioritization | Implemented capability; research candidate | Real workers/risk/prioritization and one-worker ablations run | Paired controlled comparisons across independently generated cases/seeds |
| Peer deviation | Implemented capability; synthetically mechanism-tested | Peer worker and isolated synthetic cohort sensitivity runner execute; production isolation constrains population | Independent real/practitioner-labelled cohorts; never production cross-tenant rows |
| LangGraph orchestration | Implemented engineering infrastructure | Persistent orchestration, checkpoint, review interrupt and resume exist | Measure orchestration overhead/recovery versus direct execution; no current benefit claim |
| Evidence-backed findings and provenance | Implemented engineering capability; research candidate | Evidence references/provenance and retrieval paths exist | Predefined traceability coverage metric and independently assessed reviewability |
| Human supervisory checkpoint | Implemented workflow capability | Authorized decision persists and resumes/finalizes workflow | Controlled human study; no examiner time/agreement outcome currently available |
| TRUST-SAT decision binding (ML-DSA-65, SHA3-256, ledger) | Implemented security/engineering contribution; integrity research candidate | Finalization, binding, verification and tamper tests exist | A separately reported controlled mutation protocol and operational cost study |
| Tenant-aware SaaS persistence and deployment topology | Engineering contribution; deployment evidence incomplete | API/DB/worker/S3-compatible code and deployment artifacts exist | Phase 7 local production-like and hosted deployment were not executed/verified |
| Reproducible evaluation method | Partially implemented; engineering contribution | Versioned synthetic catalog, deterministic runner, baselines and ablation exist | Immutable run manifests, artifact hashes, durable exports and independent datasets |

No aspect is classified as established research novelty. Inherited QSMLOps,
LangGraph, cryptographic algorithms, databases, and standard statistical
methods are not claimed as SAT-SA inventions.

## Evidence categories (never merged)

| Category | Meaning | What exists |
| --- | --- | --- |
| Controlled synthetic | mechanism and robustness validation on authored or generated data | EXP-C01, R01b, O01, O02, T01, P01, A01, PR01 (freeze v1) |
| External dataset | partial independent validation on real data of a different domain | EXP-X02: UCI-498 real IT incident log — feasibility, detector saturation, no association with SLA-miss rate |
| Real operational SOC data | effectiveness on the target domain | **not evaluated** |

The authoritative claim-to-artifact matrix is
[PAPER_EVIDENCE_INDEX.md](PAPER_EVIDENCE_INDEX.md); literature positioning is
in [LITERATURE_POSITIONING.md](LITERATURE_POSITIONING.md); limitations in
[RESEARCH_LIMITATIONS.md](RESEARCH_LIMITATIONS.md).

## Claims/evidence matrix

| Claim under consideration | Why it matters | Component | Metric and unit | Dataset / baseline / experiment | Artifact | Threats / current status |
| --- | --- | --- | --- | --- | --- | --- |
| SAT-SA emits declared supervisory signal families on controlled cases | Tests basic detection behavior | Existing deterministic workers | Micro precision/recall/F1 over expected/emitted case-family pairs; case is the fixture | Five executable synthetic scenarios; compare against independently declared catalog labels | Immutable benchmark bundle with raw per-case outputs | Small authored catalog, family labels not incident-level truth; pilot executable, no real operations claim |
| Signal fusion changes finding coverage compared with component removal | Tests whether each selected detector contributes unique coverage | Worker dispatch, correlation, risk | Set of families lost when one worker is removed on identical scope; scope is one mixed fixture | Full worker set vs exactly one worker removed per run | Ablation JSON and raw results | One scope does not estimate general causal value; implemented, measure is descriptive |
| Prioritization captures synthetic pathological entities above random review order | Tests ordering on generator-defined conditions | Entity prioritization | Recall@K; lift over seeded random mean; entity population is unit | Seeded pathological/clean profiles vs 200 seeded random permutations | Raw result + seed/config manifest | Synthetic profiles may favor known rules; a 6-entity pilot is only a smoke experiment |
| Evidence/provenance allows findings to be traced through an authorized decision and receipt | Makes examiner review auditable | Evidence, provenance, review, TRUST-SAT | Finding-level recommendation coverage, resolvable evidence-reference coverage, decision existence, receipt verification; finding is unit | One complete controlled synthetic workflow | `trust-integrity-*` traceability section | One workflow; limited reference checklist, not a human reviewability result |
| TRUST-SAT detects controlled changes to the finalized supervisory record | Tests integrity verification, not truth of evidence | Finalization, decision binding, ledger verification | Verified/tampered outcomes by mutation class; receipt is unit | Valid state then one-at-a-time mutation of decision, finding, risk, recommendation, source provenance, canonical payload, receipt signature, ledger chain | `trust-integrity-*` immutable bundle; verification categories and timings | One synthetic SQLite run; not a population detection-rate or resistance-to-coordinated-replacement claim |
| Evidence incompleteness changes validation and analytical outputs in a measurable way | Tests robustness to partial submissions | Submission validation and negative-space workers | Acceptance/rejection, findings, risk and completeness by perturbation level; submission is unit | Complete control vs controlled missing/duplicate/stale/conflicting/malformed conditions | `EXP-R01b-evidence-robustness` bundle | Measured on five authored fixtures: validation matched its contract in 245/245 conditions; stale and contradictory records are accepted silently (limitation) |
| Stateful orchestration has acceptable overhead and resumes without repeating committed stages | Quantifies orchestration trade-off | Phase 3 worker + LangGraph | Paired latency, recovery completion, duplicate side effects; analysis run is unit | Direct vs graph on the same fixture, 30 rotated trials; 6 injected interruption points × 2 modes × 3 trials | `EXP-O01` and `EXP-O02` bundles | Measured on one machine with SQLite: median +0.096 s (interval includes 0), +38 DB calls, 36/36 recoveries; not production topology |
| Peer deviation behavior responds to cohort sufficiency and configured deviation threshold | Tests implemented peer baseline rules in a controlled population | Peer benchmark worker | Peer-baseline count, median/MAD and actual emitted finding; cohort is unit | Synthetic peer counts 2/3/4 and subject closure times 30/400/750s; same worker threshold | `peer-sensitivity-*` immutable bundle | Pilot executed: count 2 and 3 cases did not emit; count 4 emitted; fixed n=4 magnitude sweep flagged 30s only. Small engineered closure-only cohorts; no field-population inference |

## Research questions

### RQ1 — Controlled signal detection

**Question:** On independently specified synthetic supervisory cases, how often
does the real SAT-SA pipeline emit declared finding families and expected
actions? **Hypothesis:** the deterministic workers will emit the target family
for supported fixtures, while some additional families may appear. This is a
descriptive engineering hypothesis, not a real-world effectiveness claim.

- Independent variable: scenario condition from the frozen ground-truth catalog.
- Dependent variables: family TP/FP/FN; action match; execution coverage.
- Control/baseline: healthy negative control and predeclared scenario labels.
- Unit: scenario-family pair; action unit: scenario.
- Protocol: `satsa-controlled-supervisory-benchmark` v1.0.0 through the actual
  ingestion and synchronous SQLite analytics path.
- Statistics: descriptive micro counts and ratios. Do not infer population
  uncertainty from five hand-authored cases.
- Artifact: raw run bundle, per-scenario output, input digests, config, manifest.
- Main threat: synthetic cases and labels are authored within the same project.

### RQ2 — Detector contribution and prioritization

**Question:** Which workers add unique finding-family coverage on a controlled
multi-signal case, and does SAT-SA ordering capture generator-labelled
pathological entities more often than random order? **Hypothesis:** some worker
ablations remove a family on the selected scope; ranking may exceed random on
the selected synthetic population.

- Independent variables: one worker omitted at a time; ranking method.
- Dependent variables: families lost; recall@K and review volume to find all.
- Baselines: complete worker set for ablations; 200 seeded random orders for
  prioritization.
- Unit: finding family for ablation; generated entity population for ranking.
- Statistics: report counts and random-trial distribution; no significance
  claim from one generated population. Repeat independent dataset seeds before
  any inferential comparison.
- Threats: one ablation scope, generator/worker alignment, small populations.
- Status: executable; each artifact must preserve its actual seed and scope.

### RQ3 — Evidence and supervisory review traceability

**Question:** Can an examiner-facing finding be traced through source evidence,
recommendation, authorized decision and trust verification? **Hypothesis:**
required references can be reconstructed for supported complete workflows.

- Independent variable: complete workflow vs a controlled missing-reference
  condition (future experiment).
- Dependent variables: traceability coverage under a field checklist and
  verification outcome.
- Baseline: a predeclared required-reference checklist, not an LLM judgment.
- Unit: finding/decision chain.
- Statistics: descriptive coverage only until independent cases/reviewers exist.
- Status: one limited synthetic workflow checklist was executed by
  `run_trust_integrity_experiment.py`; missing-reference perturbations and
  any examiner review study remain unexecuted.

### RQ4 — Robustness to imperfect evidence

**Question:** How do validation, findings and risk change under controlled
omission, duplication, staleness, conflict and malformed input? **Hypothesis:**
structural errors should be surfaced and missing expected records may produce
negative-space signals where defined.

- Independent variable: perturbation type and predeclared rate.
- Dependent variables: validation outcome, rejected/accepted records, findings,
  risk and evidence completeness.
- Baseline: unmodified submission from the same seeded generator.
- Unit: paired submission from the same seed/profile.
- Statistics: paired differences; bootstrap intervals only after enough
  independent seeds and with the seed as the replication unit.
- Status: implemented and executed as EXP-R01b (five families, 10/25/50%
  omission with five seeds each, paired controls). Results are descriptive
  counts over authored fixtures; see [EXPERIMENTS.md](EXPERIMENTS.md). The
  evaluation exposed and fixed one defect (a withheld sequence-chronology
  finding). Staleness has no implemented detector, so it is reported as an
  observed limitation.

### RQ5 — Cryptographic decision integrity

**Question:** Does TRUST-SAT verify a valid final record and reject controlled
changes to its finalized decision context? **Hypothesis:** the live verifier
will reject the specified one-at-a-time mutations.

- Independent variable: one mutation class applied at a time to an isolated
  scratch SQLite record/ledger.
- Dependent variables: verification outcome/category and verifier latency.
- Baseline: valid unmodified supervisory finalization before mutations and
  after restoring each mutation.
- Unit: one finalized synthetic analysis run per experiment; mutation class is
  the repeated condition, not an independent dataset sample.
- Statistics: report detected/attempted counts and individual outcomes; no
  estimate of general tamper-detection probability or significance.
- Artifact: `run_trust_integrity_experiment.py` bundle, containing raw mutation
  outcomes and timings. EXP-T01 expanded the matrix to 13 canonical-state
  mutations with declared expected outcomes and target objects, plus an
  unsigned operational-field negative control; all 13 were detected and the
  control verified.
- Threats: single database, local key and ledger; no external trust anchor or
  coordinated database+key+ledger replacement.

### RQ6 — Peer-cohort sensitivity

**Question:** Does the existing peer worker abstain below its minimum cohort
size and signal a subject when its closure behavior crosses the configured
deviation rule? **Hypothesis:** two peers produce no peer finding; with at
least three peers, sufficiently large deviations may emit one.

- Independent variables: peer count (2, 3, 4) and subject closure time (30,
  400, 750 seconds), each in a separate exact-match synthetic cohort.
- Dependent variables: peer count, median/MAD and actual emitted peer finding.
- Baseline: same controlled peer closure values and the configured 3-peer,
  2-MAD policy.
- Unit: synthetic subject/cohort.
- Statistics: report each generated cohort and its output; no distributional
  generalization from these deliberately small cohorts.
- Artifact: `run_peer_sensitivity_experiment.py` immutable bundle.
- Pilot observation: peer counts 2 and 3 emitted no finding, while count 4
  emitted a finding; at four peers, the 30-second subject was flagged and
  400/750 seconds were not. At count 3, the 30-second subject was 1.9 MAD
  from the measured peer median, below the configured 2-MAD rule.
- Threats: one alert per entity; only critical closure median is informative;
  values are controlled, not observed CSE behavior.

## Baseline and ablation definitions

- **Closure-time baseline:** z-score, MAD, IQR, fixed threshold, and seeded
  random flagging operate on identical construction-labelled close times;
  SAT-SA `FastClosureWorker` runs on the same canonical alerts. Thresholds and
  labels are not tuned from SAT-SA output.
- **Prioritization baseline:** random permutation of the same generated entity
  population, 200 trials by default, seeded independently from label assignment.
  Each recall@K/review-volume permutation result is retained in raw metrics;
  mean, quartiles and range summarize this finite randomization distribution.
  Those quartiles are not confidence intervals.
- **Ablation:** run the existing `RunService` with all default workers and then
  remove one worker per run on the same ingested mixed-scenario scope. Report
  disappeared finding families. Do not interpret absence in this one scope as
  proof a worker is unhelpful generally.
- **Not a baseline:** human examiner review; no matched human study exists.

## Statistical and metric policy

For binary flag metrics, `TP`, `FP`, `FN`, and `TN` use independently assigned
labels. Precision is `TP/(TP+FP)` and recall is `TP/(TP+FN)`; a zero denominator
is undefined (`null`). F1 is `2PR/(P+R)` when defined and zero when both defined
values are zero. Family metrics are micro-aggregated across executed scenarios.
Action alignment is exact matches divided by executed scenarios. Recall@K is
pathological entities in top K divided by all pathological entities. Random
lift is SAT-SA recall@K divided by the empirical mean random recall; if the
random mean is zero, the result is explicitly handled by the runner.

The workload runner retains a finite seeded randomization distribution with
raw trials and descriptive mean/quartiles/range. These are not confidence
intervals. No inferential test or statistical significance claim is made for
the 5-case catalog, one generated population, or the small peer/trust
experiments. Future method comparisons must preserve paired inputs and use
independently generated seed-level datasets as the replication unit; interval,
effect-size and multiple-comparison methods must be fixed before inspecting
confirmatory outputs.

## Data boundaries and limitations

The controlled benchmark uses synthetic fixture builders, construction-defined
closure labels, and seeded synthetic populations. Expert-label sample files
remain templates; no real expert-labeled corpus is available. CIC-IDS2017 and
BOTS adapters have not been executed against the actual downloaded datasets.
No human examiner time/agreement study has run. The Phase 7 local multi-service
deployment, live PostgreSQL, live S3, and hosted deployment were not verified.
The current benchmark is an isolated scratch SQLite/synchronous evaluation,
not a performance test of the production API/worker/S3 topology.

No result should be described as evidence that SAT-SA is novel, superior to
human examination, validated on real CSE/SOC operations, or production-scalable.
