# Frontend and backend convergence audit

Scope: the Next.js application in `web/` and the SAT-SA API in `satsa/api`.
Audited on branch `phase16/product-convergence` (based on GitHub `main`
`c0c99cc`). Status words follow the claim classes in `docs/CLAIMS.md`:
implemented, tested, CI-tested, locally verified, hosted verified, unverified.

> **Status (Phase 18): resolved.** The web workbench is now a client of the
> SAT-SA API. Sections 2 to 7 record the Phase 16 audit that led there;
> section 8 records how each gap was closed.

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
* Sign-in calls the right routes (`POST /api/v1/session`, `GET /api/v1/session`)
  but stores the raw credential in the web's cookie and discards the backend
  session that login creates (Phase 17 audit). It works, but the handoff asks
  for the session token instead: a raw credential used for
  `DELETE /api/v1/session` would revoke the credential itself.

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

### Phase 17 (backend contract closure)

* `docs/API_CONTRACT.md` rewritten from the live application (46 routes) and
  kept in step by `tests/test_phase17_api_contract.py` (route index,
  pagination, idempotency, schema fields).
* Frontend-facing behaviour tested on SQLite and PostgreSQL
  (`tests/test_phase17_api_behaviour.py`): multi-entity priorities with
  pagination, record ordering, decisions by organization administrators,
  receipts without private material, the error shape, session logout.
* Real API and worker processes over HTTP are a regression test
  (`tests/test_phase17_http_topology.py`).
* The frozen paper's code facts are pinned to the freeze's code commit, so
  API additions no longer change paper values
  (`evaluation/research/paper.py`, `tests/test_phase17_paper_code_facts.py`).

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

## 8. Phase 18: how the gaps were closed

| Phase 16 gap | Resolution |
|---|---|
| `api` adapter calling about fifteen routes that do not exist | Replaced by `web/src/lib/api/client.ts`, one function per contract route, with wire types in `web/src/lib/api/types.ts`. The fixture adapter, the fixture file and its exporter were removed; there is no mock data path. |
| No `X-Organization-ID` | Organization context (`web/src/lib/api/context.ts`): memberships from `GET /api/v1/organizations`, automatic with one membership, `/organization` otherwise; every tenant call carries the header. |
| camelCase, unpaginated expectations | Pages consume the snake_case wire types; lists page with `{items, limit, offset, has_more}` (`web/src/components/ui/pager.tsx`). |
| Ingest action posting one multipart request to a nonexistent route | `web/src/components/domain/ingest-workflow.tsx` performs the real sequence (entity, assessment, submission, version, one upload per file, complete, validate, run) with idempotency keys reused on retry. |
| Review action posting per-finding reviews | Replaced by the run decision (`POST /runs/{id}/decision`) on the run page; per-finding review actions were removed. |
| Raw credential stored in the web cookie | Sign-in keeps only the backend session token; sign-out revokes that session. |
| Development identities and fixture presented beside live data | Removed. Local development runs the real backend offline on SQLite (`scripts/local_stack.py`, demo via `scripts/seed_demo_via_api.py`). |
| Offline-only panels (meta-audit, benchmark validation, supervisor engine, observations, agent registry) | Benchmarks shows the documented benchmark and states that `sat-sa validate` is offline-only; Agents shows the static registry mapping with live worker status from a run's steps; the other panels were removed from the workbench. |

A backend defect was found by the browser test and fixed: a finding whose
worker produced an integer statistic was digested as `1` but read back from
its REAL column as `1.0`, so finalization of a decided run failed with
"finding digest mismatch" (`satsa/domain/evidence.py`,
`tests/test_phase18_finding_numeric_digest.py`).

Verification: `web/e2e/workbench.spec.ts` drives the whole workflow in a
browser against a real API and worker (6 tests), and CI runs it in the
`web-e2e` job.
