# SAT-SA Phase 1 — Engineering quality plan

SAT-ENG-01 in [requirements traceability](requirements-traceability.md). This plan distinguishes what is already a reusable EXISTING foundation (verified by direct read) from what SAT-SA must build fresh.

## Code quality — existing foundation to reuse as-is

| Capability | Evidence | Reuse decision |
|---|---|---|
| Structured JSON logging | `core/logging.py`: stable field set (`event`, `service`, `actor`, `resource`, `level_name`, `code`), idempotent reconfiguration, JSON-per-line in production / human-readable in development | Reuse directly; SAT-SA modules call `get_logger(__name__)` and log with the same field vocabulary, so a future log aggregator does not need two parsing rules |
| Typed error hierarchy | `core/errors.py`: every error carries a stable machine-readable `code` and HTTP status hint (`ConfigurationError`, `IntegrityError`, `PermissionDeniedError`, `NotFoundError`, ...) | Reuse the base `QSMLOPSError` pattern; add SAT-SA-specific subclasses (e.g. `IngestionValidationError`, `DetectorContractError`) following the same `code`/`status_code` convention rather than inventing a second error taxonomy |
| Permission model | `security/permissions/model.py`: `domain.action` capability vocabulary, named roles, `has_permission`/`require_permission` with fail-closed unknown-permission handling | Currently unused at the API boundary (GAP-07) — wiring it in is INTEGRATE work, not new design; the vocabulary already anticipates least-privilege agent roles (`security_agent`, `redteam_agent`, etc. hold only `AGENT_OBSERVE`/`AGENT_RECOMMEND`, never mutation) which is exactly the constraint [agent architecture](agent-architecture.md) requires for SAT-SA workers |
| Dynamic policy loading | `security/policies/loader.py`: file-watched policy engine that never replaces a known-good configuration with a broken one, records `last_error` for operators | Reuse directly for versioned severity/escalation-SLA/threshold policy documents SAT-SA's detectors need (per [analytics architecture](analytics-architecture.md)'s "policy version" requirement) |
| Audit trail pattern | `security/audit/service.py`: ledger is authoritative, database is a best-effort indexed mirror rebuilt from the ledger when it diverges, every event carries `ledger_entry_hash` for provenance | Reuse the pattern for SAT-SA's review-decision and finding-publication audit trail; do not invent a second audit mechanism |

## Code quality — new work

Modularity and separation of concerns are enforced by the layering in [target-architecture.md](target-architecture.md) (foundation -> domain -> ingestion -> analytics -> risk/review -> API -> UI, each depending only downward). Configuration-driven behavior extends the existing YAML-layering convention (`configs/settings.*.yaml`) rather than adding environment-variable sprawl. Deterministic/reproducible analysis is a hard requirement stated already in [analytics architecture](analytics-architecture.md) (frozen snapshots, saved seeds/digests) — this is a design constraint, not a testing afterthought, because reproducibility is itself part of SIH-EX-03/04 (traceability/auditability).

## Testing

The existing suite (27 `test_*.py` modules, `conftest.py`, 451 passed / 1 portability failure / 17 skipped — [technology-baseline.md](technology-baseline.md)) is a real, executed regression suite for the MLOps product and stays as its own test tree; SAT-SA gets a **separate** test tree (e.g. `tests/satsa/`) rather than mixed in, so the two products can evolve and be graded independently. Planned coverage, mapped to what the brief asks for in Part M:

| Test category | What it must cover | Source of the requirement |
|---|---|---|
| Unit | Each detector's rule/statistic in isolation against fixtures | Per-detector fixture tables already specified in [analytics architecture](analytics-architecture.md) |
| Schema | Ingestion adapter against the canonical model | Acceptance examples already listed in [data architecture](data-architecture.md) (mixed timezones, duplicate native IDs across CSEs, truncated files, etc.) |
| Trust-layer | Tamper/rotation/expiry/revocation/crash scenarios | QT-01..07 test matrix already specified in [quantum-trust-audit.md](quantum-trust-audit.md) |
| Integration | Full ingestion -> analytics -> synthesis -> review pipeline on the demo dataset | [demo-strategy.md](demo-strategy.md) ground-truth manifest doubles as the integration fixture |
| Regression | Legacy MLOps suite stays green; SAT-SA changes to shared foundation code (`crypto/`, `evidence/`, `core/`) must not break it | Both suites run in CI once CI exists (GAP-16 notes CI does not exist today) |
| Edge cases | Malformed input, conflicting duplicate records, missing data, empty ledger, crash-at-each-outbox-boundary | Already enumerated per-area in data-architecture.md and quantum-trust-audit.md; consolidated here as a cross-cutting requirement rather than repeated |

The one known existing defect (`TestDeterminismAndQuiet.test_boundary_still_clean_after_phase10` calling Unix `grep`, unavailable on Windows PATH — confirmed via `Get-Command grep` and source read) is a portability bug in the legacy suite, not a SAT-SA concern, and is noted here only so it is not mistaken for a new regression once SAT-SA's own suite starts running alongside it.

## Observability

Extend the existing structured-logging field vocabulary with assessment/run/worker identifiers (`assessment_id`, `run_id`, `worker`, `detector_version`) so a single log line can be correlated to a specific analytical run without parsing prose — this mirrors the `run manifest` concept already specified in [data architecture](data-architecture.md) and [agent architecture](agent-architecture.md). Processing metrics (duration, resource use per worker) and algorithm/model version are mandatory run-manifest fields, not optional telemetry, because they feed SIH-EX-04 auditability directly: an auditor reconstructing what happened needs to know which code version produced a given finding.

## Security

Input validation at the ingestion boundary is the primary new attack surface (GAP-14): bounded resource parsing, path-traversal and spreadsheet-formula-injection defenses, no pickle deserialization of submitted evidence anywhere (explicit constraint already stated in [data architecture](data-architecture.md), and consistent with the existing audit finding that non-reference serving paths in the legacy product use pickle — SAT-SA must not repeat that pattern for CSE-submitted data). Access control is the wiring of the existing, currently-unused permission model into every mutating API route (GAP-07). Data isolation is entity/assessment-scoped repository arguments, never UI-layer filtering (already a stated principle in [data architecture](data-architecture.md)). Configuration/security separation follows the existing YAML-layering pattern with fail-closed startup validation of crypto policy (QT-07). Cryptographic verification is the hardened trust layer from [quantum-trust-audit.md](quantum-trust-audit.md).

## What this plan deliberately does not add

No new linting/formatting tool choice, no new dependency-management tool, no CI platform selection — these are implementation-phase decisions that depend on operator/NCIIPC tooling constraints this repository gives no evidence about, and specifying them here would be exactly the kind of unverified assumption Rule 1 of the brief prohibits.
