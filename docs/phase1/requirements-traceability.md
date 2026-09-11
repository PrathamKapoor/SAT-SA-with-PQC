# SAT-SA Phase 1 — Requirements traceability

Every row is `SIH/SAT requirement -> SAT-SA capability -> module -> UI surface -> validation method -> status`. Status values follow Part O of the brief: **EXISTING** (implemented and usable as-is), **ADAPT** (existing code changes meaning/shape), **BUILD** (no existing implementation), **INTEGRATE** (existing pieces must be wired together), **DOCUMENT** (capability exists, needs written explanation), **VERIFY** (appears present, unconfirmed). Module names are verified paths from [existing architecture](existing-architecture.md); no module below is invented. `SAT-*` IDs not present in the SIH brief are introduced here for anything Parts D-T require but SIH26157 does not itself enumerate; they are cross-referenced from the other Phase 1 documents rather than re-derived.

## C1 — Primary supervisory objectives

| ID | Capability | Module | UI surface | Validation | Status |
|---|---|---|---|---|---|
| SIH-OBJ-01 Identify entities needing attention | Entity risk dimensions + priority ordering | *new* `satsa.risk` (synthesis coordinator, [agent architecture](agent-architecture.md)) | Overview, Entity view | Expert top-K agreement ([validation strategy](validation-strategy.md)) | BUILD |
| SIH-OBJ-02 Prioritize alert samples/investigations for review | Lexicographic review queue | *new* `satsa.review` | Review Queue | Workload/coverage evaluation vs FIFO/random baseline | BUILD |
| SIH-OBJ-03 Detect operational weaknesses/resilience concerns | Execution-gap + resilience detectors | *new* `satsa.analytics` detectors ([analytics architecture](analytics-architecture.md)) | Findings, Analytics | Detector fixtures + expert-labeled cases | BUILD |
| SIH-OBJ-04 Improve efficiency/consistency/scalability of assessment | End-to-end deterministic pipeline + explainable synthesis | *new* orchestration reusing `evidence/`, `crypto/` | All surfaces | Reproducibility test (same inputs -> same findings) | BUILD, reuses EXISTING trust primitives |

`agents/base.py`, `supervisor/validation.py` and `supervisor/supervisor.py` supply typed evidence/finding/observation contracts and output validation that the new synthesis coordinator will reuse (ADAPT, not BUILD-from-zero) — see the module boundary table in [existing architecture](existing-architecture.md).

## C2 — Out-of-scope safeguards

| ID | Boundary | Architectural safeguard | Status |
|---|---|---|---|
| SIH-OOS-01 Not a SOC replacement | No case-handling/ticketing workflow; only periodic evidence ingestion and read-only analysis | DOCUMENT as a hard scope line in `satsa.ingestion` design |
| SIH-OOS-02 Not real-time monitoring | Ingestion accepts only closed periodic submissions with a declared cutoff (`Assessment.submission_cutoff`, [data architecture](data-architecture.md)); no streaming endpoint | BUILD with the constraint enforced at the API boundary |
| SIH-OOS-03 Not a SIEM | No log/event correlation engine, no rule-based real-time alerting; detectors run once per assessment run on a frozen snapshot | BUILD — the analytical contract in [analytics architecture](analytics-architecture.md) forbids continuous evaluation |
| SIH-OOS-04 Not a centralized SOC for multiple CSEs | Cross-CSE features are read-only de-identified aggregates for peer benchmarking only ([data architecture](data-architecture.md) storage/isolation section); no shared incident queue across CSEs | BUILD with suppression rules for small cohorts |
| SIH-OOS-05 Not continuous log/telemetry collection | Coverage summaries are periodic aggregate counts, never raw log ingestion (`Coverage summary` record, [data architecture](data-architecture.md)) | BUILD, schema-enforced |
| SIH-OOS-06 Not a national cyber monitoring platform | Single-installation, per-assessment-cycle scope; no always-on collection agent, no push telemetry client shipped to CSEs | DOCUMENT explicitly in [deployment architecture](deployment-architecture.md) |

## C3 — Supported data environment

| ID | Capability | Module | Status |
|---|---|---|---|
| SIH-DATA-01 Alert metadata | `Alert` record + adapter | *new* `satsa.ingestion` | BUILD |
| SIH-DATA-02 Case-management records | `Case` record | *new* `satsa.ingestion` | BUILD |
| SIH-DATA-03 Investigation workflow data | `Investigation step` record | *new* `satsa.ingestion` | BUILD |
| SIH-DATA-04 Escalation records | `Escalation` record | *new* `satsa.ingestion` | BUILD |
| SIH-DATA-05 Disposition/closure information | `Disposition/closure` record | *new* `satsa.ingestion` | BUILD |
| SIH-DATA-06 Asset/system inventory | `Asset/system` record, optional | *new* `satsa.ingestion` | BUILD |

`database/engine.py`, `database/migrations.py` (SQLite engine, WAL, migration runner) are EXISTING and reusable transport; the fifteen tables they define are MLOps-shaped and do not implement these six records (verified: only `AuditEventRepository`/`IdentityRepository` have insertion paths — [existing architecture](existing-architecture.md)). New SAT-SA tables/migrations are BUILD on top of an ADAPTed engine.

## C4 — Execution-gap analytics

| ID | Method classification (from [analytics architecture](analytics-architecture.md)) | Module | Status |
|---|---|---|---|
| SIH-EG-01 Acknowledged, not investigated | Deterministic rule (required action classes + sequence completeness) | Workflow analysis worker | BUILD |
| SIH-EG-02 Unusually fast closure | Statistical (robust lower-tail quantile + effect size) | Workflow analysis worker | BUILD |
| SIH-EG-03 Critical closure without escalation | Deterministic rule + timeline validation | Workflow analysis worker | BUILD |
| SIH-EG-04 Repetitive investigations | Sequence/text similarity | Workflow analysis worker | BUILD |
| SIH-EG-05 Controls deployed, not monitored | Coverage expectation graph | Coverage analysis worker | BUILD |
| SIH-EG-06 Metrics satisfied without risk reduction | Longitudinal joint-trend analysis | Longitudinal analysis worker | BUILD |

`ml/drift.py` (PSI, KS, rolling metric history) is EXISTING and ADAPTable for SIH-EG-06's longitudinal trend detection once re-scoped from model metrics to matched CSE periods (statistical assumptions must be re-validated per [quantum-trust-audit.md](quantum-trust-audit.md) sibling audit in [analytics architecture](analytics-architecture.md)).

## C5 — Negative-space analytics

| ID | Required context | Module | Status |
|---|---|---|---|
| SIH-NS-01 Missing critical telemetry | Critical inventory + expected interval + coverage summary | Coverage analysis worker | BUILD |
| SIH-NS-02 Absent alert categories | Applicable categories + historical rate + exposure | Coverage analysis worker | BUILD |
| SIH-NS-03 Missing investigations | Eligible population + workflow completeness | Workflow analysis worker | BUILD |
| SIH-NS-04 Missing escalation records | Escalation obligation + exceptions | Workflow analysis worker | BUILD |
| SIH-NS-05 Unexpectedly low activity | Historical matched periods + exposure | Longitudinal analysis worker | BUILD |
| SIH-NS-06 Monitoring blind spots | Asset-control-category expectation graph | Coverage analysis worker | BUILD |
| SIH-NS-07 Evidence absent vs peers | Comparable cohort + normalized coverage | Comparative analysis worker | BUILD |

No existing module computes contextual absence; the nine-agent MLOps layer has no coverage/expectation concept (VERIFY confirmed negative during agent audit — [agent architecture](agent-architecture.md)). All SIH-NS-* are BUILD.

## C6 — General supervisory analytics

| ID | Capability | Status |
|---|---|---|
| SIH-AN-01 Detection weakness | Coverage worker output | BUILD |
| SIH-AN-02 Investigation weakness | Workflow worker output | BUILD |
| SIH-AN-03 Escalation weakness | Workflow worker output | BUILD |
| SIH-AN-04 Execution gaps | SIH-EG-01..06 aggregate | BUILD |
| SIH-AN-05 Negative space | SIH-NS-01..07 aggregate | BUILD |
| SIH-AN-06 Anomalies | Robust standardized features; `ml/drift.py` PSI/KS ADAPTed | Comparative/longitudinal worker | ADAPT + BUILD |
| SIH-AN-07 Outliers | Same as AN-06 | ADAPT + BUILD |
| SIH-AN-08 Suspicious operational patterns | Cross-detector corroboration in synthesis | Synthesis coordinator | BUILD |
| SIH-AN-09 Peer comparison | Cohort manifest + normalized rate comparison | Comparative worker | BUILD |
| SIH-AN-10 Benchmarking | Same as AN-09 | BUILD |
| SIH-AN-11 Entity-level supervisory risk indicators | SAT-RISK-01..06 dimension vector | Synthesis coordinator | BUILD |
| SIH-AN-12 Entity prioritization | SAT-PRI-01 methodology | Review prioritization | BUILD |
| SIH-AN-13 Control prioritization | SAT-PRI-01 methodology, control level | Review prioritization | BUILD |
| SIH-AN-14 Process prioritization | SAT-PRI-01 methodology, process level | Review prioritization | BUILD |
| SIH-AN-15 Alert-sample prioritization | SAT-PRI-01 methodology, alert level | Review prioritization | BUILD |

`scores.py` and `supervisor/supervisor.py` weighted aggregation (1/4/10/25 severity, max/mean combination) are EXISTING but explicitly must **not** be reused for SIH-AN-11 (documented decision in [analytics architecture](analytics-architecture.md) — no SOC calibration evidence for those weights).

## C7 — Explainability

| ID | Capability | Module | Status |
|---|---|---|---|
| SIH-EX-01 Clear rationale | Typed `Signal/finding` record with rule/statistic/threshold fields | *new* `satsa.domain` | BUILD |
| SIH-EX-02 Supporting evidence | `source_record_ref` chain to immutable bytes | `artifacts/store.py` (EXISTING, ADAPT for verified reads) | ADAPT |
| SIH-EX-03 Traceability | Finding -> signal -> evidence -> source record chain | *new* synthesis + EXISTING `artifacts/store.py` | BUILD + ADAPT |
| SIH-EX-04 Auditability | Signed envelopes + hash-chained ledger | `evidence/ledger.py`, `evidence/packet.py` (EXISTING, hardening required per [quantum-trust-audit.md](quantum-trust-audit.md)) | ADAPT |
| SIH-EX-05 Human-readable explanation | Rationale text generation from typed finding fields (no LLM) | *new* synthesis coordinator | BUILD |

## C8 — Reporting

| ID | Capability | Module | UI surface | Status |
|---|---|---|---|---|
| SIH-RP-01 Supervisory dashboards | Overview + Entity views | *new* API + UI | Overview, Entities | BUILD |
| SIH-RP-02 Supervisory reports | Exportable signed report manifest | *new* reporting service | Reports | BUILD |
| SIH-RP-03 Trend across entities | Comparative worker outputs | Analytics, Benchmarks | BUILD |
| SIH-RP-04 Trend across periods | Longitudinal worker outputs | Analytics | BUILD |
| SIH-RP-05 Drill-down finding->evidence | Evidence chain UI | Evidence | BUILD, depends on SIH-EX-03 |

`api/app.py` (EXISTING) is a legacy MLOps dashboard API (`/models`, `/registry`, `/agents`, `/security`, `/dashboard` — verified route list) and is **not** reusable as the SAT-SA reporting API; a versioned `/api/v1/assessments`/`/findings`/`/reviews` surface is BUILD, kept separate per [existing architecture](existing-architecture.md).

## Parts D-T — SAT-* requirements introduced by this Phase 1

| ID | Source part | Capability | Module | Status |
|---|---|---|---|---|
| SAT-ADD-01..08 | Part D | Metric gaming, repeat/root-cause gap, similarity, drift, cross-CSE pattern, evidence completeness, confidence, human feedback | *new* longitudinal/comparative workers + review decisions | BUILD (all; specified in [analytics architecture](analytics-architecture.md)) |
| SAT-AG-01 | Part E | Bounded worker + synthesis coordinator agent design | `agents/base.py` contracts ADAPTed; workers BUILD | ADAPT + BUILD |
| SAT-RISK-01..06 | Part F | Detection/investigation/escalation/discipline/coverage/resilience dimensions | Synthesis coordinator | BUILD |
| SAT-PRI-01 | Part G | Lexicographic entity->control->process->case->alert->evidence prioritization | Review prioritization service | BUILD |
| SAT-TR-01 | Part H | Signed assessment envelope (distinct from model passport) | `passport/passport.py` pattern ADAPTed | ADAPT |
| SAT-TR-02 | Part H | Signer/verifier/key-policy hardening (QT-01..07) | `crypto/` | ADAPT |
| SAT-TR-03 | Part H | Provenance writer / verify bundle across lifecycle stages | `evidence/` | ADAPT |
| SAT-TR-04 | Part H | Independent checkpoint anchor (external to ordinary storage) | *new*, no existing equivalent | BUILD |
| SAT-TR-05 | Part H | Durable transactional publication (outbox pattern) | `evidence/ledger.py` ADAPTed | ADAPT |
| SAT-TR-06 | Part H | v1/v2 migration without retroactive re-signing | `passport/`, `evidence/` | ADAPT |
| SAT-UI-01..09 | Part I | Overview, Entities, Findings, Review Queue, Analytics, Benchmarks, Evidence, Reports, System/Deployment status | *new*, no frontend exists (verified) | BUILD |
| SAT-DEMO-01 | Part J/K | Multi-CSE demo dataset with internal ground truth, one-click walkthrough | *new*; `demo.py` pattern (MLOps-only, EXISTING) is not reusable content, only reusable as a CLI-invocation pattern | BUILD |
| SAT-OFF-01 | Part L | Local database/models/analytics/crypto/reporting, no external API | `core/`, `database/`, `crypto/` (EXISTING, local-only) | ADAPT: bootstrap script and dependency install currently require internet (verified) |
| SAT-OFF-02 | Part L | Air-gapped installation bill of materials | *new* packaging | BUILD |
| SAT-ENG-01 | Part M | Modularity, typed interfaces, structured logging, error codes | `core/logging.py`, `core/errors.py` (EXISTING, reusable as-is) | EXISTING |
| SAT-VAL-01..05 | Part N | Precision/recall/prioritization-effectiveness methodology vs expert review | *new*, no expert-labeled data exists yet | BUILD (methodology); data collection is an operational dependency, not code |

## Coverage check

Every SIH-* ID enumerated in Parts C1-C9 of the brief appears above. No SIH requirement is classified EXISTING: the repository has no SOC-domain analytics, no negative-space logic, no CSE data model and no frontend (all confirmed absent during the audit, not merely undiscovered). The only EXISTING/ADAPT classifications are for underlying platform primitives (trust, storage, logging, error handling, validation contracts) that SAT-SA's new domain logic will sit on top of. This asymmetry — strong trust/engineering foundation, zero domain-specific analytics — is the central finding carried into [gap analysis](gap-analysis.md) and the [final report](phase1-final-report.md).
