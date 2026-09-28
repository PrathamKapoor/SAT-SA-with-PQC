# SAT-SA backend API contract, version 1

This backend-owned contract is implemented by `satsa.api` and served by
`python -m satsa.api.server` (entry point `sat-sa-api`). The machine-readable
schema is served at `/openapi.json`. The route index in section 4 is checked
against the live application by `tests/test_phase17_api_contract.py`; the two
must not drift. The earlier frontend proposal in `web/docs/API_CONTRACT.md` is
not this contract (section 11).

The live API has **46 routes**. 44 existed at the research freeze's code commit
(`837d1ef`, the figure the paper keeps through its pinned code facts); two were
added in Phase 16: `GET /api/v1/priorities` and
`GET /api/v1/versions/{version_id}/records`.

## 1. Transport, authentication and organization context

**Credentials.** A credential is a QSMLOps identity key `key_id.secret` issued
to a human identity with an active SAT-SA user. Non-human identities and
users without an active record are rejected (`401`).

**Two ways to authenticate a request.**

| Method | How | CSRF |
|---|---|---|
| Bearer | `Authorization: Bearer <token>`, where `<token>` is a session token or a credential | not required |
| Cookie | the `satsa_api_session` cookie set by `POST /api/v1/session` (HttpOnly, `Path=/api/v1`, `Secure` when `SATSA_COOKIE_SECURE` is true, `SameSite` from `SATSA_COOKIE_SAMESITE`, default `lax`) | every non-GET/HEAD/OPTIONS request must send `X-CSRF-Token` equal to the session's `csrf_token` |

A bearer token is resolved first as a session token, then as a credential.

**Sessions.** `POST /api/v1/session {credential}` creates a persisted session
(lifetime `SATSA_SESSION_TTL_SECONDS`, default 28800 s). The session token is
returned only in `Set-Cookie: satsa_api_session=<session token>`; the body is a
`Session` with `csrf_token`. Revoking the credential invalidates its sessions.

**Logout depends on the token type.** `DELETE /api/v1/session` revokes the
*session* when called with a session token or the cookie, but revokes the
*credential itself* when called with a raw credential as bearer. A client that
holds a raw credential must not call it for an ordinary sign-out.

**Browser login origin.** When `POST /api/v1/session` carries an `Origin`
header, it must be listed in `SATSA_ALLOWED_ORIGINS` or equal the API's own
origin; otherwise `403 ORIGIN_DENIED`.

**Organization context.** Every tenant route requires
`X-Organization-ID: <organization id>` (1–128 characters; missing or too long:
`400 ORGANIZATION_REQUIRED`). On every request the server resolves the caller's
active membership in that organization and its role; without one the request
fails with `403`. Resources are read through organization-scoped queries, so a
resource of another organization returns `403` or `404` and never its content.
Organization, role and permissions are never taken from the client beyond this
header.

**Response headers.** Every response carries `X-Request-ID` (a caller-supplied
`X-Request-ID` matching `[A-Za-z0-9_-]{1,64}` is kept; otherwise one is
generated) and `Cache-Control: no-store`.

## 2. Roles and permissions

Membership roles and their permissions (`qsmlops/security/permissions/model.py`):

| Permission | viewer | analyst | supervisor | auditor | admin |
|---|---|---|---|---|---|
| `finding.view`: entities, assessments, submissions, versions, validation, runs, steps, findings, risk, priorities, recommendations, decision | yes | yes | yes | yes | yes |
| `evidence.view`: artifacts, summary, canonical records, evidence, receipt, verification | yes | yes | yes | yes | yes |
| `analysis.run`: create entities, assessments, submissions, versions; upload, complete, validate; start runs | – | yes | yes | – | yes |
| `review.create` plus supervisor/admin role: record the run decision, cancel a run | – | – | yes | – | yes |
| `audit.read`: audit events | – | – | – | yes | yes |
| `identity.read`, `identity.manage`: members | – | – | – | – | yes |

Recording a decision and cancelling a run require **both** `review.create` and
a membership role of `satsa_supervisor` or `satsa_admin`; an organization
administrator may therefore decide. Creating an organization requires the
caller identity's global role to grant `identity.manage` (in practice a
`satsa_admin` identity); the creator becomes that organization's admin.
Callers can never set run states, decision authority or trust status.

## 3. Conventions

* JSON properties are `snake_case`. Identifiers are opaque strings. Times are
  Unix epoch seconds (UTC, float).
* **Collections** return `{"items": [...], "limit": n, "offset": n, "has_more": bool}`.
  Query `limit` 1–200 (default 50) and `offset` 0–1,000,000 (default 0).
  Ordering is stable (`created_at, id` unless stated). Filters are whitelisted
  per route; there is no client-controlled SQL filtering or sorting.
* **Idempotency.** `Idempotency-Key` (1–128 characters) is required on
  `POST /submissions`, `POST /submissions/{id}/versions`,
  `POST /versions/{id}/artifacts` and `POST /runs`. The same key with the same
  content returns the original resource; the same key with different content
  is a conflict; a missing key is `422 VALIDATION_ERROR`.
  `POST /runs/{id}/decision` is idempotent by content: an identical retry
  returns the original decision.
* **Limits.** Request bodies up to `SATSA_MAX_REQUEST_BYTES` (default 17 MiB).
  Per user, route and minute: 300 reads and 30 mutations
  (`SATSA_READ_RATE_LIMIT`, `SATSA_MUTATION_RATE_LIMIT`); login: 5 attempts per
  client address per minute. Windows are stored in the database and shared
  across API instances.

## 4. Route index

The authoritative list, one route per line:

```text
GET    /health/live
GET    /health/ready
POST   /api/v1/session
GET    /api/v1/session
DELETE /api/v1/session
GET    /api/v1/organizations
POST   /api/v1/organizations
GET    /api/v1/members
POST   /api/v1/members
DELETE /api/v1/members/{user_id}
GET    /api/v1/entities
POST   /api/v1/entities
GET    /api/v1/entities/{entity_id}
GET    /api/v1/assessments
POST   /api/v1/assessments
GET    /api/v1/assessments/{assessment_id}
GET    /api/v1/submissions
POST   /api/v1/submissions
GET    /api/v1/submissions/{submission_id}
POST   /api/v1/submissions/{submission_id}/versions
GET    /api/v1/submissions/{submission_id}/versions
GET    /api/v1/versions/{version_id}
POST   /api/v1/versions/{version_id}/artifacts
GET    /api/v1/versions/{version_id}/artifacts
GET    /api/v1/artifacts/{artifact_id}
POST   /api/v1/versions/{version_id}/complete
POST   /api/v1/versions/{version_id}/validate
GET    /api/v1/versions/{version_id}/validation
GET    /api/v1/versions/{version_id}/summary
GET    /api/v1/versions/{version_id}/records
POST   /api/v1/runs
GET    /api/v1/runs
GET    /api/v1/runs/{run_id}
POST   /api/v1/runs/{run_id}/cancel
GET    /api/v1/runs/{run_id}/steps
GET    /api/v1/runs/{run_id}/findings
GET    /api/v1/findings/{finding_id}
GET    /api/v1/runs/{run_id}/evidence
GET    /api/v1/runs/{run_id}/risk
GET    /api/v1/priorities
GET    /api/v1/runs/{run_id}/recommendations
POST   /api/v1/runs/{run_id}/decision
GET    /api/v1/runs/{run_id}/decision
GET    /api/v1/runs/{run_id}/receipt
POST   /api/v1/runs/{run_id}/verify
GET    /api/v1/audit/events
```

## 5. Routes

Auth column: **none** = public; **user** = authenticated caller, no
organization header; **org** = authenticated caller plus `X-Organization-ID`
and an active membership. Permission names refer to section 2. `Page[X]` is the
collection envelope of section 3.

### Health

| Route | Auth | Response | Notes |
|---|---|---|---|
| `GET /health/live` | none | `200 {"status": "alive"}` | process only; no database access |
| `GET /health/ready` | none | `200 {"status": "ready"}` · `503 NOT_READY` | database query, current migration version, trust key configured, artifact storage reachable |

### Session, organizations and members

| Route | Auth | Request | Response | Errors |
|---|---|---|---|---|
| `POST /api/v1/session` | none | `{"credential": str (1–512)}` | `200 Session` + `Set-Cookie` | `401`, `403 ORIGIN_DENIED`, `429` |
| `GET /api/v1/session` | user | – | `200 Session` (`expires_at` and `csrf_token` are null for a credential bearer) | `401` |
| `DELETE /api/v1/session` | user (cookie requires CSRF) | – | `204` (see logout semantics) | `401`, `403` |
| `GET /api/v1/organizations` | user | `limit, offset` | `200 Page[Organization]`: the caller's active memberships with the role in each | `401` |
| `POST /api/v1/organizations` | user, global `identity.manage` | `{"name": str (1–200)}` | `201 Organization` (caller becomes admin) | `403` |
| `GET /api/v1/members` | org, `identity.read` | `limit, offset` | `200 Page[Member]` | `403` |
| `POST /api/v1/members` | org, `identity.manage` | `{"name": str, "email": str, "role": membership role}` | `201 Invitation` (`Member` + `credential`, shown once) | `403`, `409` |
| `DELETE /api/v1/members/{user_id}` | org, `identity.manage` | – | `204` (membership revoked) | `403`, `404` |

### Entities, assessments, submissions and uploads

| Route | Auth | Request | Response |
|---|---|---|---|
| `GET /api/v1/entities` | org, `finding.view` | `limit, offset` | `200 Page[Entity]` |
| `POST /api/v1/entities` | org, `analysis.run` | `{"display_name": str (1–200), "sector"?: str, "environment_class"?: str}` | `201 Entity` |
| `GET /api/v1/entities/{entity_id}` | org, `finding.view` | – | `200 Entity` |
| `GET /api/v1/assessments` | org, `finding.view` | `limit, offset, entity_id?` | `200 Page[Assessment]` |
| `POST /api/v1/assessments` | org, `analysis.run` | `{"entity_id": str, "period_start": float, "period_end": float}` | `201 Assessment` (`status: "open"`) |
| `GET /api/v1/assessments/{assessment_id}` | org, `finding.view` | – | `200 Assessment` |
| `GET /api/v1/submissions` | org, `finding.view` | `limit, offset, entity_id?` | `200 Page[Submission]` |
| `POST /api/v1/submissions` | org, `analysis.run`, `Idempotency-Key` | `{"assessment_id": str}` (assessment must be `open`) | `201 Submission` |
| `GET /api/v1/submissions/{submission_id}` | org, `finding.view` | – | `200 Submission` |
| `POST /api/v1/submissions/{submission_id}/versions` | org, `analysis.run`, `Idempotency-Key` | – | `201 Version` |
| `GET /api/v1/submissions/{submission_id}/versions` | org, `finding.view` | `limit, offset` | `200 Page[Version]` |
| `GET /api/v1/versions/{version_id}` | org, `finding.view` | – | `200 Version` |
| `POST /api/v1/versions/{version_id}/artifacts` | org, `analysis.run`, `Idempotency-Key` | query `category` (required); multipart field `file` | `201 Artifact`; the server determines format, size and SHA3-256 digest |
| `GET /api/v1/versions/{version_id}/artifacts` | org, `evidence.view` | `limit, offset` | `200 Page[Artifact]` (no storage paths) |
| `GET /api/v1/artifacts/{artifact_id}` | org, `evidence.view` | – | `200 Artifact` |
| `POST /api/v1/versions/{version_id}/complete` | org, `analysis.run` | – | `200 Version` (`uploading` → `uploaded`) |
| `POST /api/v1/versions/{version_id}/validate` | org, `analysis.run` | – | `200 Validation` (stored report) |
| `GET /api/v1/versions/{version_id}/validation` | org, `finding.view` | – | `200 Validation` |
| `GET /api/v1/versions/{version_id}/summary` | org, `evidence.view` | – | `200 {"version_id": str, "counts": {category: int}}` |
| `GET /api/v1/versions/{version_id}/records` | org, `evidence.view` | `limit, offset, category?` | `200 Page[CanonicalRecord]`, ordered by `category, record_id` |

Categories: `alerts`, `cases`, `investigation_steps`, `escalations`,
`dispositions`, `assets`. An unknown category is `422`.

### Analysis runs and results

| Route | Auth | Request | Response |
|---|---|---|---|
| `POST /api/v1/runs` | org, `analysis.run`, `Idempotency-Key` | `{"submission_version_id": str, "execution_mode": "graph" \| "standard"}` (default `graph`); the version must be `valid` | `202 Run`; `review_required` is always true for API-created runs |
| `GET /api/v1/runs` | org, `finding.view` | `limit, offset, entity_id?, status?` | `200 Page[Run]` |
| `GET /api/v1/runs/{run_id}` | org, `finding.view` | – | `200 Run` |
| `POST /api/v1/runs/{run_id}/cancel` | org, supervisor or admin | – | `200 Run` (cooperative: `cancel_requested`, then `cancelled`) |
| `GET /api/v1/runs/{run_id}/steps` | org, `finding.view` | `limit, offset` | `200 Page[Step]` |
| `GET /api/v1/runs/{run_id}/findings` | org, `finding.view` | `limit, offset` | `200 Page[Finding]` |
| `GET /api/v1/findings/{finding_id}` | org, `finding.view` | – | `200 Finding` (includes `run_id`) |
| `GET /api/v1/runs/{run_id}/evidence` | org, `evidence.view` | `limit, offset` | `200 Page[Evidence]`: the source records cited by the run's findings |
| `GET /api/v1/runs/{run_id}/risk` | org, `finding.view` | – | `200 Risk` · `404` before risk is persisted |
| `GET /api/v1/priorities` | org, `finding.view` | `limit, offset` | `200 Page[EntityPriority]`, highest priority first |
| `GET /api/v1/runs/{run_id}/recommendations` | org, `finding.view` | `limit, offset` | `200 Page[Recommendation]` |
| `POST /api/v1/runs/{run_id}/decision` | org, supervisor or admin | `{"action": "confirm" \| "dismiss" \| "escalate", "reason": str (≤ 4000)}` | `201 Decision`; an identical retry returns the same decision; a different second decision is `409 DOMAIN_CONFLICT`; a run that has not reached review is `422 DOMAIN_INVALID` |
| `GET /api/v1/runs/{run_id}/decision` | org, `finding.view` | – | `200 Decision` · `404` before a decision |
| `GET /api/v1/runs/{run_id}/receipt` | org, `evidence.view` | – | `200 Receipt` · `404` before finalization |
| `POST /api/v1/runs/{run_id}/verify` | org, `evidence.view` | – | `200 Verification` for an owned run; the outcome is in `status` |
| `GET /api/v1/audit/events` | org, `audit.read` | `limit, offset, run_id?` | `200 Page[AuditEvent]`: the organization's events plus its members' login and logout events |

## 6. Schemas

```text
Session         {identity_id, name, role, user_id, expires_at: float|null, csrf_token: str|null}
Organization    {id, name, status, role}
Member          {id, identity_id, name, email, role, status}
Invitation      Member + {credential}
Entity          {id, organization_id, display_name, sector, environment_class, created_at}
Assessment      {id, organization_id, entity_id, period_start, period_end, status, created_at}
Submission      {id, organization_id, entity_id, assessment_id, ingest_status, created_at}
Version         {id, organization_id, submission_id, version: int, status, created_at,
                 snapshot_digest: str|null}
Artifact        {id, submission_version_id, category, original_filename, content_type,
                 size_bytes, sha3_256_digest, created_at, storage_status}
Validation      {status, errors: [], warnings: [], version_id, categories: {}, totals: {str: int},
                 artifact_digests: {str: str}, validator_version: str|null, created_at: float|null}
CanonicalRecord {record_id, category, payload: {}, content_digest, source_record_id,
                 artifact_id, locator, file_digest, original_record_digest}
Run             {id, organization_id, entity_id, assessment_id, submission_id,
                 submission_version_id, status, requested_at, started_at|null, finished_at|null,
                 execution_id, execution_mode, review_required, current_stage, progress_total,
                 progress_completed, retry_count, error, error_code, steps: [Step]}
Step            {worker_name, status, attempt, started_at|null, finished_at|null, error}
Finding         {id, run_id, observation_id, rule_or_category, rationale, statistic|null,
                 effect|null, threshold|null, limitations, state, confidence: {}|null,
                 evidence_refs: [str], scoped_subjects: [], content_digest, created_at}
Evidence        {source_record_id, artifact_id, record_id, category, locator, format,
                 file_digest, original_record_digest, canonical_record_digest}
Risk            {profile: {entity_id, run_id, total_score, confidence_bucket,
                 dimensions: [{name, weight, score, finding_ids, rationale}], weights: {},
                 correlation_clusters: []}, content_digest, algorithm_version, created_at}
EntityPriority  {entity_id, run_id, run_status, priority_score, risk_score, confidence_bucket,
                 rationale, top_dimensions: [str], high_signal_count}
Recommendation  {id, finding_id, action, recommendation: {}, content_digest, created_at}
Decision        {id, run_id, finding_id|null, user_id, principal_identity_id, action, reason,
                 content_digest, review_context_digest|null, created_at}
Receipt         {id, organization_id, run_id, decision_id, schema_version, state, key_id,
                 algorithm_id, content_digest, created_at, ledger_entry_hash, signature_b64,
                 public_key_b64}
Verification    {run_id, status, verified_at, code, message}
AuditEvent      {event_id, timestamp, actor, action, resource, result}
```

A receipt carries the signature and public key only; private key material is
never served.

## 7. Status values

Each status field has its own vocabulary; none is reused for another concept.

| Field | Values | Meaning |
|---|---|---|
| `Assessment.status` | `open`, `closed` | submissions can be added only to an `open` period |
| `Version.status` | `created`, `uploading`, `uploaded`, `validating`, `valid`, `invalid`, `failed` | upload and validation lifecycle of one immutable submission version |
| `Validation.status` | `valid`, `invalid`, `failed` | `invalid`: errors, or no record accepted; `failed`: the validator could not complete |
| `Submission.ingest_status` | `created`, then the latest validated version's `valid`, `invalid` or `failed` | submission-level summary |
| `Artifact.storage_status` | `uploading`, `stored`, `failed` | only `stored` artifacts are readable and validated |
| `Run.status` | `queued`, `running`, `awaiting_review`, `cancel_requested`, `cancelled`, `completed`, `partial`, `failed` | analysis lifecycle; terminal: `completed`, `partial`, `failed`, `cancelled` |
| `Step.status` | `pending`, `running`, `completed`, `failed`, `skipped` | one analytical worker within a run |
| `Finding.state` | `signal`, `no_signal`, `insufficient_data`, `not_applicable`, `error` | one worker's result for one rule |
| `Decision.action` | `confirm`, `dismiss`, `escalate` | the supervisor's decision on the run |
| `Receipt.state` | `prepared`, `recorded`, `verified` | trust finalization progress |
| `Verification.status` | `verified`, `inconsistent`, `not_finalized`, `unavailable` | outcome of rebuilding and checking the signed state |
| `EntityPriority.run_status` | `awaiting_review`, `completed`, `partial` | status of the run the ranking used |

Run transitions (`satsa/analysis/execution.py`): `queued` → `running`,
`cancel_requested` or `failed`; `running` → `awaiting_review`, `completed`,
`partial`, `failed`, `cancel_requested`, `cancelled` or `queued` (lease
expiry); `awaiting_review` → `queued` (after the decision, for finalization)
or `cancel_requested`; `cancel_requested` → `cancelled` or `failed`; `failed`
→ `queued` (retryable failure). `awaiting_review` is a worker release at the
supervised checkpoint, not a frontend state.

## 8. Traces the client can rely on

**Finding → evidence → record.** `Finding.evidence_refs` contains source-record
IDs (`srcrec_…`). `GET /runs/{run_id}/evidence` resolves them to
`{source_record_id, record_id, canonical_record_digest, …}`.
`GET /versions/{submission_version_id}/records` returns the record content;
join on `source_record_id`. The record's `content_digest` equals the evidence
row's `canonical_record_digest`. `Run.submission_version_id` names the version.

**Entity → risk → priority.** `GET /priorities` lists, for each entity, the
latest run with a persisted risk profile (`awaiting_review`, `completed` or
`partial`) and a priority computed by the same function as the offline ranking
(`satsa.analysis.prioritize.entity_priority`: risk score plus confidence,
recency and high-severity-signal terms). The full profile of that run is
`GET /runs/{run_id}/risk`; `risk_score` equals its `total_score` rounded to two
decimals.

**Decision → finalization → receipt → verification.** After
`POST /runs/{id}/decision` the worker finalizes the run (canonical supervisory
digest, ML-DSA-65 signature, hash-chained ledger entry) and moves it to
`completed` or `partial`. `GET /runs/{id}/receipt` then returns the receipt,
and `POST /runs/{id}/verify` rebuilds the canonical state and checks signature
and ledger. The TRUST-SAT digest covers the supervisory state; artifact bytes
have their own SHA3-256 digests in `Artifact`.

Example (placeholders, shape from the schema):

```http
GET /api/v1/priorities?limit=50 HTTP/1.1
Authorization: Bearer <session token>
X-Organization-ID: <organization id>
```

```json
{
  "items": [
    {
      "entity_id": "<entity id>",
      "run_id": "<run id>",
      "run_status": "awaiting_review",
      "priority_score": 0.0,
      "risk_score": 0.0,
      "confidence_bucket": "<very_low|low|medium|high>",
      "rationale": "risk <n>/100; confidence <bucket>; top dimensions: <name>=<score>",
      "top_dimensions": ["<dimension>"],
      "high_signal_count": 0
    }
  ],
  "limit": 50,
  "offset": 0,
  "has_more": false
}
```

## 9. Errors

Every error body is
`{"error": {"code": str, "message": str, "request_id": str, "details": [...]}}`.
Validation `details` items are `{"location": [...], "code": str, "message": str}`.

| HTTP | Code | When |
|---|---|---|
| 400 | `ORGANIZATION_REQUIRED` | tenant route without a valid `X-Organization-ID` |
| 401 | `AUTHENTICATION_ERROR` | missing, invalid, expired or revoked credential or session |
| 403 | `PERMISSION_DENIED` | missing permission or membership, foreign resource, failed CSRF check |
| 403 | `ORIGIN_DENIED` | login from an origin that is not allowed |
| 404 | `NOT_FOUND` | resource absent, or not yet produced (risk, decision, receipt) |
| 409 | `DUPLICATE_ENTRY`, `IDENTITY_EXISTS` | uniqueness conflict |
| 409 | `DOMAIN_CONFLICT` | state conflict: second decision, reused idempotency key, immutable resource |
| 413 | `REQUEST_TOO_LARGE` | body over the configured limit |
| 422 | `VALIDATION_ERROR` | request schema, query or header validation |
| 422 | `DOMAIN_INVALID` | well-formed request that is not valid for the resource's state |
| 429 | `RATE_LIMITED` | rate window exceeded |
| 503 | `NOT_READY` | a readiness dependency is unavailable |
| 500 | `INTERNAL_ERROR`, or a platform code such as `STORAGE_ERROR` | unexpected failure |

Error bodies never contain stack traces, SQL, file paths or secret material.

## 10. Deployment configuration

Set `SATSA_DATABASE_URL`, `SATSA_DATA_DIR`, `SATSA_TRUST_KEY_DIR`,
`SATSA_LEDGER_PATH`, `SATSA_ALLOWED_HOSTS` and, for browser callers,
`SATSA_ALLOWED_ORIGINS`; wildcards are rejected. Cookie and limit settings are
in sections 1 and 3. Proxy headers are ignored unless
`SATSA_TRUST_PROXY_HEADERS=true` and `SATSA_TRUSTED_PROXIES` are set.

S3-compatible storage uses `SATSA_S3_ENDPOINT_URL`, `SATSA_S3_REGION`,
`SATSA_S3_BUCKET`, `SATSA_S3_ACCESS_KEY`, `SATSA_S3_SECRET_KEY` (omit both for
workload identity), `SATSA_S3_USE_SSL` and `SATSA_S3_ADDRESSING_STYLE`;
otherwise `SATSA_ARTIFACTS_DIR` (or `SATSA_DATA_DIR/artifacts`) selects local
storage. Production requires PostgreSQL, S3 storage, TLS, a pre-provisioned
signing key, an explicit durable ledger path, secure cookies, explicit hosts
and `SATSA_AUTO_MIGRATE=false`.

Migrations run as a deployment step: `python -m satsa.api.migrate upgrade`
(inspect with `status`, gate with `check`). API and worker reject an
out-of-date schema. The worker's container check is
`python -m satsa.api.healthcheck --role worker`. The hosting contract is in
`docs/deployment.md`.

## 11. Difference from the frontend proposal

`web/docs/API_CONTRACT.md` is an earlier frontend proposal: bearer-only global
reads, unpaginated camelCase arrays, per-finding reviews and about fifteen
routes that do not exist. It is kept as history. The frontend adapts to this
contract; wiring instructions are in `docs/FRONTEND_API_HANDOFF.md`. There are
no agents, meta-audit, benchmark-validation, observation or per-finding review
routes, and none will be added to satisfy the old proposal.
