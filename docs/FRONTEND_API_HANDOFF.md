# Frontend API handoff

For whoever wires `web/` to the SAT-SA backend. `docs/API_CONTRACT.md` is the
authoritative contract (section numbers below refer to it) and `/openapi.json`
is its machine-readable form; a test keeps the contract's route index and
schemas in step with the live API. This file says how the workbench should use
it. The audit behind it is `docs/FRONTEND_BACKEND_CONVERGENCE.md`.

Rule: the backend is the only source of analytical truth. The frontend shows
findings, risk, priorities, recommendations, decisions and trust state exactly
as returned and never recomputes them. There is no mock API; in API mode every
value comes from the calls below.

## 1. Base URL and transport

* `SATSA_API_BASE_URL` (server-side only, read by `web/src/lib/api/index.ts`) is
  the backend origin, for example `http://127.0.0.1:8000` locally. No host is
  hard-coded. `SATSA_DATA_SOURCE=api` selects the backend; `fixture` keeps the
  labelled development fixture.
* Call the API from Next.js server code only (server components, route
  handlers, server actions). The browser never talks to the API, so CORS is not
  involved and no API token reaches client JavaScript.
* Every request: `Accept: application/json`, `Authorization: Bearer <session token>`,
  and on tenant routes `X-Organization-ID: <organization id>`. Use
  `cache: "no-store"`. Optionally send `X-Request-ID` (letters, digits, `_`,
  `-`, up to 64) to correlate logs; the API echoes it.

## 2. Authentication and sessions

Recommended flow (contract section 1):

1. **Sign in.** Server action posts `POST /api/v1/session` with
   `{"credential": "<key_id.secret>"}`. On `200`, read the session token from
   the response's `Set-Cookie: satsa_api_session=<token>` header and store
   **that token**, not the credential, in the web's HttpOnly `satsa_session`
   cookie. The body is `Session {identity_id, name, role, user_id, expires_at,
   csrf_token}`; `expires_at` is the session expiry.
2. **Each request.** Send `Authorization: Bearer <session token>`. Bearer calls
   need no CSRF token.
3. **Current user.** `GET /api/v1/session` resolves the identity; `401` means
   the session expired or was revoked: clear the cookie and return to sign-in.
4. **Sign out.** `DELETE /api/v1/session` with the session token as bearer
   revokes only that session; then clear the cookie.

Never call `DELETE /api/v1/session` with a raw credential as bearer: that
revokes the credential itself and the user can no longer sign in.

Implemented in Phase 18 (`web/src/lib/auth/actions.ts`,
`web/src/lib/api/client.ts`): the web keeps only the session token, and
sign-out revokes it.

The session `role` is the identity's global role. The role that governs a
tenant page is the membership role from `GET /api/v1/organizations`. Hide
controls by that role for convenience only; the backend enforces every
permission (`403 PERMISSION_DENIED`).

## 3. Organization selection

* `GET /api/v1/organizations` → `Page[{id, name, status, role}]`: the signed-in
  user's active memberships.
* Store the selected organization ID in a server-side cookie (for example
  `satsa_org`) and send it as `X-Organization-ID` on every tenant call. With
  one membership select it automatically; with several, show a selector.
* `400 ORGANIZATION_REQUIRED` means the header was missing; `403` on a stale or
  foreign organization means: clear the selection and ask again. The backend
  checks membership, role and resource ownership on every request; the stored
  organization ID grants nothing by itself.

## 4. Collections and field names

Every list returns `{items, limit, offset, has_more}` (`limit` ≤ 200, default
50). Page with `offset` until `has_more` is false. Fields are `snake_case`;
times are Unix epoch seconds. Replace the array and camelCase assumptions in
`web/src/lib/api/http.ts` and the `src/lib/types/domain.ts` mappings.

## 5. Workbench flow to backend calls

| Step | Call(s) | Required role |
|---|---|---|
| Login | `POST /api/v1/session` | any member |
| Organization | `GET /api/v1/organizations` | any member |
| Entity | `GET /api/v1/entities`, `GET /api/v1/entities/{id}`; create `POST /api/v1/entities` | view: any; create: analyst, supervisor, admin |
| Assessment period | `GET /api/v1/assessments?entity_id=`; create `POST /api/v1/assessments` `{entity_id, period_start, period_end}` | as above |
| Submission | `POST /api/v1/submissions` `{assessment_id}` (period must be `open`) | analyst, supervisor, admin |
| Upload | `POST /api/v1/submissions/{id}/versions`, then per file `POST /api/v1/versions/{id}/artifacts?category=…` (multipart `file`) | analyst, supervisor, admin |
| Validation | `POST /api/v1/versions/{id}/complete`, `POST /api/v1/versions/{id}/validate`; read `GET /api/v1/versions/{id}/validation`, `/summary` | analyst, supervisor, admin (read: any) |
| Run | `POST /api/v1/runs` `{submission_version_id, execution_mode}` | analyst, supervisor, admin |
| Run status | `GET /api/v1/runs/{id}` (poll), `GET /api/v1/runs/{id}/steps`, `GET /api/v1/runs?entity_id=&status=` | any |
| Findings | `GET /api/v1/runs/{id}/findings`, `GET /api/v1/findings/{id}` | any |
| Evidence | `GET /api/v1/runs/{id}/evidence` + `GET /api/v1/versions/{version_id}/records` | any |
| Risk | `GET /api/v1/runs/{id}/risk` | any |
| Priority | `GET /api/v1/priorities` | any |
| Recommendation | `GET /api/v1/runs/{id}/recommendations` | any |
| Review | the run's findings, evidence, risk and recommendations while `status` is `awaiting_review` | any |
| Decision | `POST /api/v1/runs/{id}/decision`; read `GET /api/v1/runs/{id}/decision` | supervisor, admin (read: any) |
| TRUST-SAT | `GET /api/v1/runs/{id}/receipt`, `POST /api/v1/runs/{id}/verify` | any |
| Audit | `GET /api/v1/audit/events?run_id=` | auditor, admin |

"Any" means any active membership role: viewer, analyst, supervisor, auditor
or admin.

## 6. Upload and validation (replaces `ingest-actions.ts`)

Every creating call needs an `Idempotency-Key` header (1–128 characters).
Generate one per logical step and reuse it when retrying that step; the same
key with the same content returns the original resource.

1. `POST /submissions` `{assessment_id}` → `Submission`.
2. `POST /submissions/{id}/versions` → `Version` (`status: "created"`).
3. For each file: `POST /versions/{version_id}/artifacts?category=<category>`
   with multipart field `file`. Categories: `alerts`, `cases`,
   `investigation_steps`, `escalations`, `dispositions`, `assets`. Check
   `storage_status == "stored"`.
4. `POST /versions/{id}/complete` → `Version` (`uploaded`).
5. `POST /versions/{id}/validate` → `Validation {status, errors, warnings,
   totals, categories, artifact_digests}`. `status`: `valid` (proceed),
   `invalid` (show `errors`/`warnings` as returned; upload a new version),
   `failed` (validator could not complete; retry).
6. Optional: `GET /versions/{id}/summary` → canonical record counts.

## 7. Run lifecycle and polling

* Start: `POST /runs` `{submission_version_id, execution_mode: "graph" | "standard"}`
  with `Idempotency-Key` → `202 Run`. The version must be `valid`. API runs
  always stop for human review.
* Poll `GET /runs/{id}` every 2–5 seconds until the status changes. Show
  `status`, `current_stage`, `progress_completed`/`progress_total` and
  `steps[]` (`worker_name`, `status` of `pending`/`running`/`completed`/
  `failed`/`skipped`). Do not animate progress the backend has not reported.
* `Run.status`: `queued`, `running`, `awaiting_review` (analysis done, waiting
  for the supervisor), `cancel_requested`, `cancelled`, `completed`,
  `partial`, `failed`. Stop polling at `awaiting_review` and at the terminal
  states `completed`, `partial`, `failed`, `cancelled`; resume after a
  decision until `completed` or `partial`.
* Cancel: `POST /runs/{id}/cancel` (supervisor, admin).

## 8. Findings, evidence, risk, priorities, recommendations

**Findings.** `GET /runs/{id}/findings` → `Finding {id, rule_or_category,
rationale, statistic, effect, threshold, limitations, state, confidence,
evidence_refs, scoped_subjects, content_digest}`. `state`: `signal`,
`no_signal`, `insufficient_data`, `not_applicable`, `error`. There is no
organization-wide finding list: load findings per run.

**Evidence (do not reconstruct it from other tables).**

1. `Finding.evidence_refs` holds source-record IDs.
2. `GET /runs/{run_id}/evidence` maps them to
   `{source_record_id, record_id, category, locator, artifact_id,
   canonical_record_digest, …}`.
3. `GET /versions/{run.submission_version_id}/records?category=` returns the
   record content `{record_id, category, payload, content_digest,
   source_record_id, …}`. Join on `source_record_id`; the record's
   `content_digest` equals the evidence row's `canonical_record_digest`.

The same records route with a `category` filter serves the security-data view
for the entity's latest submission version.

**Risk.** `GET /runs/{id}/risk` → `{profile: {total_score, confidence_bucket,
dimensions: [{name, weight, score, finding_ids, rationale}], weights,
correlation_clusters}, content_digest, algorithm_version}`. `404` until the run
has persisted its risk. Weights are inside the profile.

**Priorities.** `GET /priorities` → `EntityPriority {entity_id, run_id,
run_status, priority_score, risk_score, confidence_bucket, rationale,
top_dimensions, high_signal_count}`, highest first. An entity's current
findings, risk and recommendations are those of the `run_id` in its row. The
ranking uses the same function as the offline tool; do not rank in the
frontend. Example response shape: contract section 8.

**Recommendations.** `GET /runs/{id}/recommendations` → `{finding_id, action,
recommendation, content_digest}`.

## 9. Review and decision (replaces `review-actions.ts`)

* The supervisory decision is **one per run**, not per finding:
  `POST /runs/{id}/decision` `{action: "confirm" | "dismiss" | "escalate",
  reason}` (reason ≤ 4000 characters). Allowed for the membership roles
  `satsa_supervisor` and `satsa_admin`; others get `403`.
* Only while the run is `awaiting_review`; otherwise `422 DOMAIN_INVALID`.
  An identical retry returns the same `201 Decision`; a different second
  decision is `409 DOMAIN_CONFLICT`.
* `GET /runs/{id}/decision` reads it (`404` before a decision).
* After the decision the worker finalizes the run; poll `GET /runs/{id}` until
  `completed` or `partial`.
* The UI actions `request_review`, `annotate`, `defer` and `false_positive`
  have no API equivalent. In API mode remove them or keep them disabled with a
  label; do not map them onto `confirm` or `dismiss`.

## 10. TRUST-SAT verification

* `GET /runs/{id}/receipt` → `{state, key_id, algorithm_id, content_digest,
  ledger_entry_hash, signature_b64, public_key_b64, created_at, …}` after
  finalization (`404` before). `state`: `prepared`, `recorded`, `verified`.
  Only public material is served.
* `POST /runs/{id}/verify` rebuilds the canonical supervisory state and checks
  signature and ledger → `{status, code, message, verified_at}`. `status`:
  `verified` (the only success), `inconsistent`, `not_finalized`,
  `unavailable`. Show it verbatim with `verified_at`.

## 11. Audit and administration

* `GET /audit/events?run_id=` (auditor, admin) → `{event_id, timestamp, actor,
  action, resource, result}`.
* `GET/POST /members`, `DELETE /members/{user_id}` (admin). `POST /members`
  returns the new member's credential once: show it once, never store it.
* `POST /organizations` needs a global administrator identity.

## 12. Errors

Every error body is `{"error": {"code", "message", "request_id", "details"}}`;
`details` holds `{location, code, message}` for field errors.

| Code | HTTP | UI treatment | Retry |
|---|---|---|---|
| `ORGANIZATION_REQUIRED` | 400 | select an organization | after selection |
| `AUTHENTICATION_ERROR` | 401 | clear session, sign in again | after sign-in |
| `PERMISSION_DENIED` | 403 | "not permitted" (also foreign or unknown IDs) | no |
| `ORIGIN_DENIED` | 403 | configuration problem; not expected for server-side calls | no |
| `NOT_FOUND` | 404 | "not found" or "not produced yet" (risk, decision, receipt) | poll later where relevant |
| `DUPLICATE_ENTRY`, `IDENTITY_EXISTS`, `DOMAIN_CONFLICT` | 409 | show message | no |
| `REQUEST_TOO_LARGE` | 413 | file too large | after change |
| `VALIDATION_ERROR`, `DOMAIN_INVALID` | 422 | show `details` messages | after correction |
| `RATE_LIMITED` | 429 | "try again shortly" | yes, with backoff |
| `NOT_READY` | 503 | "service not ready" | yes |
| `INTERNAL_ERROR` and other 5xx | 500 | generic failure | yes |

Always show `request_id` (also in the `X-Request-ID` header) so an operator can
trace the request. The API never returns stack traces, SQL, paths or secrets;
the frontend must not add them.

## 13. Offline-only panels in API mode

`getMetaAudit`, `getValidation` (benchmark validation), `getSupervisorDecision`,
`listObservations` and `listAgents` have no hosted API route. In API mode hide
these panels or show a labelled "available in the offline tool" state. Do not
fill them from the fixture.

## 14. Done means

With `SATSA_DATA_SOURCE=api`, a signed-in user can select an organization,
create or select an entity and assessment period, upload and validate
evidence, start a run, watch its persisted status, inspect findings, evidence
records, risk, priorities and recommendations, record the run decision, verify
TRUST-SAT and read the audit trail, with every value coming from the calls
above. `scripts/deployment_smoke.py` performs the same sequence over HTTP and
is the reference implementation; `tests/test_phase17_http_topology.py` runs it
against real API and worker processes.
