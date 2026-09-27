# Frontend and backend convergence audit

Scope: the Next.js application in `web/` and the SAT-SA API in `satsa/api`.
Audited on branch `phase16/product-convergence` (based on GitHub `main`
`c0c99cc`). Status words follow the claim classes in `docs/CLAIMS.md`:
implemented, tested, CI-tested, locally verified, hosted verified, unverified.

## 1. What exists

| Layer | Implementation | Status |
|---|---|---|
| API | FastAPI app `satsa.api.create_app`, served by `python -m satsa.api.server`. All product routes under `/api/v1`, OpenAPI at `/openapi.json`, contract in `docs/API_CONTRACT.md`. | tested (SQLite and PostgreSQL), CI-tested |
| Authentication | QSMLOps identity credentials; `POST /api/v1/session` issues a persisted, revocable HttpOnly session with a CSRF token; API/CLI callers use `Authorization: Bearer`. | tested |
| Tenancy | Every tenant route requires `X-Organization-ID`; membership and role are checked per request; resources are read through organization-scoped queries. Foreign IDs return 403/404. | tested, including direct cross-tenant access |
| Database | One engine interface (`qsmlops.database.engine.create_engine`) with SQLite and PostgreSQL dialects; the same migrations and services run on both. | tested on both; PostgreSQL CI-tested in the topology job |
| Artifact storage | One `ArtifactStorage` interface with `LocalArtifactStorage` (offline) and `S3ArtifactStorage` (hosted). PostgreSQL holds metadata; object storage holds bytes. | local tested; S3 CI-tested only through SeaweedFS in the topology job |
| Worker | `sat-sa-worker` (`satsa.analysis.execution.worker_main`): PostgreSQL/SQLite queue with leases, heartbeats, generation fencing, retry classification, cooperative cancellation and a review checkpoint. The API never runs analysis in the request. | tested; locally verified as a separate process |
| LangGraph | `execution_mode="graph"` runs the same deterministic workers under a LangGraph state graph with checkpointing and a human-review interrupt; `standard` runs them without the graph. | tested |
| TRUST-SAT | After the supervisor's decision the worker finalizes the run: canonical supervisory digest, ML-DSA-65 receipt, hash-chained ledger entry; `POST /runs/{id}/verify` rebuilds and checks it. | tested, CI-tested |
| Offline product | CLI (`sat-sa`) and the FastAPI/Jinja UI (`satsa/ui`) over a local SQLite file, no network calls in the pipeline. | tested (offline suite) |
| Web UI | Next.js 16 app: public pages plus an authenticated workbench reading through one `SatsaDataSource` interface with two adapters (`fixture`, `api`). | lint/typecheck/build CI-tested |

## 2. The actual gap

The backend is the complete product path. The web workbench is not yet on it.

* `web/src/lib/api/http.ts` (the `api` adapter) calls an earlier proposed
  contract (`web/docs/API_CONTRACT.md`): global, unpaginated arrays in
  camelCase, no `X-Organization-ID`, and about fifteen endpoints that the
  backend does not serve (`/findings`, `/jobs`, `/observations`,
  `/priorities/entities`, `/reviews`, `/trust/receipts`, `/trust/audit`,
  `/source-records`, `/security-data`, `/agents`, `/validation`,
  `/runs/{id}/verification`, `/runs/{id}/supervisor-decision`,
  `/risk/weights`, `/entities/{id}/risk`).
* With `SATSA_DATA_SOURCE=api` the workbench would therefore fail on most
  pages. With the default `SATSA_DATA_SOURCE=fixture` it shows a development
  fixture generated from a real backend run. Every page labels the origin
  ("Development fixture" or "Live backend"), so fixture data is not presented
  as live, but it is not live either.
* Server actions `ingest-actions.ts` and `review-actions.ts` post to routes
  that do not exist (`POST /submissions` as one multipart request,
  `POST /findings/{id}/reviews`).
* Sign-in already matches the backend: `POST /api/v1/session` with a
  credential and `GET /api/v1/session` with the bearer credential.

## 3. Page-by-page mapping

`loadCore` (`web/src/lib/model.ts`) loads entities, findings, review
decisions, runs, assessments, submissions, priorities and per-run
verification for most workbench pages.

| Web data-source method | Backend route (real) | Status |
|---|---|---|
| `listEntities`, `getEntity` | `GET /entities`, `GET /entities/{id}` | available (paged, snake_case) |
| `listAssessments(entityId)` | `GET /assessments?entity_id=` | available |
| `listSubmissions(entityId)` | `GET /submissions?entity_id=` plus `GET /submissions/{id}/versions`, `GET /versions/{id}/validation` | available; ingest report is the validation resource |
| `listRuns(entityId)` | `GET /runs?entity_id=&status=` | available; each run embeds its `steps` |
| `listJobs(runId)` | `GET /runs/{id}/steps` | available under another name |
| `listObservations(runId)` | none | not exposed; findings carry `observation_id` |
| `listFindings(query)` | `GET /runs/{id}/findings`, `GET /findings/{id}` | available per run; no organization-wide finding list |
| `getRiskProfile(entityId)` | `GET /runs/{id}/risk` (entity's latest run from `/priorities`) | available per run |
| `listEntityPriorities` | `GET /priorities` | **added in this phase** |
| `getRiskWeights` | inside every risk profile (`profile.weights`) | available |
| `listReviewDecisions(findingId)` | `GET /runs/{id}/decision` | semantic difference: one decision per run, not per finding |
| `listTrustReceipts(subjectId)` | `GET /runs/{id}/receipt` | available per run |
| `getRunVerification(runId)` | `POST /runs/{id}/verify` | available (verification is an action that rebuilds state) |
| `listSourceRecords(ids)` | `GET /runs/{id}/evidence` plus `GET /versions/{id}/records` | **records route added in this phase** |
| `getSecurityData(entityId)` | `GET /versions/{id}/records?category=` | **added in this phase** (per submission version) |
| `getMetaAudit` | none | offline pipeline feature; not in the hosted API |
| `getValidation` (benchmark validation report) | none | offline/research feature; not in the hosted API |
| `getSupervisorDecision(runId)` | none | offline supervisor-engine output; not in the hosted API |
| `listAgents` | none | static registry; `web/src/lib/domain/agents.ts` duplicates architecture metadata, not analytical output |
| ingest action | `POST /entities`, `/assessments`, `/submissions`, `/submissions/{id}/versions`, `/versions/{id}/artifacts` (one per file), `/versions/{id}/complete`, `/versions/{id}/validate`, `POST /runs` | available as a sequence |
| review action | `POST /runs/{id}/decision` (`confirm`, `dismiss`, `escalate`) | available; per-finding `request_review`/`annotate` are not API actions |
| audit page | `GET /audit/events` | available |
| administration | `GET/POST /members`, `DELETE /members/{id}`, `GET/POST /organizations` | available |

## 4. Static content classification

| Content | Where | Class |
|---|---|---|
| Public landing, methodology and security pages | `web/src/app/(public)` | legitimate product/marketing content; no supervisory data |
| Development fixture | `web/src/lib/mocks/fixture.json`, generated by `web/scripts/export-demo-fixture.py` from a real backend run | development fixture; labelled on every page |
| Documented figures quoted from repository reports | `web/src/content/documented.ts` (with source paths) | legitimate documented content, not live data |
| Agent/worker grouping and layer labels | `web/src/lib/domain/agents.ts` | static architecture description; must stay consistent with `satsa/supervisor/agents.py` |
| Review action labels and lifecycle labels | `web/src/lib/domain/*.ts` | presentation only |
| Risk scoring, findings, recommendations, trust state | none in TypeScript | correct: the frontend does not recompute analytics |

No production-path static data was found: the workbench has no hard-coded
findings or scores outside the generated, labelled fixture.

## 5. Changes made in this phase (backend)

* Render hosting configuration removed; deployment documentation is
  provider-neutral (`docs/deployment.md`).
* `GET /api/v1/priorities`: organization-scoped entity ranking from each
  entity's latest persisted risk profile, using the same priority function
  as the offline ranking (`satsa.analysis.prioritize.entity_priority`).
* `GET /api/v1/versions/{id}/records`: the existing tenant-scoped canonical
  record listing, so cited evidence can be inspected as record content.
* `scripts/deployment_smoke.py` checks both, and was run against a local
  PostgreSQL topology with separate API and worker processes (20/20 checks).

## 6. Remaining work for the frontend owner

Tracked in `docs/FRONTEND_API_HANDOFF.md`. In short: rewrite the `api`
adapter and the two server actions against `docs/API_CONTRACT.md`, add
organization selection, map per-run decisions and records, and hide or
label the offline-only panels (meta-audit, benchmark validation, supervisor
engine, observations) in API mode. No React component or visual change was
made in this phase.

## 7. Not done, and why

* No hosting provider is selected; nothing is hosted.
* The web workbench has not been run against the live API end to end (the
  adapter does not match the contract yet).
* Container execution was not performed locally (Docker is not installed on
  the development machine); the compose topology is CI-tested.
* No per-finding review workflow was added to the API: the backend records
  one supervisory decision per run, which TRUST-SAT binds. Changing that is
  a product decision, not an integration fix.
