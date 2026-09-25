# Persistent Asynchronous Analysis Execution Implementation Plan

> **For agentic workers:** Execute this plan task-by-task in this session. Each task ends with a focused verification before continuing.

**Goal:** Add durable, tenant-scoped asynchronous analysis runs for validated submission versions, reusing SAT-SA's current deterministic workers and result semantics.

**Architecture:** Keep the existing synchronous SQLite `RunService` path intact. Add an explicit tenant-bound run service and PostgreSQL-backed execution queue. The worker resolves its run, organization, assessment, entity, and validated version from persisted joins; it loads that immutable version snapshot, calls the existing `Orchestrator` and analytical workers, and commits each worker's step/results atomically so a recovered run can skip completed steps. PostgreSQL claims use row locking and leases; SQLite uses a serialized transaction for local/offline execution.

**Tech Stack:** Python, existing `DatabaseEngine`, PostgreSQL/psycopg, SQLite, pytest, current `Orchestrator`, current `CanonicalDataset` and workers.

**Spec:** Phase 3 in the user request; supporting existing-run contract: `docs/phase4/analysis-run.md`.

## Global Constraints

- Git author and committer: `PrathamKapoor <prathamkapoor027@gmail.com>`.
- Do not modify frontend files or frontend API contracts.
- Do not add LangGraph, LLM workers, Redis, or new analytics implementations.
- Preserve existing SQLite synchronous workflows, analytical semantics, and TRUST-SAT verification.
- All hosted run/result operations require organization and user or system-worker context and include tenant ownership in repository queries.
- Never hold a database transaction across analytical execution.
- Cross-organization peer access is denied; hosted comparisons use same-organization data only, and abstain when a safe comparable population is unavailable.

---

### Task 1: Execution schema and state contracts

**Files:**
- Modify: `qsmlops/database/migrations.py`
- Modify: `satsa/domain/runs.py`
- Test: `tests/test_phase3_execution_schema.py`

Add a new deterministic migration after version 11. Extend `satsa_runs` with submission-version identity, idempotency key, requester, request time, correlation ID, progress, retry count, and diagnostic fields. Add `satsa_execution_jobs` as the one-run queue with `queued/running/retry_wait/completed/failed/cancel_requested/cancelled`, lease owner/expiry/heartbeat, attempt/max attempts, availability time, and unique run/idempotency constraints. Extend existing `satsa_jobs` as per-worker durable stages with attempts and a unique `(run_id, worker_name)` key. Add indexes for claim order, tenant scope, leases, and status. Preserve migration 7 worker-job records and migration 11 submission records. Add tests that migrate both dialects and verify uniqueness and foreign-key ownership.

### Task 2: Tenant-aware run and queue repository

**Files:**
- Create: `satsa/analysis/execution_repository.py`
- Test: `tests/test_phase3_execution_repository.py`

Implement methods that require organization context: create queued run from a validated version, fetch/list run, fetch steps/findings, request cancellation, claim one available job, heartbeat, complete, retry, fail, and recover expired leases. Claim PostgreSQL jobs with a short transaction using `FOR UPDATE SKIP LOCKED`; claim SQLite jobs in the engine's serialized transaction. A successful claim increments an attempt and fencing generation. Heartbeats and completion require matching job ID, lease owner, and generation. Every query joins `run → submission → version → assessment/entity` and enforces the stored organization ID. Test two workers claiming concurrently, stale lease recovery, stale-owner fencing, retry exhaustion, invalid transitions, and cross-tenant IDs on SQLite and PostgreSQL.

### Task 3: Load an immutable Phase 2 version as the existing analysis dataset

**Files:**
- Modify: `satsa/store/dataset.py`
- Create: `satsa/analysis/tenant_context.py`
- Test: `tests/test_phase3_versioned_dataset.py`

Add a loader that fetches `satsa_version_records` only through `(organization_id, version_id)` and requires a valid report/status. Convert the stored `to_dict()` payloads using existing domain `from_dict` methods, retain `source_record_ref`, build `submitted_categories`, and use the Phase 2 snapshot digest. Resolve assessment bounds and entity identity from the persisted parent records, never caller payload. Add tenant-scoped previous-period lookup. Define `ORGANIZATION_ONLY` peer policy: cross-organization raw or aggregate access is denied; only same-organization peers with a valid version for the same period may contribute to a peer aggregate, and no peer identities or raw rows are returned to a worker. If fewer than the existing worker's minimum peers exist, preserve its honest abstention behavior. Cross-entity insight extras use same-organization run rows only. Test source links, canonical equality with the offline loader for equivalent fixtures, and direct cross-tenant entity/version attempts.

### Task 4: Persist per-worker stages and resumable analysis

**Files:**
- Modify: `satsa/contracts/orchestration.py`
- Modify: `satsa/analysis/run.py`
- Modify: `satsa/analysis/execution_repository.py`
- Test: `tests/test_phase3_analysis_execution.py`

Add an optional completion callback and safe-boundary stop predicate to the existing `Orchestrator`; default behavior remains unchanged for offline callers. The hosted executor registers the existing default worker set, persists pending stage rows at enqueue, marks one stage running, executes outside a transaction, then commits the stage result, observation, findings, and job-result digest in one tenant-scoped transaction. A completed stage is skipped on retry. A failed worker is permanent by default; a typed retryable execution error returns the run to the queue up to its configured maximum. Failure diagnostics are stored internally while user-facing error codes remain bounded. Persist run progress after every stage. Test deterministic output equality against `RunService.run()` on equivalent datasets and simulate interruption before and after stage commit to prove no duplicate findings.

### Task 5: Analysis run service, cooperative cancellation, and worker command

**Files:**
- Create: `satsa/analysis/execution.py`
- Create: `satsa/worker.py`
- Modify: `pyproject.toml`
- Test: `tests/test_phase3_worker_lifecycle.py`

Implement the tenant-authorized request API with `(organization_id, user_id, validated_version_id, idempotency_key)`. Store no tenant/resource IDs in untrusted job payloads; queue rows reference a run and the worker re-resolves all parents. Provide `run_once`, a polling loop, heartbeat maintenance while analysis is running, cancellation checks between actual analytical worker stages, retry/finalization, and safe shutdown. Add `sat-sa-worker` using `QSMLOPS_DB_URL`, migrations, and bounded polling configuration. Keep SQLite available for local worker execution. Test cancellation races, worker interruption, lease expiry, repeated request/cancel, retryable and permanent errors, and worker resolution from database state.

### Task 6: Risk, trust, audit, observability, and backend documentation

**Files:**
- Modify: `satsa/analysis/execution.py`
- Modify: `satsa/analysis/trust.py` only if tenant-aware persistence can be preserved without weakening verification
- Modify: `docs/DATABASE.md`
- Modify: `docs/SATSA_SYSTEM_ARCHITECTURE.md`
- Create or update: backend execution documentation
- Test: `tests/test_phase3_execution_trust.py`

Compute the existing risk profile for the completed run and persist a versioned run-risk snapshot without changing the risk algorithm. Preserve ML-DSA-65 and existing canonical digest semantics; sign only after result finalization and make retries reuse or verify the same receipt rather than append duplicate trust history. If trust signing remains offline-only, leave hosted signing explicitly unavailable and document why; never mark unsigned results verified. Emit lifecycle audit events through the existing audit service with run and correlation IDs but no evidence content. Add structured run/step/worker IDs to logs. Document queue state transitions, leases, retry policy, cancellation safe boundaries, same-organization peer policy, SQLite versus PostgreSQL execution, and the absence of LangGraph or hosted deployment.

### Task 7: Verification and commit

Run focused Phase 3 SQLite and live PostgreSQL integration tests, then the existing backend suite. Run only repository-configured static checks if present. Inspect `git status`, `git diff --check`, staged file list, and both author/committer identity. Stage backend/documentation files explicitly so existing worktree edits in `handoff.md`, `web/`, `docs/superpowers/` and log files are preserved. Commit as `feat(execution): add persistent asynchronous analysis runs` after verification.

## Review Notes

- Existing `satsa.analysis.run.RunService` is a synchronous SQLite-only path; its `RunStore` and related stores explicitly reject PostgreSQL. Do not route hosted runs into those unscoped stores.
- Current `satsa_jobs` are one analytical worker invocation/result, not a run-level leased queue. Keep this distinction explicit; `satsa_execution_jobs` owns run scheduling and leases.
- Current run extras can read all entities and other tenants. Hosted execution must use the scoped context introduced in Task 3; the offline path remains as it is.
- Existing trust attestation is best-effort after analysis and `TrustService` is offline-store-only. Do not claim hosted cryptographic attestation unless the trust persistence path itself is made tenant-safe and verified.
- No task alters the frontend or claims LangGraph, MLOps, or a production deployment.
