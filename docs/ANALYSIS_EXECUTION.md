# Persistent analysis execution (Phase 3)

SAT-SA now has a durable execution service around the existing deterministic
analysis workers. This is an internal backend service and worker entry point;
Phase 3 does not add or claim frontend-facing analysis HTTP routes.

## Local SQLite mode

SQLite remains suitable for offline work and test runs. Start with an existing
database containing a tenant, an open assessment, and a Phase 2 submission
version whose validation status is `valid`. The run-creation caller must pass
the authenticated user's organization and user IDs and the existing audit
service:

```python
from pathlib import Path

from qsmlops.database.engine import SQLiteDatabaseEngine
from qsmlops.database.migrations import MigrationRunner
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.service import AuditService
from satsa.analysis.execution import AnalysisExecutionService

db = SQLiteDatabaseEngine(Path("satsa.db"))
MigrationRunner(db).migrate()
audit = AuditService(EvidenceLedger(Path("audit/evidence.jsonl")), database=db)
service = AnalysisExecutionService(db, organization_id, user_id, audit=audit)
run = service.create_run(valid_submission_version_id, idempotency_key="period-2026-01")
print(run["run_id"], run["status"])  # queued
```

Run the separate worker in another shell/process against the same database:

```powershell
$env:QSMLOPS_DB_URL = "sqlite:///C:/data/satsa.db"
$env:QSMLOPS_HOME = "C:/data/qsmlops"
sat-sa-worker
```

For source checkouts, install the package and dependencies first:

```powershell
python -m pip install -e ".[postgres]"
```

`AnalysisExecutionService.get_run(run_id)` returns run status, correlation ID,
submission/version IDs, progress, retry count, and each worker stage. The
service's `list_findings`, `get_finding`, `list_evidence`, and `get_risk`
operations apply organization ownership checks themselves. A worker processes
one claimed run at a time and polls the persistent queue with bounded idle
backoff.

## Hosted PostgreSQL mode

Install the PostgreSQL extra and configure the database URL before running the
API host and a separate worker process:

```powershell
python -m pip install -e ".[postgres]"
$env:QSMLOPS_DB_URL = "postgresql://user:password@host:5432/satsa"
$env:QSMLOPS_HOME = "C:/durable/shared/qsmlops"
sat-sa-worker
```

The API-side caller must construct the same tenant-bound service with the
authenticated user and organization and an `AuditService` pointed to the same
durable audit ledger used by workers. Keep credentials in deployment secrets,
not command history or source control. A shared durable audit ledger is
required when API and worker processes append to the same chain. No hosted
deployment, S3 bucket, multi-host ledger volume, or production runbook has been
validated as part of this phase.

## Run and queue semantics

The run lifecycle is `queued → running → completed | partial | failed` with
`cancel_requested → cancelled` at a worker boundary. A run binds to exactly one
validated immutable submission version. Repeating the same idempotency key for
that organization/version returns the same run. A different key requests a
distinct run.

PostgreSQL claim transactions use `FOR UPDATE SKIP LOCKED`; SQLite claims are
serialized with an immediate write transaction. Each claim has an owner,
monotonic lease generation, expiry, heartbeat, and bounded attempt count. A
worker heartbeat continues while a detector is running. Lease generation
fencing prevents an expired worker from committing output after another
worker reclaims its run. Explicitly tagged transient failures retry with
bounded exponential delay; unknown exceptions are retained as failures.
Exhausted crashed-worker leases also become failed runs.

Worker stages are created as `pending` with the run. Each stage's finding,
observation, result, and completed state commit atomically. Stable IDs and
unique `(run_id, worker_name)` stage identity prevent duplicate results when a
run resumes. A cancellation request is checked between workers; an active
detector is allowed to reach that safe boundary.

## Analytics, peers, and trust

The worker rehydrates the version's canonical records and runs the existing
SAT-SA analytical workers and Orchestrator. It does not call the legacy
assessment-wide SQLite loader on PostgreSQL. Hosted peer population data is
not queried: peer benchmarking and cross-entity insights abstain until a
tenant-scoped, disclosure-governed aggregate is implemented. Cross-tenant
aggregate comparison is prohibited in this phase.

The existing risk algorithm is run over the tenant-owned run findings and its
profile is persisted with a digest. Findings retain source-record references;
the tenant-bound evidence method resolves those references to artifact and
canonical-record metadata. SQLite can use the existing TRUST-SAT ML-DSA
attestation/verification flow when `trust_key_dir` is configured. PostgreSQL
trust attestation is intentionally unavailable because the current
`TrustService` is SQLite-only. No hosted run is marked verified. LangGraph is
not part of Phase 3.

## Phase 5 supervised non-graph execution

`create_run(..., review_required=True)` enables the same human review and trust
boundary without LangGraph. Default non-graph requests remain analysis-only for
compatibility: their `completed` status and legacy receipts do not prove a
supervisory outcome. Graph requests imply `review_required=True`.

Supervised execution persists recommendations, pauses at `awaiting_review`,
accepts only the existing authorized supervisor/admin `decide()` operation,
and requeues the existing job. On resume it skips completed analytical stages,
finalizes and verifies TRUST-SAT, then completes the queue item. Failed trust
finalization cannot silently complete the run. Configure `SATSA_TRUST_KEY_DIR`
on workers with a durable secret-backed directory. No frontend API or route
shape is changed. See [TRUST_MODEL.md](TRUST_MODEL.md#supervisory-finalization-phase-5).
