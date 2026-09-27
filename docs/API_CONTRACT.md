# SAT-SA backend API contract, version 1

This backend-owned contract is implemented by `satsa.api`; it does not replace
or edit the frontend proposal in `web/docs/API_CONTRACT.md`. Machine-readable
schemas are served at `/openapi.json`. Run `python -m satsa.api.server` to serve
the API. All product routes use `/api/v1`; only `/health/live` and
`/health/ready` are outside the prefix. HTML/demo routes are not mounted.

## Authentication and scope

`POST /api/v1/session` accepts `{ "credential": "key_id.secret" }` and returns
the authenticated identity, user, role, expiration, and session-bound CSRF
token. It sets an HttpOnly, Secure (hosted default), SameSite=Lax cookie.
`GET /api/v1/session` resolves current credentials/session. `DELETE` revokes the
persisted browser session, or revokes the bearer credential when bearer auth was
used. Credential revocation invalidates sessions derived from that credential.
The cookie mutation contract requires `X-CSRF-Token`. API/CLI callers use
`Authorization: Bearer <credential>`.

Every tenant endpoint requires `X-Organization-ID`. The authenticated identity
must resolve to an active SAT-SA user and active membership. Permissions are
checked from the organization membership for every operation, then resources
are fetched through tenant-scoped repositories/services. Unknown/foreign IDs
return 403 or 404 without disclosing another tenant's existence. API-created
runs always require human review. The current `role` in the session response
describes the identity; the organization-list response is authoritative for the
role in each selected organization.

## Common conventions

JSON properties use `snake_case`; identifiers are opaque SAT-SA IDs, and times
are Unix epoch seconds (UTC). Collections return
`{items, limit, offset, has_more}`, default limit 50, maximum 200, stable
`created_at,id` ordering unless noted. Offset must be 0..1,000,000. Run steps,
findings, evidence, recommendations, organizations, memberships, and audit
events have bounded pages. Filters are whitelisted: entity and run status on
run listing; entity on assessments/submissions; run ID on audit listing. No
client-controlled SQL filters or sorting are accepted.

Responses include `X-Request-ID` and `Cache-Control: no-store`. Errors are
`{ "error": {"code", "message", "request_id", "details": []} }`. Codes
distinguish `AUTHENTICATION_ERROR`, `PERMISSION_DENIED`, `NOT_FOUND`,
`DUPLICATE_ENTRY`, `DOMAIN_CONFLICT`, `DOMAIN_INVALID`, `VALIDATION_ERROR`,
`RATE_LIMITED`, `REQUEST_TOO_LARGE`, `NOT_READY`, and `INTERNAL_ERROR`.
Validation details contain request field locations and validator messages.
Unexpected failures do not return stack traces, SQL, paths, or secret material.

## Resource routes

`{limit=50,offset=0}` applies wherever a collection is returned.

| Method and route | Request | Permission/behavior | Success |
|---|---|---|---|
| `POST /session`, `GET /session`, `DELETE /session` | credential on login; CSRF for cookie logout | QSMLOps identity credentials, persistent revocable session | `200 Session`, `204` logout |
| `GET /organizations` | pagination | active memberships of current user | `Page[Organization]` |
| `POST /organizations` | `{name}` | global `identity.manage`; creator becomes org admin | `201 Organization` |
| `GET /members` | pagination | `identity.read` | `Page[Member]` |
| `POST /members` | `{name,email,role}` | `identity.manage`; role enum below | `201 Invitation`, raw credential shown once |
| `DELETE /members/{user_id}` | none | `identity.manage`; revokes membership | `204` |
| `GET,POST /entities`; `GET /entities/{id}` | create `{display_name,sector?,environment_class?}` | view/create permission; organization scoped | paginated `Entity`, or `201 Entity` |
| `GET,POST /assessments`; `GET /assessments/{id}` | `{entity_id,period_start,period_end}` | tenant entity required | paginated `Assessment`, or `201 Assessment` |
| `GET,POST /submissions`; `GET /submissions/{id}` | create `{assessment_id}` + `Idempotency-Key` | analyst/admin; key scoped by org+assessment | paginated `Submission`, or `201 Submission` |
| `POST /submissions/{id}/versions`; `GET /submissions/{id}/versions`; `GET /versions/{id}` | create uses `Idempotency-Key` | immutable version; tenant parent required | `201 Version` or paginated versions |
| `POST /versions/{id}/artifacts?category=alerts` | multipart field `file`, `Idempotency-Key` | bounded stream; server checks format/name/size/digest | `201 Artifact` |
| `GET /versions/{id}/artifacts`; `GET /artifacts/{id}` | pagination | evidence permission | paginated or `Artifact`; no storage path |
| `POST /versions/{id}/complete`, `POST /versions/{id}/validate` | none | controlled Phase2 transitions | `Version`, durable `Validation` |
| `GET /versions/{id}/validation`, `GET /versions/{id}/summary` | none | tenant version; summary contains canonical record counts only | `Validation`, `{version_id,counts}` |
| `POST /runs` | `{submission_version_id,execution_mode:"graph"|"standard"}` + `Idempotency-Key` | requires validated version; both modes require review | `202 Run` |
| `GET /runs`, `GET /runs/{id}` | pagination, optional `entity_id,status` | tenant scoped | `Page[Run]`, `Run` |
| `POST /runs/{id}/cancel` | none | supervisor/admin only; cooperative cancellation | updated `Run` |
| `GET /runs/{id}/steps`, `/findings`, `/evidence`, `/risk`, `/recommendations` | pagination | corresponding view permissions | page or persisted risk profile |
| `GET /priorities` | pagination | finding view; organization scoped; one row per entity from its latest run with a persisted risk profile (`awaiting_review`, `completed` or `partial`), ranked by the same priority function as the offline pipeline; read-only, nothing recomputed from source data | `Page[EntityPriority]` `{entity_id,run_id,run_status,priority_score,risk_score,confidence_bucket,rationale,top_dimensions,high_signal_count}` |
| `GET /findings/{id}` | none | tenant scoped | `Finding` including available confidence and exact evidence refs |
| `GET,POST /runs/{id}/decision` | action `confirm|dismiss|escalate`, reason ≤4000 | supervisor/admin; one immutable decision, identical retry returns same decision | `Decision`, or `201 Decision` |
| `GET /runs/{id}/receipt`; `POST /runs/{id}/verify` | none | evidence/trust permission; verification rebuilds canonical state | signed receipt, or structured `Verification` |
| `GET /audit/events` | pagination, optional run ID | `audit.read`; tenant events plus member login/logout events | `Page[AuditEvent]` |
| `GET /health/live`, `/health/ready` | none | non-sensitive process/dependency status | `{status:alive|ready}` |

Membership roles are `satsa_viewer`, `satsa_analyst`, `satsa_supervisor`,
`satsa_auditor`, and `satsa_admin`. Analysts can create submissions and runs;
viewers inspect authorized analytical resources; only supervisors/admins record
terminal decisions or cancel; only auditors/admins read audit events; admin
membership/identity management follows the existing permissions. The backend
does not allow users to set run states or final trust status.

Idempotency is required for submission, version, artifact, and analysis
creation. The header is 1–128 printable non-space characters; each operation's
existing tenant service determines its scope. Same-key/same-content retries
return the original resource, while reusing a key for changed content conflicts.
The existing review service returns the original row for an identical decision
retry and rejects a different second decision. Trust finalization uses Phase5's
database identity rather than a caller key.

## Status meanings

Submission-version statuses come from Phase2: `created`, `uploading`,
`uploaded`, `validating`, `valid`, `invalid`, `failed`. Run states are Phase3/4:
`queued`, `running`, `awaiting_review`, `cancel_requested`, `completed`,
`partial`, `failed`, `cancelled`. `awaiting_review` is a genuine worker release
at the graph/non-graph supervised checkpoint. `cancel_requested` is
cooperative. Trust states are `prepared`, `recorded`, `verified`; an API
`Verification.status` additionally distinguishes `not_finalized`,
`inconsistent`, and `unavailable`. These are projections of persisted backend
state, not frontend animation states.

## Security and deployment configuration

Set `SATSA_DATABASE_URL`, `SATSA_DATA_DIR`, `SATSA_TRUST_KEY_DIR`,
`SATSA_LEDGER_PATH`, `SATSA_ALLOWED_HOSTS`, and (when needed)
`SATSA_ALLOWED_ORIGINS`. Set cookie security, request and rate limits with
`SATSA_COOKIE_SECURE`, `SATSA_MAX_REQUEST_BYTES`,
`SATSA_MUTATION_RATE_LIMIT`, `SATSA_READ_RATE_LIMIT`; `SATSA_SESSION_TTL_SECONDS`
controls expiry. API rate windows are database backed and shared among API
instances. Login defaults to five attempts per IP per minute. TLS termination
and proxy addresses are infrastructure responsibilities; proxy headers are
ignored unless `SATSA_TRUST_PROXY_HEADERS=true` and explicit
`SATSA_TRUSTED_PROXIES` are configured. Wildcard hosts/origins are rejected.

S3-compatible storage uses `SATSA_S3_BUCKET`, optional endpoint/region/prefix,
and standard boto credential resolution; otherwise `SATSA_ARTIFACTS_DIR` (or
`SATSA_DATA_DIR/artifacts`) selects local storage. Hosted local artifacts,
keys, and audit ledger require durable/shared mounted storage. Bucket retention
and encryption policies are configured by the operator. `Idempotency-Key`
upload requests are multipart and streamed to bounded temporary storage; the
client digest is never authoritative.

Artifact responses include `storage_status` (`uploading`, `stored`, `failed`);
only `stored` artifacts are readable or eligible for validation. Repeating an
interrupted upload with the same key and same content retries the object write;
changed content conflicts.

Deployment environment variables use the `SATSA_S3_*` namespace:
`SATSA_S3_ENDPOINT_URL`, `SATSA_S3_REGION`, `SATSA_S3_BUCKET`,
`SATSA_S3_ACCESS_KEY`, `SATSA_S3_SECRET_KEY`, `SATSA_S3_USE_SSL`, and
`SATSA_S3_ADDRESSING_STYLE`. Credentials may be omitted when the provider's
workload identity supplies them. Production requires PostgreSQL, S3 storage,
TLS, a pre-provisioned signing key, explicit durable ledger path, secure cookies,
explicit hosts, and `SATSA_AUTO_MIGRATE=false`.

Migrations are run by the deployment step with
`python -m satsa.api.migrate upgrade`; inspect with `status` or gate startup with
`check`. API and worker startup reject an out-of-date schema and never migrate
automatically in production. `/health/live` is process-only and does not query
the database. `/health/ready` checks database connectivity, schema version,
trust configuration, and artifact-storage connectivity. The separate worker
container check uses `python -m satsa.api.healthcheck --role worker`.

## Contract difference from the frontend proposal

The existing frontend proposal is retained as a proposal and currently expects
bearer-only global reads, unpaginated arrays, `periodStart/periodEnd`, and
fixture-shaped camelCase types. This backend uses `X-Organization-ID`, pages,
`period_start/period_end`, and the explicit Pydantic shapes above. Existing
legacy HTML endpoints are separate and are not SaaS API routes. The integration
checkpoint must update the frontend's HTTP adapter/types to this contract;
this phase does not edit those files. There are no `agents`, MLOps model, or
fake drift endpoints. Physical artifact-byte digest checking remains distinct
from TRUST-SAT's canonical supervisory digest; the verification route currently
verifies the latter and the stored source metadata.
