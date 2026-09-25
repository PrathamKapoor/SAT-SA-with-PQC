# SAT-SA web UI: backend API contract

The web UI reads everything through one interface, `SatsaDataSource`
(`src/lib/api/source.ts`). It has two adapters:

| `SATSA_DATA_SOURCE` | Adapter | Data |
|---|---|---|
| `fixture` (default) | `src/lib/mocks/fixture-source.ts` | Development fixture generated from a real backend run (`scripts/export-demo-fixture.py`) |
| `api` | `src/lib/api/http.ts` | The SAT-SA backend at `SATSA_API_BASE_URL` |

Every page shows which one is active (top bar: "Development fixture" or
"Live backend"). Nothing mixes the two.

**Status:** the FastAPI app currently serves only `/api/entities` and
`/api/entities/{id}/risk`. Everything below is the contract the backend
needs to implement for `SATSA_DATA_SOURCE=api` to work. All calls are made
server-side by Next.js (no CORS needed); the session credential is sent as
`Authorization: Bearer <credential>`.

Response bodies are the backend's existing `to_dict()` output. Field names
map 1:1 to `src/lib/types/domain.ts` (camelCase there; snake_case is kept
where the backend already serializes snake_case: risk profile, entity
priority, agent spec, supervisor decision, meta-audit, validation). The
fixture exporter shows the exact mapping for each record.

## Session

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/api/v1/session` | `{credential}` | `200 {identity_id, name, role}` · `401` · `429` (rate limited) |
| GET | `/api/v1/session` | | `200 {identity_id, name, role}` · `401` |

These endpoints back the **backend session adapter** (`SATSA_AUTH_ADAPTER=backend`,
the default for production builds). The development adapter used by `npm run dev`
makes no backend call and never forwards its session to the API.

`role` is one of `satsa_viewer | satsa_analyst | satsa_supervisor | satsa_auditor | satsa_admin`
(`qsmlops/security/permissions/model.py`). The UI stores the credential in an
HttpOnly `satsa_session` cookie and never exposes it to browser JavaScript.
Backed by `IdentityService.authenticate` and the existing login rate limiter.

## Reads

| Method | Path | Returns (type) | Backend source |
|---|---|---|---|
| GET | `/api/v1/entities` | `Entity[]` | `satsa_entities` |
| GET | `/api/v1/entities/{id}` | `Entity` · 404 | |
| GET | `/api/v1/entities/{id}/risk` | `EntityRiskProfile` (incl. `correlation_clusters`) · 404 | `compute_entity_risk(...).to_dict()` |
| GET | `/api/v1/assessments?entity_id=` | `Assessment[]` | |
| GET | `/api/v1/submissions?entity_id=` | `Submission[]` (with `ingestReport`) | `satsa_submissions` |
| GET | `/api/v1/runs?entity_id=` | `AnalysisRun[]` (with `summary`, incl. `trust`) | `satsa_runs` |
| GET | `/api/v1/jobs?run_id=` | `WorkerJob[]` | `satsa_jobs` |
| GET | `/api/v1/observations?run_id=` | `Observation[]` | `satsa_observations` |
| GET | `/api/v1/findings?entity_id=&run_id=&state=` | `Finding[]` | findings joined to observations; plus `riskDimension` (`risk._dimension_for`), `severity` and `priorityScore` (`prioritize_findings`), `recommendation` (`recommend`) |
| GET | `/api/v1/findings/{id}` | `Finding` · 404 | same |
| GET | `/api/v1/priorities/entities` | `EntityPriority[]` (ordered) | `prioritize_entities` |
| GET | `/api/v1/risk/weights` | `{dimension: weight}` | `DIMENSION_WEIGHTS` |
| GET | `/api/v1/reviews?finding_id=` | `ReviewDecision[]` | `ReviewService.history` |
| GET | `/api/v1/trust/receipts?subject_id=` | `TrustReceipt[]` (key/signature as byte lengths) | `satsa_trust_receipts` |
| GET | `/api/v1/runs/{id}/verification` | `RunVerification` (+ `verifiedAt`) · 404 | `RunService.verify_run` |
| GET | `/api/v1/runs/{id}/supervisor-decision` | `SupervisorDecision` · 404 | `SupervisorEngine().run(...)` |
| GET | `/api/v1/trust/audit` | `MetaAudit` | `run_meta_audit(...).to_dict()` |
| GET | `/api/v1/source-records?ids=a,b` | `SourceRecord[]` | `satsa_source_records` |
| GET | `/api/v1/security-data?entity_id=` | `SecurityData` | alerts, cases, steps, escalations, dispositions, assets |
| GET | `/api/v1/agents` | `AgentSpec[]` | `satsa.supervisor.list_agents` |
| GET | `/api/v1/validation` | `ValidationReport` · 404 | `run_validation` |

## Writes

| Method | Path | Body | Response | Permission |
|---|---|---|---|---|
| POST | `/api/v1/findings/{id}/reviews` | `{action, reason, finding_content_digest}` | `201 ReviewDecision` · `403` · `409` if the finding's live digest no longer matches | `decision.record` |
| POST | `/api/v1/submissions` | multipart: `entity, sector, environment, periodStart, periodEnd, sourceSystem`, one file part per category (`alerts`, `cases`, ...) | `201 {submission_id, entity_id, assessment_id, ingest_status, counts, snapshot_digest, run_id?}` | `analysis.run` |

`action` is one of the actions `ReviewService` accepts today:
`confirm | dismiss | escalate | request_review | annotate`. The review call
must mirror into the decision ledger (`build_review_decision_ledger`), as
`SatsaService.record_review(trust_key_dir=...)` does.

## Backend gaps the UI already shows

These are visible in the UI as disabled controls or labelled empty states.
Nothing is simulated for them.

1. **Review actions `defer` and `false_positive`**: shown on the review panel,
   disabled. Needs new `REVIEW_ACTIONS` values (or a documented mapping).
   The UI records "Reject" as `dismiss` and "Request evidence" as `request_review`.
2. **Platform audit events**: `GET /api/v1/audit/events` (Audit page).
3. **Identity management**: `GET/POST /api/v1/identities`, credential issue and revoke (Administration page).
4. **Configuration (read only)**: `GET /api/v1/system/config` (Administration page).
5. **Health**: `GET /api/v1/system/doctor`, the `sat-sa doctor` result (System page).
6. **Re-verification on demand**: `POST /api/v1/runs/{id}/verify` (TRUST-SAT page currently shows the last verification).
7. **Drift and trend**: available once an entity has a second assessment period; the UI already says so.

## Switching to the backend

```bash
SATSA_DATA_SOURCE=api SATSA_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Keep the fixture current while the API is built:

```bash
python web/scripts/export-demo-fixture.py   # from the repository root, backend installed
```
