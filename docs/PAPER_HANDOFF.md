# Paper Handoff

Factual substrate for writing the SAT-SA paper. Every empirical statement
below has a frozen artifact in `research/evidence/freeze-v2/` and a row in
`research/evidence/catalog.json`. This is not the paper and is not
promotional. Companion documents: [PAPER_EVIDENCE_INDEX.md](PAPER_EVIDENCE_INDEX.md),
[EVIDENCE_FREEZE.md](EVIDENCE_FREEZE.md), [STATISTICAL_AUDIT.md](STATISTICAL_AUDIT.md),
[RESEARCH_LIMITATIONS.md](RESEARCH_LIMITATIONS.md),
[EXTERNAL_FAILURE_ANALYSIS.md](EXTERNAL_FAILURE_ANALYSIS.md),
[LITERATURE_POSITIONING.md](LITERATURE_POSITIONING.md),
[EXPERIMENTS.md](EXPERIMENTS.md).

**Manuscript (Phase 12):** `paper/manuscript.tex` (compiled `paper/manuscript.pdf`),
with every number generated into `paper/data/paper-data.json` / `values.tex` by
`scripts/build_paper_assets.py` and checked by `scripts/audit_paper.py`. Reproduction
package: `paper/REPRODUCIBILITY.md`; supplementary material: `paper/supplementary/`;
literature matrix: `paper/literature-matrix.csv` (48 verified, cited sources; 33 from
Phase 12 plus 15 from the Phase 13 structured search in `paper/literature-review/`,
77 sources included there in total). IEEE Access package: `paper/submission/`; release
candidate and gate: `paper/release-candidate/`, `docs/SUBMISSION_GATE.md`. Hackathon
narrative: [SIH_TECHNICAL_NARRATIVE.md](SIH_TECHNICAL_NARRATIVE.md).

## Paper-safe title candidates

1. SAT-SA: Record-Level Analytics for Supervising Security Operations Centres, with Controlled and External Evaluation
2. Evidence-Cited Supervisory Analytics for SOC Assessment: Design, Controlled Evaluation and an External Negative Result
3. From Controlled Scenarios to an External Incident Log: Evaluating a Supervisory SOC Analytics System

## Research problem

Supervisors (e.g. national critical-infrastructure authorities) must assess
many SOCs periodically. Existing practice relies on self-assessed maturity
models and manual examination of records. The problem studied: can a system
analyse a SOC's submitted operational records (alerts, cases, investigation
steps, escalations, dispositions, assets) to produce evidence-cited
supervisory findings and priorities, keep a human supervisor as the decision
authority, and bind the reviewed state cryptographically — and how does such
a system behave under controlled perturbation and on independent data?

## Research questions

| RQ | Question | Experiments |
| --- | --- | --- |
| RQ1 | Does the pipeline emit the declared finding families on controlled scenarios? | C01 |
| RQ2 | How do detectors compare with simple baselines, which components contribute, and how does prioritization compare with baselines? | C01, A01, PR01 |
| RQ3 | Can findings be traced to source records through an authorized decision and a verifying receipt? | T01, D01 |
| RQ4 | How does the system behave with missing, duplicated, malformed, stale or contradictory evidence? | R01b |
| RQ5 | Does TRUST-SAT detect changes to the finalized supervisory record? | T01 |
| RQ6 | How sensitive is peer benchmarking to cohort size and spread? | P01 |
| RQ7 | What do durable orchestration and TRUST-SAT cost, and does the workflow recover from interruption? | O01, O02 |
| EXT | What happens on an independent real workflow dataset, and why? | X02b, X03 |

## Candidate contributions (from the final contribution map)

- **Candidate (low confidence):** framing SOC supervision as record-level,
  evidence-cited analytics for an external supervisor — an application
  framing; the detection techniques are adaptations of known methods.
- **Empirical findings:** controlled robustness, ablation, prioritization,
  peer sensitivity and orchestration results, and an external negative
  result with a diagnosed cause.
- **Engineering:** tenant-aware persistence, versioned submissions, durable
  queue/worker, LangGraph review interrupt with recovery.
- **Security capability (integration):** ML-DSA-65 signed, ledger-bound
  supervisory receipts.
- **Not contributions:** research infrastructure (bundles, freeze, exports).

## System description (for the architecture section)

Periodic submission → hosted validation (all-or-nothing, per-record
provenance) → 16 deterministic workers (execution gap, negative space,
anomaly, peer benchmark, coverage gap, evidence completeness, workflow
reconstruction, case similarity, and others) → risk (7 weighted dimensions,
confidence-based saturating fusion) → recommendations → human supervisory
decision (review interrupt; direct or LangGraph orchestration) → TRUST-SAT
finalization (SHA3-256 canonical document, ML-DSA-65 signature, hash-chained
ledger) → verification. Figure 1 (architecture) has no data dependency.

## Evaluation protocol

Declared-before-execution labels and perturbations; one isolated database
per condition; write-once bundles with manifests (dataset, seed,
configuration digest, commit, environment, hashes); freeze with verification;
no tuning on evaluation data; paired comparisons; descriptive bootstrap
intervals; no p-values (see STATISTICAL_AUDIT.md).

## Datasets

| Dataset | Type | Use |
| --- | --- | --- |
| Controlled catalog v1.0.0 (5 executable scenarios) | controlled synthetic | C01, R01b, A01, O01, O02 |
| Generated workload populations (seeds 100–119; 300–304) | controlled synthetic | PR01, A01 |
| Engineered peer cohorts (96 cells) | controlled synthetic | P01 |
| One controlled trust workflow | controlled synthetic | T01 |
| UCI-498 incident management event log (CC BY 4.0; 50 groups, 22,604 incidents) | external, IT service management (not SOC) | X02b, X03 |

## Baselines

Closure-time: z-score, MAD, IQR, fixed threshold, seeded random (C01).
Prioritization: seeded random order, critical/high alert volume, fastest
median closure (PR01). Ablation: full worker set (A01). Orchestration: direct
execution and an unreviewed configuration (O01). External: random, incident
volume, slowest median resolution, reassignment rate (X02b).

## Canonical results (paper-safe wording)

- In five controlled catalog scenarios, SAT-SA emitted every declared finding
  family (micro recall 1.0) with additional undeclared families (precision
  0.417, F1 0.588); the expected supervisory action matched in 4 of 5
  scenarios (C01).
- On 12 construction-labelled closures, the fast-closure detector achieved
  F1 1.0, as did the fixed-threshold and MAD baselines; z-score and IQR
  flagged none (C01).
- In controlled perturbation of the five scenarios, hosted validation matched
  its declared contract in all 245 conditions with a declared expectation;
  records shifted outside the assessment period and contradictory records
  were accepted without warning (R01b).
- Across 20 generated populations, SAT-SA's ranking captured more
  generator-labelled pathological entities in the top 20% than random order
  (median paired difference in recall +0.59, 95% bootstrap 0.41–0.60) and
  alert-volume ranking (+0.40, 0.30–0.60); against a fastest-median-closure
  heuristic the median difference was 0 (0–0.2): higher in 8 populations,
  equal in 11, lower in 1 (PR01).
- Removing the fast-closure or negative-space worker lowered micro recall on
  the catalog scenarios from 1.0 to 0.6 (A01).
- In the evaluated workflows on one machine with SQLite, LangGraph execution
  produced outputs identical to direct execution and added a median 0.096 s
  per workflow (95% bootstrap −0.020 to 0.211 s over 30 paired runs) and 38
  database calls; supervisory finalization took a median 0.288 s and receipt
  verification 0.062 s (O01).
- All 36 injected interruptions recovered with outputs identical to
  uninterrupted execution and without repeating completed stages (O02).
- TRUST-SAT detected all 13 tested single-field mutations in the controlled
  mutation matrix; a change to an unsigned operational field did not affect
  verification (T01).
- The peer rule never fired with fewer than 3 peers; with a tight peer spread
  it flagged every non-median subject from 3 peers, with a wide spread only
  extreme subjects (P01).
- The external IT incident dataset provided feasibility evidence — all
  134,888 mapped rows were accepted and all 50 group analyses completed — but
  did not establish an association between SAT-SA risk and SLA misses
  (Spearman ρ −0.11, 95% bootstrap −0.42 to 0.21), whereas slowest median
  resolution was strongly associated (ρ 0.94) (X02b).
- The failure analysis attributes the external result mainly to construct
  mismatch: on this data, groups with more fast closures missed SLA less
  (ρ −0.70, −0.82 to −0.52), so SAT-SA's execution-gap risk dimension ran
  opposite to the outcome (ρ −0.41); four detectors fired for all 50 groups
  and three risk dimensions had no input data (X03).

## Negative findings (keep in Discussion/Limitations)

1. A closure-speed heuristic is comparable to SAT-SA on generated populations (PR01).
2. Fixed-threshold and MAD baselines tie the fast-closure detector (C01).
3. External risk vs SLA miss ρ −0.11; slowest resolution ρ 0.94 (X02b).
4. Construct inversion of the fast-closure signal on ITSM data (X03).
5. Detector saturation of existence rules at scale (X03).
6. Stale and contradictory evidence accepted silently (R01b).
7. Peer findings depend strongly on cohort composition (P01).
8. Four workers lowered population ranking quality when present (A01, exploratory).
9. A real product defect (withheld finding) was found by evaluation and fixed (R01 → R01b).

## Unsupported claims (must not appear without new evidence)

- real-world SOC effectiveness; SOC validation; production validation
- external effectiveness (the external result is negative and domain-mismatched)
- production-scale performance; enterprise-scale deployment; scalability
- state-of-the-art, best, leading, superior, outperforms, first, novel
- universal robustness
- expert-validated findings or recommendations
- human review improvement (speed, accuracy, agreement, trust)
- a general tamper-detection rate; "tamper-proof"
- verified container, PostgreSQL, S3 or hosted deployment
- statistical significance of any result

## Figure list (source data in `freeze-v2/exports/figures/`, index `figures-index.json`)

| Figure | Data | Source |
| --- | --- | --- |
| 1 Architecture | none | this document |
| 2 Prioritization vs baselines | FIG-2-prioritization.csv | PR01 |
| 3 Ablation | FIG-3-ablation.csv | A01 |
| 4 Peer sensitivity | FIG-4-peer-sensitivity.csv | P01 |
| 5 Missing-evidence robustness | FIG-5-missing-evidence-robustness.csv | R01b |
| 6a LangGraph overhead | FIG-6a-langgraph-overhead.csv | O01 |
| 6b Recovery | FIG-6b-recovery.csv | O02 |
| 6c TRUST-SAT overhead | FIG-6c-trust-overhead.csv | O01 |
| 7 External risk vs SLA miss | FIG-7-external-risk-vs-sla.csv | X02b |
| 8 External construct inversion | FIG-8-external-construct-inversion.csv | X03 |

## Table list (source data in `freeze-v2/exports/`)

| Table | Files | Source |
| --- | --- | --- |
| System/dataset characteristics | dataset_characteristics.* | all canonical |
| Baseline comparison | baseline_closure_time.*, prioritization*.* | C01, PR01 |
| Ablation | ablation_scenario.*, ablation_population.* | A01 |
| Robustness | robustness_by_family.*, robustness_omission.* | R01b |
| Orchestration overhead | orchestration_modes.*, orchestration_comparisons.* | O01 |
| Recovery | recovery.* | O02 |
| TRUST-SAT integrity | integrity_mutations.* | T01 |
| Peer sensitivity | peer_sweep.* | P01 |
| External validation | external_association.*, external_ranking.*, external_detector_saturation.*, external_failure_*.*, external_construct_validity.* | X02b, X03 |
| Deployment/performance | deployment_smoke_local_processes.* (local processes only), orchestration_modes.* | D01, O01 |
| Statistical audit | statistical_audit.* | all canonical |

No table exists for PostgreSQL, container or hosted performance: those
experiments are BLOCKED.

## Human evaluation and expert labels

Human review study: **PROTOCOL READY — STUDY NOT EXECUTED**
([HUMAN_REVIEW_PROTOCOL.md](HUMAN_REVIEW_PROTOCOL.md)). Expert labels:
**LABELING PIPELINE READY — NO EXPERT-LABELLED DATA AVAILABLE**
(`evaluation/research/expert_labels.py`).

## Citation/source list

See the verified source table in [LITERATURE_POSITIONING.md](LITERATURE_POSITIONING.md)
(SOC-CMM; SOC analyst performance and technical metrics papers in
*Computers & Security*; ACM Computing Surveys on alert fatigue and alert
prioritisation; GUIDE, AIP and learning-to-defer papers; Bolton & Hand peer
group analysis; van der Aalst conformance checking; DeTT&CT; BIS suptech;
Schneier & Kelsey; Crosby & Wallach; FIPS 204; W3C PROV-DM; Parasuraman &
Manzey) plus the UCI-498 dataset (DOI 10.24432/C57S4H). A systematic
literature review is still required before the related-work section is
final.
