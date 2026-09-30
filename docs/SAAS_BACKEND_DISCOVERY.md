# SAT-SA SaaS backend: Phase 0 discovery and migration design

Date: 2026-09-25. Scope: backend, data, security, orchestration, trust, and deployment. This document describes the checked-out `release-fresh` code and the separately inspected public QSMLOps repository and deployed SAT-SA site. It is a design baseline, not a claim that the SaaS capabilities below already exist.

**Historical document.** Its references to Render and `render.yaml` describe
the prototype hosting at the time; Render is no longer used and the hosted
deployment is AWS (`deploy/aws/README.md`).

**Phase 1 update:** The database and tenant foundation described in [DATABASE.md](DATABASE.md) has been implemented after this discovery snapshot. PostgreSQL migration and tenant/session tests now exist. The hosted API, ingestion lifecycle, queue, LangGraph, and MLOps work remain later phases.

## 1. Current state and repository safety

At inspection, `release-fresh` contained local web commits ahead of `newrepo/main`. The working tree contained user work in `handoff.md` and untracked UI server logs; earlier in the inspection it also contained staged and unstaged `web/` changes that another workstream subsequently committed as `de63f8e`. None of that work was discarded or incorporated here. Git identity resolved to `PrathamKapoor <prathamkapoor027@gmail.com>`.

The Python package is named `qsmlops` and packages both `qsmlops/` and `satsa/` (`pyproject.toml`). The actual backend is a synchronous FastAPI/Jinja application (`satsa/ui/__init__.py`) and CLI (`satsa/cli.py`) over `SatsaService` (`satsa/service.py`). `scripts/serve_ui.py` creates a SQLite engine, runs the shared migrations, optionally loads demo data, and starts Uvicorn. The current root `Dockerfile` packages that single process with SQLite and filesystem keys. `render.yaml` still describes a separate Next.js deployment from `feat/sat-sa-site`; the live Render URL served a Next.js landing page and workbench, while `/workbench/system` returned 404 when checked. The newer local `web/` work is not proof that the live deployment contains those routes.

Selected fresh-database, authentication/RBAC, and trust-tamper test files passed in the local Python 3.13 virtual environment during discovery. This is a targeted baseline, not a full-suite or deployment gate.

## 2. Existing data and processing model

`qsmlops/database/engine.py` defines a small `DatabaseEngine` interface, but its only implementation and URL parser are SQLite. `qsmlops/database/migrations.py` holds one version history for platform and SAT-SA tables. The significant SAT-SA relationships are:

```text
satsa_entities
  -> satsa_assessments -> satsa_submissions -> satsa_source_records
                      -> satsa_alerts / cases / investigation_steps /
                         escalations / dispositions / assets
  -> satsa_runs -> satsa_observations -> satsa_findings
                -> satsa_jobs
satsa_findings -> satsa_review_decisions
satsa_runs/findings -> satsa_trust_receipts
```

The platform tables include `identities`, `identity_credentials`, `audit_events`, datasets, dataset versions, experiments, training runs, model lineage, deployments, observations, findings, supervisor decisions, and provenance edges. The model registry also maintains its own SQLite tables. SAT-SA IDs are stable opaque UUID4-based strings (`satsa/domain/base.py`). Several child tables have only an indirect ownership path through a run, assessment, or submission. There is no organization or membership key in the schema. `Entity.access_scope` is a string field, not tenant enforcement. `SatsaService.register_entity()` de-duplicates by display name across the whole database, which is incompatible with separate organizations using the same name.

`satsa/ingest/readers.py`, `normalize.py`, `db_adapter.py`, and `service.py` parse CSV, JSON, JSONL, and source SQLite; normalize six evidence categories; link native IDs; reject malformed rows; hash source records; and persist an ingestion report. Identical file digests for the same assessment are rejected. The file reader loads whole files into memory (`read_file_bytes`), and the browser upload route calls `await upload.read()` then writes complete files to a temporary directory. There is no durable upload object, artifact storage contract, explicit version lifecycle, or bounded streaming path.

`SatsaService.run_analysis()` calls `RunService.run()` synchronously. `Orchestrator.run()` loops through sorted workers in process, isolates individual worker exceptions, and returns `Job` objects. The run, jobs, observations, and findings are written in one SQLite transaction. Statuses (`completed`, `partial`, `failed`) and per-worker errors exist, but persisted jobs are retrospective records, not a queue or resumable worker execution. `model_version=None` is set for the default run. The default detector set is deterministic rules and robust statistics, with peer, drift, coverage, similarity, and completeness workers. `risk.py`, `prioritize.py`, `correlation.py`, and `recommend.py` produce decomposable risk, priority, corroboration, and bounded advice. Peer baselines currently read comparable entities from the shared database without an organization boundary; cross-tenant peer use needs an explicit privacy and policy design before SaaS exposure.

`ReviewService` appends decisions with an authenticated principal ID supplied by the caller and binds each to a finding digest. When the caller passes a trust key directory, the decision also enters an independent hash-chained ledger. `RunService.verify_run()` recomputes live run and finding digests and checks receipts; review binding and decision-ledger consistency are additional checks. Signing after analysis is currently best-effort: failures log a warning while the analysis remains valid. Hosted policy must distinguish an analyzed-but-unattested run from a verified one and must never report success from a stored flag alone.

## 3. Authentication and authorization

SAT-SA reuses `qsmlops.security.identity.IdentityService`, salted high-entropy API-key credentials, identity lifecycle auditing, and role/permission bundles. `satsa/security.py` resolves bearer headers or an HttpOnly cookie, checks permissions, uses a CSRF token for the review and ingest forms, and applies an in-memory login rate limiter. The existing roles include `satsa_viewer`, `satsa_analyst`, `satsa_supervisor`, `satsa_auditor`, and `satsa_admin`.

This is real single-installation authentication, not hosted user/session management. There is no organization membership, resource-scoped authorization, expiring server-side session, shared rate-limit state, password flow, SSO, or account recovery. The credential is a long-lived bearer secret; its SHA3-256 digest is suitable for a random token but is not a password hashing design. Existing cookies are deliberately not marked `Secure` for local HTTP. `satsa/ui/__init__.py` exposes most read pages and both existing JSON endpoints without tenant authorization. All current IDs are globally addressable within the installation. This is the principal SaaS security gap.

## 4. Existing API and frontend boundary

The Python app has HTML routes for entities, findings, queue, evidence, trust, reports, ingest, review, and other pages. Its JSON surface is only `GET /api/entities` and `GET /api/entities/{entity_id}/risk`. The newer Next.js `web/` tree has a typed `SatsaDataSource` and an HTTP adapter (`web/src/lib/api/http.ts`) whose `/api/v1/*` routes are prospective. `SATSA_DATA_SOURCE=fixture` is the default; fixture and live modes are explicitly labeled. `web/docs/API_CONTRACT.md` is the frontend workstream's current proposed contract, including session, entities, assessments, submissions, runs, jobs, observations, findings, risk, review, trust, agents, and validation. It must be reconciled with the backend and extended for organization/tenant ownership before implementation. Do not silently change that document or frontend types.

## 5. Reusable QSMLOps infrastructure

The separately inspected `Quantum-Secure-MLOps` repository at `5995f0d` contains the platform identity and permission model, audit service, crypto providers and agility, evidence ledger, artifact store, dataset/experiment/training tables, model registry, model passport, training adapters, deployment lifecycle, monitoring/drift, supervisor, and a learning store. SAT-SA already vendors an extended `qsmlops/` copy in its package and consumes the identity, SQLite migrations, hashing, signing, ledger, and logging components. The SAT-SA default analysis does not currently execute a QSMLOps model lifecycle or register a SAT-SA model. `qsmlops/supervisor/learning.py` tracks MLOps outcomes/false positives; it is not proof of SAT-SA RLHF.

Use the vendored interfaces for the first SaaS slices. Before extracting an external package dependency, compare versions, SAT-SA additions, migration ownership, and compatibility under tests. Do not instantiate a second registry, signer, audit ledger, or identity system merely because a hosted deployment is being added.

## 6. Gaps and target architecture

| Concern | Today | Target and migration rule |
|---|---|---|
| Tenancy | Global entities, identities, rows and queries | Explicit organization membership, scoped resource lookup, audited cross-organization access denial; default no cross-tenant analytics |
| Database | One SQLite connection and SQLite-specific DDL/SQL | PostgreSQL for hosted use; SQLite retained for offline mode; dialect-specific tested migration path |
| Submission | One synchronous directory/file ingestion call | Durable submission/version/upload/validation state, bounded artifact storage, resumable failures |
| Analysis | In-process blocking workers; jobs saved after execution | API-created run, leased background worker, progress/attempt history, idempotent retry |
| Graph | No LangGraph dependency or checkpoints | Graph around existing workers, persistent checkpoints, explicit review interrupt/resume |
| Review | Real append-only decisions, no tenant boundary | Authenticated, tenant-scoped reviewer action; revision and digest preconditions |
| Trust | Real digest/signature verification; optional attestation | Durable key custody, explicit attestation states, live re-verification and chain status |
| MLOps | QSMLOps facilities present; SAT-SA run has no model version | One justified model use case with real dataset/version/passport/approval/inference/monitoring lineage |
| API | Mostly HTML and two unscoped JSON reads | Versioned typed JSON with tenant authorization, pagination, stable errors and OpenAPI |
| Deployment | Single-process SQLite image; Render serves separate Next.js branch | Separate API and worker containers, PostgreSQL, artifact storage and key/ledger durability, health checks |

## 7. Exact PostgreSQL and tenant migration sequence

1. Freeze the SQLite schema and golden outputs with migration, ingestion, run, review, and trust parity tests. Inventory raw SQL in `satsa/store/repositories.py`, `satsa/analysis/repository.py`, `qsmlops/database/repositories.py`, and related services. SQLite `?` parameters, `AUTOINCREMENT`, `BLOB`, and PRAGMAs require deliberate dialect handling; do not run the SQLite migration strings against PostgreSQL.
2. Add a PostgreSQL `DatabaseEngine` with pooled connections and explicit transactions. Keep the existing SQLite engine for offline use. Introduce PostgreSQL migrations with schema parity and indexes, preserving opaque IDs, UTC timestamps, canonical JSON/digest semantics, and append-only review/trust records. Use a migration tool such as Alembic for the PostgreSQL history, while retaining the SQLite history until parity is proven.
3. Add `organizations` and `organization_members` with a membership role; attach `organization_id` first to entities, assessments, submissions, runs, findings/reviews and artifact metadata, then propagate/enforce it along all child paths. Preserve original IDs and digests. Backfill only from an explicit operator-approved owner map; do not guess ownership from display names. If ownership cannot be established, quarantine those records from hosted exposure.
4. Make repository methods accept a verified organization scope and query with it. Join through the parent where a child lacks a direct key, then add direct keys/indexes where the high-volume path warrants them. Deny ID lookups outside the caller's organization in the service/API layer and test every resource family. PostgreSQL row-level security can be a second control after application scoping works; it is not a substitute for application checks.
5. Compare record counts, representative canonical digests, source-to-finding links, reviews, trust receipts, and ledger verification between SQLite export and PostgreSQL import. Cut hosted traffic only after parity and rollback tests. Do not mix two writable databases during cutover.

Default peer analysis must use only authorized organization data. A future cross-CSE benchmark requires a separate, approved aggregate-only cohort service with minimum cohort size and disclosure controls; raw peer evidence must not become visible to another organization.

## 8. Exact submission and storage plan

Retain the existing readers and normalizers. Add a thin submission application service around them: create assessment/submission, register a version and expected category manifest, stream each upload with byte and content-type limits to a staged object, hash while streaming, validate category/schema/row semantics, then commit immutable artifact metadata and provenance. Use an artifact interface with local filesystem implementation for offline mode and S3-compatible implementation for hosted mode; PostgreSQL stores metadata and digests, not large file bodies. Add deterministic duplicate/idempotency behavior per organization, assessment, category, and client key. A failed validation keeps a queryable report and does not create canonical records. Processing transitions are server-controlled and audited. Existing `submit_files()` becomes the trusted normalizer invoked after the staged artifact set passes validation; do not reimplement six record mappings.

Initial lifecycle: `created -> uploading -> uploaded -> validating -> validated -> processing -> analyzed -> ready_for_review -> under_review -> decided`, plus `validation_failed`, `processing_failed`, and `cancelled` where justified. `verified` is an independent trust state, not an automatic submission state: verification can fail after a decision, and a completed analysis may have missing attestation. Every transition records actor, timestamp, prior state, result, and request/run correlation.

## 9. Exact asynchronous run and LangGraph plan

Start with a PostgreSQL-backed work queue, because PostgreSQL is already required and analysis is periodic. API transaction creates `analysis_run` plus an outbox/queue row and returns `202` with a stable run ID. Workers lease rows using `FOR UPDATE SKIP LOCKED`, heartbeat, bounded attempts, exponential backoff, and dead-letter/failure state. Worker concurrency is capped; duplicate requests use an idempotency key and snapshot/config digest. Keep the existing analytical `Job` and `AnalyticalWorker` contract; publish stage/worker transitions as committed run events. A process crash leaves a lease that another worker can reclaim. Distinguish retryable infrastructure errors from deterministic validation/worker failures.

Once the queue and run history work, compile a LangGraph `StateGraph` whose state carries organization, submission/version, snapshot digest, run ID, config version, completed stage references, errors, and human-review pointer. Nodes call the existing validation, `RunService` worker dispatch (refactored into idempotent stage boundaries), correlation/risk/prioritization, evidence assembly, recommendation, and trust services. Use a PostgreSQL checkpointer with one graph thread per analysis run; expose checkpoint and stage history through the run API. A review node uses a real interrupt and resumes only after an authenticated supervisor's persisted decision. An interrupt is a wait state, not an automatic acceptance. Replayed nodes must check persisted stage keys before any side effect, especially signatures, review rows, and ledger appends. The graph orchestrates domain code; it does not replace workers with LLM calls. LangGraph's maintained PostgreSQL checkpointer documents durable persistence and first-use setup; version and serializer policy must be pinned and tested before deployment.

## 10. MLOps and human feedback plan

Keep deterministic detectors and robust statistics. First establish a labeled, consented SAT-SA dataset and a measurable candidate use case, likely case similarity or anomaly ranking. Compare it against the current deterministic baseline on held-out data. Only if it improves an agreed metric should the model enter the QSMLOps dataset/version, training/evaluation, passport, registry, human approval, deployment, inference, drift, and rollback path. Store model/version and feature-schema references on each affected analysis run and finding. If no candidate meets the gate, do not deploy a model or claim SAT-SA ML performance.

Record supervisor decisions as feedback events linked to finding, evidence snapshot, reviewer, reason, and time. Evaluate those labels offline for calibration and model/rule proposals; require separate review and approval before policy deployment. This is a human-feedback loop, not reinforcement learning or RLHF. The SIH slide's claims of continuous telemetry, parallel agent checks, SHA-256 hash chains, tamper-proofness, and RLHF do not match the present periodic, sequential, SHA3-256, tamper-detecting code and must be corrected unless separately substantiated.

## 11. Security and API contract plan

Keep `IdentityService` as the identity record and capability checker; add persistent organization membership and a hosted session/credential layer around it. Define analyst, supervisor, and admin permissions in the existing permission vocabulary. If human passwords are introduced, use a password-specific KDF; do not use the current random-token SHA3 hash for passwords. Sessions need expiry, revocation, secure cookies, rotation and CSRF protections. Rate limits must be shared across processes. Every read and write route checks `principal -> membership -> role -> resource organization -> operation`; no frontend filter or opaque ID is an authorization boundary. Add IDOR tests for submissions, findings, evidence, reviews, runs, reports, trust records, model artifacts, and direct manipulated IDs. Keep sensitive app pages/API authenticated and `noindex`; public pages remain separately accessible.

Reconcile `web/docs/API_CONTRACT.md` with backend-owned `docs/API_CONTRACT.md` before adding routes. Define `/api/v1` explicit Pydantic request/response schemas, list pagination/filter/sort, stable timestamp format and opaque IDs, validation-error envelope, correlation ID, idempotency-key behavior, auth/session contract, and OpenAPI examples. Preserve the frontend's typed `SatsaDataSource` names or make a versioned, documented mapping. Implement read endpoints in a coherent first slice, then submission/run/review/trust mutations. Never serialize `SELECT *` rows directly, particularly credential, source-record, and trust-key material. Define upload and event-stream contracts explicitly if used.

## 12. Deployment and operations plan

Portable hosted topology: reverse proxy/TLS -> Next.js public and secure app -> FastAPI API -> PostgreSQL; a separately scaled worker reads the PostgreSQL queue and executes SAT-SA/QSMLOps/LangGraph; artifact store and durable key/ledger storage sit beside them. Local Docker Compose uses PostgreSQL, API, worker, web, and local artifact volume; an offline profile can retain SQLite and local artifact/key storage. Render is one deployment target, not an assumption in domain code. The existing root Dockerfile and `render.yaml` are not this topology. Configure secret injection, key backup/rotation, database backup/restore, ledger durability, readiness checks for DB/queue/worker, and a migration job. Log request, organization, submission, run, graph stage, worker, retry, and result IDs without raw evidence or secrets. Add dependency/SAST/container checks after measuring current CI coverage.

## 13. Ordered independently testable implementation phases

1. **Foundation:** PostgreSQL parity, organization/membership schema, tenant-scoped repository and identity context, local SQLite compatibility. Gate: migration parity and cross-tenant IDOR tests.
2. **Submission:** versioned artifact storage, bounded upload, validation, normalization, state and audit. Gate: real file -> canonical records with duplicate/failure tests.
3. **Async analysis:** queue, leased worker, persistent progress and retry. Gate: API returns 202, worker completes, crash/retry remains idempotent.
4. **LangGraph:** durable graph/checkpoints and review interrupt/resume around existing services. Gate: restart during a run and resume at the correct stage with no duplicate side effects.
5. **API and supervisory workflow:** typed reads, evidence, risk, recommendations, tenant-scoped review and decision, frontend contract. Gate: authenticated end-to-end assessment.
6. **Trust and security:** live verification API, key/ledger durability, session hardening, audit, rate limits, IDOR matrix. Gate: tamper and cross-tenant attacks fail.
7. **MLOps where justified:** labeled evaluation, QSMLOps model lifecycle and approval. Gate: measured gain and traceable inference; otherwise no model deployment.
8. **Deployment:** API/worker/web/PostgreSQL/artifact topology and backup/restore. Gate: fresh container deployment passes the real end-to-end flow.

These are separate implementation plans and review gates, not a single change set. The order deliberately puts tenant scoping before broad API exposure. The full product gate is an authenticated CSE submission through validation, queued analysis, evidence/risk/recommendation, a real supervisor decision, live trust verification, and audit history.

## 14. Expected backend files and explicit exclusions

Likely modifications: `qsmlops/database/engine.py`, `qsmlops/database/migrations.py` or a new PostgreSQL migration package, `qsmlops/security/identity/`, `qsmlops/security/permissions/model.py`, `satsa/security.py`, `satsa/store/repositories.py`, `satsa/ingest/`, `satsa/analysis/run.py`, `satsa/analysis/review.py`, `satsa/analysis/trust.py`, `satsa/service.py`, and a versioned `satsa/api/` package; new focused storage, queue, graph, configuration, and test modules; `pyproject.toml`, container/Compose and CI configuration, and backend contract/deployment/security docs. Exact files are locked by each smaller implementation plan before editing.

Do not modify `web/src/` components, routing, styling, frontend state, or frontend tests; do not overwrite the existing `web/docs/API_CONTRACT.md` proposal or unrelated `handoff.md` and UI server logs. Do not remove the local FastAPI demo UI, SQLite support, workers, QSMLOps trust/identity infrastructure, PQC, or existing tests during the migration.

## 15. Principal migration risks and release gates

The highest risks are tenant leakage through indirect child IDs and peer aggregates; divergence of digest/signature semantics during database migration; file-ledger consistency across transaction failures; replay of side-effecting graph nodes; credential/session exposure; long-running analysis overwhelming the API or database; loss of offline operation; and silent UI fixture use being mistaken for live backend data. Gate each phase with focused tests, then broader backend tests, and preserve a rollback path. Do not describe Render's current Next.js presentation service as a deployed backend SaaS.

## Sources inspected

- Local `satsa/`, `qsmlops/`, `docs/`, `tests/`, `scripts/`, `Dockerfile`, `render.yaml`, `.github/workflows/ci.yml`, and `web/` contract/adapter.
- Public SAT-SA repository: `https://github.com/PrathamKapoor/SAT-SA-with-PQC`.
- Public QSMLOps repository: `https://github.com/PrathamKapoor/Quantum-Secure-MLOps` (inspected at `5995f0d`).
- Deployed prototype: `https://sat-sa-with-pqc-81gi.onrender.com/` (landing and workbench served; the checked system route did not).
- `C:/Users/LENOVO/Downloads/SIH-26(trial).pptx.pdf` (six slides).
- LangGraph's maintained PostgreSQL checkpointer and persistence documentation, consulted for the proposed orchestration layer only; LangGraph is absent from the current SAT-SA dependencies.
