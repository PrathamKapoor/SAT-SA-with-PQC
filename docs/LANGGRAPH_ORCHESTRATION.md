# Phase 4: LangGraph orchestration

Phase 4 adds an opt-in, real LangGraph workflow to Phase 3 analysis runs. A
caller creates it with `AnalysisExecutionService.create_run(valid_version_id,
idempotency_key=..., graph_enabled=True)`. Existing run creation defaults to
the Phase 3 path to preserve existing callers and tests. No frontend API is
added here.

## Execution ownership

The Phase 3 PostgreSQL queue (or SQLite offline queue) remains authoritative
for claiming work. Its worker owns the lease, heartbeat, retries and failure
state. While holding a lease, the worker compiles and invokes a `StateGraph`.
LangGraph does not enqueue another job. The graph's `thread_id` is
`satsa:<run_id>`; callers never receive raw checkpoint access. Its typed state
contains only the run, organization and submission version IDs plus small
stage/review references. Uploaded records, findings, risk and recommendations
remain in SAT-SA's domain tables.

The graph is deliberately linear: `readiness → analysis → recommendations →
human_review → trust_boundary`. Readiness verifies the authoritative leased
context. Analysis calls Phase 3's existing deterministic Orchestrator and
workers. Phase 3's per-worker transactions, stable IDs and completed-stage
skipping still protect restart/retry behavior. Risk remains the existing SAT-SA
calculation. Recommendations use the existing deterministic `recommend()`
function and have unique `(run_id, finding_id)` identities. No LLM provider is
required.

The graph uses LangGraph's actual `interrupt()` at `human_review`. The worker
releases its lease and marks the run `awaiting_review`; the inert queue item is
requeued only after an authenticated tenant supervisor/admin persists a
decision. A new worker reconstructs the graph from its checkpoint and resumes
using `Command(resume=<persisted decision ID>)`. The node checks the decision
against the authoritative tenant-owned table before finalization. A repeated
identical decision returns the same row; a changed decision is rejected.
`AnalysisExecutionService.get_graph_progress(run_id)` first checks tenant
ownership and returns only checkpoint presence, current stage and review
status. It never exposes raw checkpoint values or a checkpoint ID as an
authorization token. A run whose analytical stages all fail becomes failed
without presenting a supervisory review checkpoint.
Terminal run-level actions are `confirm`, `dismiss`, and `escalate` from the
existing review vocabulary. `annotate` and `request_review` are finding-level
review actions and cannot silently become a terminal supervisory decision.

## Checkpoints and recovery

Hosted mode uses `PostgresSaver` in the configured PostgreSQL database. Its
`setup()` creates LangGraph's own checkpoint tables; SAT-SA migration 13 adds
only SAT-SA's run review/recommendation references and an opt-in flag. Offline
mode uses `SqliteSaver` in `<satsa.db>.langgraph.sqlite` beside the SAT-SA
database. Both are durable across worker process restarts. The product-facing
record remains `satsa_runs` and `satsa_jobs`; graph checkpoints are internal
orchestration state.

LangGraph checkpoints after completed nodes. If a worker stops inside the
analysis node before a graph checkpoint, the Phase 3 stage table still prevents
completed analytical workers from rerunning. A transient node exception is
handled by the Phase 3 queue retry policy; graph nodes have no second retry
policy. The recommendation table's uniqueness and the single run review row
protect durable side effects if a node is retried. Lease generation fencing
still prevents a stale worker from persisting output. Cancellation uses Phase
3's `cancel_requested` state and is checked at graph and analytical worker
boundaries. A paused run can also be cancelled; cancellation does not forge a
human decision.

## Review, audit and trust limits

The older `ReviewService` is finding-scoped and SQLite-only. Phase 4 adds a
run-level supervisory decision linked to the first finding when one exists,
and supports a legitimate zero-finding run with a null finding reference.
It records the authenticated user, identity, action, reason, a live canonical
finding digest where applicable, a decision digest, and an audit event. The
table is tenant-scoped and one terminal decision is allowed per run. Finding
review history remains unchanged.

TRUST-SAT finalization occurs only after a persisted human decision. For
SQLite, the existing ML-DSA attestation runs after the final canonical run
digest is written. PostgreSQL's existing TrustService remains SQLite-only;
hosted graph runs receive no fake trust receipt. The current run receipt
canonicalization does **not** cryptographically bind the new run-level review
row; a future trust migration must explicitly bind decision and recommendation
digests without changing existing receipt semantics silently. A shared durable
audit ledger remains required across API and worker processes.

No cross-tenant peer population is introduced. Hosted peer workers still
abstain until a governed organization-scoped aggregate exists. Live S3,
hosted deployment and model lifecycle integration are outside this phase.

## Local verification

Install the controlled dependencies and run the focused integration tests:

```powershell
python -m pip install -e ".[postgres]"
$env:SATSA_TEST_POSTGRES_DSN = "postgresql://postgres@127.0.0.1/postgres"
python -m pytest tests/test_phase4_langgraph.py -q
```

The tests use real SQLite and PostgreSQL checkpoints, an interrupt and a new
worker instance for resume. The PostgreSQL suite requires an accessible local
database and does not claim deployment validation.
