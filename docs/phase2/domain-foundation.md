# SAT-SA Phase 2 — Domain foundation (Part H)

Status: **FOUNDATION ONLY** — typed, validated domain records exist (`satsa/domain/`); ingestion parsing, persistence, and detector logic that would read these records do not exist yet and are explicitly later-phase work.

## Why a new top-level package, not another `qsmlops` subpackage

[target-architecture.md](../phase1/target-architecture.md) (Phase 1) specified `satsa.*` as a bounded context beside `qsmlops.*`, reusing its foundation layer without repurposing its MLOps domain logic. Phase 2 acts on that decision concretely: a new top-level `satsa/` package (added to `pyproject.toml`'s `[tool.setuptools.packages.find]` include list, alongside the existing `qsmlops*`), with its own error hierarchy (`satsa/errors.py`, deliberately not inheriting from `qsmlops.core.errors.QSMLOPSError` — Part L: "keep domain-specific semantics separate"). `satsa` does reuse `qsmlops.core.logging`/`qsmlops.core.errors` conventions where it makes sense (structured logging, error-code pattern) without importing MLOps-specific modules.

## The fifteen concepts Part H named, and what exists for each

| Concept | Module | What's implemented | What's deliberately not |
|---|---|---|---|
| CSE | `satsa.domain.entities.Entity` | Fields, `validate()`, `to_dict()`/`from_dict()` | No cohort-matching logic (that's analytics) |
| Assessment | `satsa.domain.entities.Assessment` | Half-open period `[start, end)`, status enum, `supersedes_id`, `.contains(timestamp)` | No submission-cutoff enforcement (ingestion-phase) |
| Submission | `satsa.domain.entities.Submission` | Declared period/counts/digests, signature-status enum | No reconciliation against actually-parsed files (ingestion-phase) |
| Alert | `satsa.domain.workflow.Alert` | `acknowledged_at`/`closed_at` as `Optional[float]` (never a fabricated zero), chronology validation, `time_to_acknowledge`/`time_to_close` properties returning `None` when not applicable | No native-category-to-mapped-category mapping logic (ingestion-phase) |
| Case | `satsa.domain.workflow.Case` | Status/closed_at consistency validation | No investigation-quality scoring (analytics-phase) |
| Investigation | `satsa.domain.workflow.InvestigationStep` | Sequence/action-type validation | No text-similarity/meaningfulness scoring (analytics-phase, SIH-EG-01/SIH-EG-04) |
| Escalation | `satsa.domain.workflow.Escalation` | Requires an alert or case reference | No escalation-SLA/policy evaluation (analytics-phase, SIH-EG-03) |
| Disposition | `satsa.domain.workflow.Disposition` | Requires an alert or case reference | No benign/duplicate/suppressed classification logic |
| Asset | `satsa.domain.entities.Asset` | Fields, validation | No control-coverage expectation graph (analytics-phase, SIH-NS-*) |
| Evidence (source record) | `satsa.domain.evidence.SourceRecord` | Digest-based pointer to immutable original bytes | No object store wiring (this points *at* the pattern `qsmlops.artifacts.store.ArtifactStore` already implements — reuse is a later-phase integration, not duplicated here) |
| Observation | `satsa.domain.evidence.Observation` | Run/worker/scope envelope | Not persisted (see below) |
| Finding | `satsa.domain.evidence.Finding` | Five-state enum (`signal`/`no_signal`/`insufficient_data`/`not_applicable`/`error`), a **validation rule enforcing SIH-EX-02** ("a score without explanation is insufficient") — a `signal`-state finding is invalid unless it carries both `evidence_refs` and a `ConfidenceVector`, tested directly | No actual detector produces one yet |
| SupervisoryDecision | `satsa.domain.evidence.ReviewDecision` | Action enum (`confirm`/`dismiss`/`escalate`/`request_review`/`annotate`), `previous_revision_id` for append-only correction chains | No API/persistence wiring (Part D's identity auth foundation exists; this record is not yet connected to it) |
| ProvenanceRecord | `satsa.domain.evidence.ProvenanceRecord` | Same subject/predicate/object shape as the qsmlops `provenance_edges` table (Part E), for SAT-SA's own object types | Not persisted — this is intentionally the same modeling decision Part E made for the qsmlops side, restated for consistency, not duplicated effort |
| AnalysisRun | `satsa.domain.runs.AnalysisRun` | Status enum with **terminal-state validation** (`completed`/`failed`/`partial`/`cancelled` require `finished_at`; `failed` additionally requires a non-empty `error`) | No scheduler/executor beyond the orchestration skeleton (Part K, separate doc) |

## Why validation lives on each record, not in a central validator

Each dataclass owns a `validate() -> list[str]` method (never raises — a caller decides whether to reject, log, or queue for operator review) rather than a single external "validate any record" dispatcher. This mirrors the pattern already established by `qsmlops.security.identity.models.Identity`/`qsmlops.agents.base.Finding` (Part E2's explicit instruction: reuse the existing convention, don't invent a parallel one), and keeps each record's rules next to the fields they constrain — e.g. `Alert`'s chronology check (`acknowledged_at >= created_at >= None-safe`) is unreadable if separated from the dataclass it validates.

## Concrete validation rules enforced today (not placeholders)

Tested in `tests/test_phase2_satsa_domain.py` (23 tests): `Alert.acknowledged_at is None` is distinct from zero duration (data-architecture.md's explicit missing-data semantic); `Assessment` periods must run forward and are half-open; `Case.closed_at` requires `status == "closed"`; `Escalation`/`Disposition` must reference at least one of alert/case; `Finding` in `signal` state must cite evidence and carry a confidence vector, while `no_signal`/`insufficient_data` states are not held to that bar (an abstaining detector is not a broken one); `ConfidenceVector.overall` is the minimum of its components, not an average (a high-impact signal is only as trustworthy as its weakest supporting leg); `AnalysisRun` terminal states require `finished_at`, and `failed` additionally requires a non-empty `error`.

## What Part H explicitly did not ask for, and this phase did not build

Ingestion parsing (CSV/JSONL adapters, quality gates, the five-step transaction [data-architecture.md](../phase1/data-architecture.md) specifies), persistence (no new database tables for these records — a deliberate parallel to Part E's own scoping decision), any detector reading these records, and any API/UI surface. All are explicitly later-phase work per the master brief's Rule 3.
