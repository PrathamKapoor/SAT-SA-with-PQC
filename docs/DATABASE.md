# SAT-SA database and submission foundation (Phases 1–2)

SAT-SA now has two storage modes behind `qsmlops.database.engine.DatabaseEngine`:

| Mode | Configuration | Intended use |
|---|---|---|
| SQLite | `sqlite:///<path>` | Existing offline CLI, FastAPI/Jinja UI, analytical workers, and TRUST-SAT flows |
| PostgreSQL | `postgresql://...` via `QSMLOPS_DB_URL` or `DatabaseService(url)` | Hosted tenant foundation; API and worker integration remain later phases |

Install PostgreSQL support with `pip install -e '.[postgres]'`. `PostgresDatabaseEngine` uses a bounded psycopg connection pool, thread-local transaction pinning, bound values, and dict rows. The current repository qmark placeholders are converted to psycopg placeholders without changing quoted SQL literals. A connection error fails closed; it never selects SQLite as fallback. Set `SATSA_TEST_POSTGRES_DSN` to an isolated test database URL to run PostgreSQL tests. Tests create and drop their own random schema within that database. The local SQLite tests do not need PostgreSQL.

`MigrationRunner` applies the same ordered versions in both modes. PostgreSQL maps SQLite's `AUTOINCREMENT` to identity columns, `BLOB` to `BYTEA`, and `REAL` to double precision, preserving timestamp and measurement precision. PostgreSQL migrations run in a locked transaction, so a failed migration does not mark a version applied. Version 10 adds the tenant foundation without assigning any preexisting row to an organization.

## Ownership model

`satsa_users` links one existing QSMLOps human `identity` to a hosted user profile. `satsa_memberships` grants one existing `satsa_*` role per user and organization. This reuses the current identity and permission vocabulary. `TenantRepository(engine, organization_id, user_id)` checks active identity, user, organization, membership, and role on **every** operation, then includes organization ownership in the SQL lookup or follows the parent relationship. IDs are opaque but never serve as authorization. A foreign resource ID returns no row or raises `PermissionDeniedError` on mutation.

`satsa_entities`, `satsa_assessments`, `satsa_submissions`, and `satsa_runs` have direct `organization_id` columns. Findings, evidence, reviews, jobs, and trust receipts inherit ownership through their existing run or submission relationship. Submission versions and artifact metadata have direct organization keys and composite foreign keys that reject a child/parent organization mismatch. No file body is placed in PostgreSQL. The stored artifact digest is SHA3-256 of its exact bytes, computed by the Phase 2 upload service and checked again during validation. The older unscoped SAT-SA stores reject PostgreSQL so hosted code cannot silently query a shared population. They remain available on SQLite for the existing offline workflows.

`PeerAccessPolicy.ORGANIZATION_ONLY` is the hosted default. It yields peer IDs only from the same organization. `AUTHORIZED_AGGREGATE` is a reserved policy value that currently fails closed; a later governed aggregate service must enforce consent, cohort thresholds, and raw-record exclusion before it is enabled. The offline peer worker remains unchanged and is not used on hosted PostgreSQL in Phase 1.

## Sessions and provisioning

`TenantAdministration` is an internal provisioning interface, not an exposed API. Its caller must authorize the administrator before creating organizations, linking existing active human identities to users, or assigning memberships. `SessionRepository` stores random-token SHA3-256 digests, user association, creation/expiry/last-activity timestamps, and revocation. Token plaintext is returned once and never stored. This is a persistence primitive; the current offline cookie still carries the existing QSMLOps credential and has **not** silently changed to a hosted session cookie. Hosted login, rotation, CSRF, rate limiting, and audit integration are later security/API work.

## Legacy SQLite data and cutover

Version 10 leaves existing SAT-SA rows with `organization_id=NULL`. They are inaccessible from `TenantRepository`. Migrate the source SQLite schema to version 10 before validation. A migration operator must supply a complete deterministic mapping of every source entity ID to a target organization ID. There is no default organization and no automatic assignment. The read-only `satsa.migration_validation.validate_migration()` checks mapped owners, row IDs and counts per mapped organization, all persisted row values (including canonical digests and relationships), review state, receipt keys/signatures, and optional ledger file integrity/equality. It raises on any discrepancy. The validator is a gate, **not** a data-copy command. The import procedure and live cryptographic verification of the target remain required before any production cutover. Preserve database backups and key/ledger files as one recovery set.

## Phase 2 submission path

The persisted `failed` state identifies storage or integrity failures separately from invalid user data. A validation report records the failure without accepting canonical rows.

Migration 11 adds idempotency keys, creator IDs, artifact category/format/name/uploader, validation reports, version source pointers, and canonical snapshot rows. It preserves all legacy rows and does not alter TRUST-SAT canonicalization. See the Phase 1 section above for legacy data ownership mapping and cutover validation.

`SubmissionService(engine, organization_id, user_id, storage=..., audit=...)` is the tenant-bound domain entry point. Its caller supplies the authenticated user and organization context and the existing `AuditService`. It checks active membership, role, and ownership on every operation. This is a Python service; hosted HTTP routes are a later integration checkpoint. The legacy Jinja `/ingest` route remains the original offline/demo flow and is not this hosted path.

The lifecycle is `created → uploading → uploaded → validating → valid/invalid`. A submission has numbered versions. A correction creates a new version; an uploaded version cannot have its artifact replaced after completion. Validation retry returns the persisted report. Each version accepts at most one artifact per evidence category and requires `alerts`; the other five categories are optional. The six categories are `alerts`, `cases`, `investigation_steps`, `escalations`, `dispositions`, and `assets`. File formats are CSV, JSON array or recognized wrapper, JSONL, and NDJSON. The separate external SQLite table adapter remains part of the legacy offline ingestion surface; a database file is not an accepted uploaded artifact.

Uploads read 64 KiB at a time and enforce a 16 MiB maximum per artifact, a 100,000 row parsing limit, filename and content type checks, and a server-calculated SHA3-256 byte digest. Format parsers stream CSV and JSONL; `ijson` streams JSON arrays. Accepted rows use the existing `normalize_category` mappings and validation. Malformed files or any rejected record make the entire version invalid; the report retains category, locator, and reason. There is no silent partial acceptance into a valid version. On success, `satsa_version_records` stores the canonical record payload and digest, joined to source record, artifact, version, submission, assessment, entity, and organization. It does not insert into old assessment-wide tables, whose native-ID uniqueness would collide across corrected versions. Phase 3 must consume a selected **valid version** snapshot when scheduling hosted analysis.

`LocalArtifactStorage` stores immutable blobs on a local volume for offline mode. `S3ArtifactStorage` uses an S3-compatible bucket/client with conditional object creation; install it with `pip install -e '.[s3]'`. Hosted mode needs PostgreSQL plus a durable object store, with bucket/endpoint/credentials provided by the deployment environment. The local adapter is not suitable for an ephemeral hosted container filesystem. Both adapters use opaque version-scoped keys; database metadata remains the source of ownership. The service does not yet provide a hosted API, resumable multipart uploads, or object garbage collection for an object written just before a database failure.

Create submission, version, and upload calls require caller-supplied idempotency keys; SQL unique indexes enforce uniqueness per tenant/assessment, submission, or version. A retry of the same upload key must have the same category and bytes. Database uniqueness races on matching keys return the persisted ID; a losing upload with conflicting bytes/category is rejected. Artifact byte digests are distinct from TRUST-SAT canonical evidence digests. Audit events use the existing QSMLOps `AuditService` ledger and database mirror. Cross-resource atomicity between the database, object store, and audit ledger is not provided in Phase 2; an outbox/reconciliation and recovery procedure remain deployment work.

## Phase boundary

PostgreSQL holds tenant, submission, and persistent asynchronous execution state. Hosted review APIs, LangGraph, and a complete hosted assessment workflow remain later work. The existing synchronous analysis, review, and TRUST-SAT writer remain SQLite-only; the hosted execution path persists findings/risk with tenant-scoped SQL and does not claim PQC attestation on PostgreSQL.

## Phase 3 analysis execution

Migration 12 adds run request/correlation/progress/retry fields, `satsa_run_context`, the run-level `satsa_execution_jobs` lease queue, and one immutable `satsa_run_risk` result per run. `satsa_jobs` continues to represent one existing analytical worker stage per run; it now carries attempt and retryable fields and is unique by `(run_id, worker_name)`. Stage rows are created as `pending` when the run is queued and updated independently as workers execute.

`AnalysisExecutionService(engine, organization_id, user_id, audit=...)` requires active tenant membership and `analysis.run`. `create_run(valid_version_id, idempotency_key=...)` verifies the version and its parent submission are owned by the active organization and are in `valid` state, then persists the run, its 16 pending deterministic worker stages, and one queue reference in a single transaction. The unique `(organization_id, submission_version_id, idempotency_key)` constraint makes request retries return the original run. Run, finding, evidence, risk, and cancellation reads repeat organization scoping below any HTTP route. Supervisors/admins can request cancellation; a worker stops at the next worker boundary.

`ExecutionQueue` uses PostgreSQL `FOR UPDATE SKIP LOCKED` for atomic competing claims and SQLite `BEGIN IMMEDIATE` for offline mode. Claims carry an expiring lease with owner and generation fencing. The worker heartbeats during long execution; an expired lease can be reclaimed, and a stale owner cannot persist stage output or finalize the run. Claims are capped by `max_attempts`; exhausted leases become a durable failed run. Explicit `RetryableAnalysisError` failures use bounded exponential delay. Unknown detector errors are recorded as failed stages and do not retry automatically. Completed stages are skipped on retry; stable stage, observation, and finding IDs plus a per-stage transaction keep retries from duplicating outputs. No transaction is held while an analytical worker runs.

The separate `sat-sa-worker` process consumes only persisted run IDs; it resolves organization, submission version, entity, and assessment through authoritative database joins and reloads the frozen Phase 2 canonical records. It invokes the existing deterministic `_default_workers` and Orchestrator; no analytical algorithm is replaced. Progress and stage errors are available through the tenant-bound service. Findings retain their source-record IDs and are readable with source/artifact provenance; run risk is the existing `compute_entity_risk` algorithm persisted for that run.

Peer policy is currently fail-closed for hosted runs: only the run's own tenant-owned snapshot is loaded. Cross-organization peer data and raw records are never queried or exposed. The peer benchmark and cross-entity insight workers receive no hosted population aggregate, so they abstain with their existing insufficient-data behavior. `PeerAccessPolicy.ORGANIZATION_ONLY` remains the intended future population boundary; organization-scoped aggregates require a governed, disclosure-limited provider before they are enabled. The SQLite demo path retains its existing shared-population analytics behavior and should not be treated as hosted tenant isolation.

Audit state changes use the existing QSMLOps `AuditService`. When multiple processes use a file-backed evidence ledger, the API and worker must point to the same durable ledger volume; database transactions serialize append operations, but separate per-instance files would create separate chains. The worker never logs artifact contents or credentials. Existing TRUST-SAT and ML-DSA verification remain functional for SQLite runs. PostgreSQL runs do not receive a trust receipt in Phase 3 because `TrustService` still rejects hosted storage; no `verified` claim is made for them. LangGraph is not implemented. S3 live-bucket validation and hosted deployment are not claimed.

Offline execution remains available with SQLite and local artifact storage. Hosted execution requires PostgreSQL and a separately running worker; the worker code supports both database dialects, but a deployed SaaS topology, shared durable audit volume, S3 bucket, and production operations are not verified by the local tests.

## Phase 4 graph state

Migration 13 adds the graph opt-in flag to `satsa_run_context`, tenant-owned
`satsa_run_recommendations`, and one attributable terminal
`satsa_run_review_decisions` row per graph run. LangGraph manages its own
checkpoint tables in PostgreSQL; SQLite offline mode stores checkpoints in
`<database>.langgraph.sqlite`. See [LANGGRAPH_ORCHESTRATION.md](LANGGRAPH_ORCHESTRATION.md)
for the queue, checkpoint, interrupt, review, and trust boundary.

## Phase 5 decision-bound trust

Migration 14 adds `review_required` to the existing run context and enables it
for existing graph runs. It introduces `satsa_trust_finalizations` as execution
metadata pointing to existing `satsa_trust_receipts`, not another receipt or
ledger implementation. Composite foreign keys bind organization, run and the
immutable decision. Unique `(run_id, decision_id, schema_version)` and a partial
unique index on supervisory receipt subjects enforce finalization identity.
Legacy receipt subjects and rows are unchanged; no old receipt is relabeled as
proving a supervisory decision.

States are `prepared → recorded → verified`. Canonical JSON/digest is frozen at
prepare, signing occurs outside the DB transaction, and receipt insertion plus
its finalization link commit together. The existing evidence ledger event and
its DB hash link are recoverable across the file/DB boundary. Live verification
reconstructs the decision, results and input relationships instead of relying
on `state='verified'`. SQLite and PostgreSQL use the same protocol. See
[TRUST_MODEL.md](TRUST_MODEL.md#supervisory-finalization-phase-5).

## Phase 6 API state

Migration 15 adds `auth_key_id` to persistent sessions so revoking/rotating the
backing bearer credential invalidates derived sessions. `satsa_api_rate_limits`
stores hashed fixed-window scopes with a unique window key; the atomic upsert
shares rate counts across API processes. `satsa_api_bootstrap` is a one-time,
row-locked initialization guard; the provisioning command refuses to create a
second first administrator. API product reads use tenant-bound repositories
and explicit response schemas. The frontend does not receive arbitrary database
rows or storage keys.

## Phase 7 production runtime

Migration 16 adds `satsa_artifacts.storage_status` (`uploading`, `stored`,
`failed`) with existing rows marked `stored`. The submission service records
upload intent in PostgreSQL before calling external object storage, verifies
the S3 object metadata/size after PUT, and only exposes stored artifacts to the
completion/validation path. A same-key/same-content retry can recover an
`uploading` or `failed` artifact because its generated object key is
content-addressed; conflicting content remains rejected. A process crash after
object write but before updating metadata leaves a retryable intent. There is
not yet a general orphan-object garbage collector; do not delete unreferenced
objects automatically.

`python -m satsa.api.migrate status|check|upgrade` is the deployment migration
interface. The production API and worker do not migrate at startup: they
validate that the schema is current and fail closed otherwise. `status` reports
applied/pending/unknown versions; `check` returns nonzero for a stale schema;
`upgrade` applies ordered migrations using the PostgreSQL migration lock.
SQLite migrations also apply each migration transactionally. There is no
automatic downgrade path. Version 16's storage status is deliberately
additive, so existing artifact records remain readable after the migration.

The production API/worker share `RuntimeSettings` and the bounded PostgreSQL
pool (`SATSA_DB_POOL_*`, connect/pool timeout and statement timeout settings).
Production requires an explicit PostgreSQL DSN and cannot select SQLite by
fallback. SQLite plus local object files remains the supported offline mode.
Production uses PostgreSQL plus S3-compatible object storage. Large file bytes
remain outside PostgreSQL; the database stores tenant ownership, content
digest, size, content type, key, and lifecycle state.

The S3-compatible runtime settings are `SATSA_S3_ENDPOINT_URL`,
`SATSA_S3_REGION`, `SATSA_S3_BUCKET`, `SATSA_S3_ACCESS_KEY`,
`SATSA_S3_SECRET_KEY`, `SATSA_S3_USE_SSL`, and
`SATSA_S3_ADDRESSING_STYLE`. Key/secret must be configured as a pair or omitted
to use the provider's workload identity. TLS is mandatory in production. The
adapter uses conditional object creation, stores the server-computed SHA3-256
as object metadata, and checks `HEAD` metadata/length after upload. Bucket
privacy, encryption, replication, and retention policy are provider/operator
controls and must be independently configured.

Phase 7's production Compose stack is documented in [deployment.md](deployment.md).
It is production-like locally, not itself high availability. PostgreSQL remains
authoritative for metadata and results; object storage holds uploaded bytes;
the append-only trust/audit ledger and ML-DSA signing key are separate durable
inputs to TRUST-SAT verification. Database, artifacts, ledger, and key backups
must be coordinated. See [SECURITY.md](SECURITY.md) for the limits of this
recovery set and trust proof.
