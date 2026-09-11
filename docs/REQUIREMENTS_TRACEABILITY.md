# Requirements traceability — SIH26157 → SAT-SA

Every functional requirement from the SIH26157 problem statement,
traced to a component, source file, test, demo step, and
documentation reference. Where a requirement is not fully met, that is
stated here rather than left implicit.

## Data ingestion

| # | Requirement | Component | Source | Test | Demo step |
|---|---|---|---|---|---|
| 1 | Ingest structured data from multiple CSEs | Ingestion Agent | `satsa/ingest/service.py` | `test_phase3_satsa_ingestion.py` | Step 1 (5 CSEs) |
| 2 | Support CSV, JSON, DB exports, APIs where available | Ingestion Agent, DB adapter | `satsa/ingest/readers.py`, `satsa/ingest/db_adapter.py` | `test_phase55_satsa_db_adapter_validation.py` | `sat-sa ingest` |
| 3 | Support large datasets, multiple entities/periods | Ingestion, Drift Agent | `satsa/ingest/service.py`, `satsa/analysis/drift.py` | `scripts/benchmark_scaling.py` (5/10/25/50 CSE, **100/1000 pending**), `test_phase37_satsa_drift.py` | — |

## Supervisory analytics

| # | Requirement | Component | Source | Test | Demo step |
|---|---|---|---|---|---|
| 4 | Detection/investigation/escalation weakness indicators | Execution Gap Agent | `satsa/analysis/workers/` (6 detectors) | `test_phase5_satsa_execution_gaps.py` | Step 5 |
| 5 | Detect potential execution gaps | Execution Gap Agent | as above | as above | Step 5 |
| 6 | Detect potential negative space | Negative Space Agent | `satsa/analysis/workers/negative_space.py` | `test_phase6_satsa_negative_space.py` | Step 5 |
| 7 | Anomalies, outliers, suspicious patterns | Anomaly Agent | `satsa/analysis/workers/anomaly.py` | `test_phase7_satsa_anomaly.py` | Step 5 |
| 8 | Peer comparison / benchmarking | Peer Benchmark Agent | `satsa/analysis/workers/peer_benchmark.py` | `test_phase8_...`, `test_phase30_...`, `test_phase47_...` | Step 5 |
| 9 | Entity-level supervisory risk indicators | Fusion Agent (risk) | `satsa/analysis/risk.py` | `test_phase9_satsa_entity_risk.py` | Step 4 |
| 10 | Prioritise entities/controls/processes/samples | Prioritization Agent | `satsa/analysis/prioritize.py` | `test_phase10_...`; simulated lift measured in `tests/test_phase67_satsa_workload_reduction.py` | Step 3, 6 |

## Explainability

| # | Requirement | Component | Source | Test | Demo step |
|---|---|---|---|---|---|
| 11 | Clear rationale for findings | every worker (`rationale` field on `Finding`) | `satsa/domain/evidence.py` | exercised across every worker test | Step 5 |
| 12 | Present supporting evidence | `evidence_refs` on `Finding`, drill-down to `satsa_source_records` | `satsa/ui/__init__.py::finding_detail` | `test_phase64_satsa_fresh_database_e2e.py` asserts every finding cites evidence | Step 5 |
| 13 | Traceability and auditability | TRUST-SAT (signed digests) + review audit trail | `satsa/analysis/trust.py`, `satsa/analysis/review.py` | `test_phase44_...`, `test_phase66_...` | Step 7–9 |
| 14 | Understand why something was flagged | Recommendation Agent (`recommend()` cites the triggering finding) | `satsa/analysis/recommend.py` | `test_phase64_...` asserts report HTML contains the actual rule id | Step 6 |

## Reporting

| # | Requirement | Component | Source | Test | Demo step |
|---|---|---|---|---|---|
| 15 | Supervisory dashboards and reports | UI (16 pages) + `sat-sa report` | `satsa/ui/`, `satsa/analysis/report.py` | `test_phase14_satsa_ui.py`, `test_phase56_satsa_premium_pages.py` | live UI walkthrough |
| 16 | Trend analysis across entities/periods | Drift Agent, Cross-Entity Insights Agent | `satsa/analysis/drift.py`, `insights.py` | `test_phase37_...`, `test_phase38_...`, `test_phase60_...` | — |
| 17 | Drill-down from finding to underlying evidence | `/findings/{id}` UI page, `/api/*` | `satsa/ui/__init__.py` | `test_phase14_satsa_ui.py` | Step 5 |

## Deployment requirements

| # | Requirement | Component | Source | Test | Status |
|---|---|---|---|---|---|
| Offline / air-gapped | no network dependency | full pipeline | `tests/test_phase18_satsa_offline_hardening.py` | verified |
| No cloud / SaaS / external AI | architecture | entire `satsa/`, `qsmlops/` | offline-hardening test; manual dependency audit (`requirements.txt` — no cloud SDKs) | verified |
| Local deployment, local processing | `scripts/serve_ui.py`, `sat-sa` CLI | `docs/deployment.md` | live-tested this session (server started, pages verified 200) | verified |
| AI/ML disclosure (architecture, hardware, offline training/inference, explainability, auditability) | robust statistics (median/MAD/percentile), not opaque ML | `satsa/analysis/anomaly.py`, `peer_benchmark.py` | see `docs/CLAIMS.md` | this project deliberately uses statistical/rule-based analytics, not trained ML models, for its core detectors — disclosed as a design choice (section 95's own instruction: "a rigorous hybrid analytics system is better than fake AI branding") |

## Illustrative supervisory use cases (from the SIH spec)

| Use case | Component | Evidence this is real, not aspirational |
|---|---|---|
| High-severity alerts closed unusually quickly | `execution_gap.fast_closure` | fires in the live demo (CSE-EXEC) and in `tests/test_phase64_...`'s independently-generated fixtures |
| Repeated alerts on same asset without root-cause remediation | `execution_gap.recurring_without_remediation` | fires in `tests/test_phase64_...`'s negative-control test (a real, not injected-for-the-test, structural finding) |
| Critical alerts closed without escalation | `execution_gap.critical_without_escalation` | was the subject of a real false-positive bug found and fixed this session (`tests/test_phase65_satsa_partial_ref_resolution.py`) |
| Critical systems with little/no telemetry | `negative_space.missing_monitoring` | fires in the live demo (CSE-NEG) |
| Significant peer deviations | `peer_benchmark.*` | fires in the live demo; cohort-gated, abstains when `n < min_peers` |
| Repetitive investigation patterns | Case Similarity Agent | `satsa/analysis/case_similarity.py`, `test_phase36_...` |
| Metric-satisfying-without-risk-reducing behavior | `execution_gap.potential_metric_gaming` | implemented, tested (`test_phase5_...`); **not yet adversarially stress-tested** — see `docs/roadmap-status.md` for what remains open |

## Performance criteria (weighted, from the SIH spec)

| Criterion | Where addressed |
|---|---|
| Ability to support supervisory assessment | Full pipeline demo, `docs/CLAIMS.md` |
| Detection of execution gaps | Execution Gap Agent, above |
| Detection of negative space | Negative Space Agent, above |
| Explainability and auditability | Explainability section above, TRUST-SAT |
| Scalability and performance | `scripts/benchmark_scaling.py` (5–50 CSE verified; 100/1000 pending) |
| Innovation / additional supervisory insights | Drift, Cross-Entity Insights, Case Similarity — all beyond the SIH spec's explicit list |

## Validation requirement

The SIH spec explicitly asks: "explain how the proposed solution will
be validated against findings derived from expert manual review."

Honest answer: the infrastructure is built and tested
(`satsa/analysis/validate.py`'s YES/NO/UNLABELED framework, the
`ExpertLabel` schema, `sat-sa validate --expert-labels <path>`) but no
real expert manual review has occurred — `docs/demo/EXPERT_LABELS.md`
discloses the shipped sample file as an illustrative template. This is
the single most consequential "pending, not fabricated" item in the
whole project; see `docs/CLAIMS.md`.
