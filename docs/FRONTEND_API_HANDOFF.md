# Frontend API handoff

For whoever wires `web/` to the SAT-SA backend. The backend contract is
`docs/API_CONTRACT.md` (authoritative) and `/openapi.json` (machine
readable). This file says how the workbench should use it. The audit behind
it is `docs/FRONTEND_BACKEND_CONVERGENCE.md`.

Rule: the backend is the only source of analytical truth. The frontend
displays findings, risk, priorities, recommendations, decisions and trust
state exactly as returned; it never recomputes them.

## 1. Base URL and transport

* `SATSA_API_BASE_URL` (server-side only, already read by
  `web/src/lib/api/index.ts`) is the backend origin, for example
  `http://127.0.0.1:8000` locally. No host is hard-coded.
* `SATSA_DATA_SOURCE=api` selects the backend; `fixture` keeps the labelled
  development fixture.
* Calls are made from Next.js server code (server components and server
  actions), so the browser never talks to the API directly and CORS is not
  needed. If a browser ever calls the API directly, its origin must be listed
  in the backend's `SATSA_ALLOWED_ORIGINS` (HTTPS in production; wildcards
  are rejected) and cookie mutations must send `X-CSRF-Token`.
* Every request: `Accept: application/json`,
  `Authorization: Bearer <credential>` and, for tenant routes,
  `X-Organization-ID: <organization id>`. Send `cache: "no-store"`; the API
  also returns `Cache-Control: no-store`.

## 2. Authentication

Already compatible (`web/src/lib/auth/adapters/backend.ts`):

* `POST /api/v1/session` `{credential}` returns `200 Session`
  `{identity_id, name, role, user_id, expires_at, csrf_token}`; `401` bad
  credential; `429` rate limited.
* `GET /api/v1/session` with the bearer credential resolves the identity.
* `DELETE /api/v1/session` revokes (bearer: revokes the credential).

The session `role` describes the identity. The role that governs a tenant
page is the membership role returned by `GET /api/v1/organizations`. Hide
controls by that role for convenience only; the backend enforces every
permission and returns `403 PERMISSION_DENIED` otherwise.

## 3. Organization selection (new)

* `GET /api/v1/organizations` returns `Page[{id, name, status, role}]` for
  the signed-in user.
* Keep the selected organization in a server-side cookie (for example
  `satsa_org`) and send it as `X-Organization-ID` on every tenant call. With
  one membership, select it automatically; with several, show a selector.
* A foreign or stale organization ID returns 403/404: clear the selection.

## 4. Collections

All lists return `{items, limit, offset, has_more}`; default `limit` 50,
maximum 200. Page with `offset` until `has_more` is false. Fields are
`snake_case`; times are Unix epoch seconds (UTC). Replace the current
array/camelCase assumptions in `http.ts` and `src/lib/types/domain.ts`
mappings accordingly.

## 5. Entities, assessments, submissions

| UI need | Call |
|---|---|
| entity list / detail | `GET /entities`, `GET /entities/{id}` |
| create entity | `POST /entities` `{display_name, sector?, environment_class?}` |
| assessment periods | `GET /assessments?entity_id=`; create `POST /assessments` `{entity_id, period_start, period_end}` |
| submissions | `GET /submissions?entity_id=`, `GET /submissions/{id}/versions`, `GET /versions/{id}` |

## 6. Upload and validation (replaces `ingest-actions.ts`)

The backend upload is a sequence, not one multipart request. Every creating
call takes an `Idempotency-Key` header (1–128 printable characters); reuse
the same key when retrying the same step.

1. `POST /submissions` `{assessment_id}` → `Submission`.
2. `POST /submissions/{id}/versions` → `Version`.
3. For each file: `POST /versions/{id}/artifacts?category=<category>` with
   multipart field `file`. Categories: `alerts`, `cases`,
   `investigation_steps`, `escalations`, `dispositions`, `assets`. Only
   `storage_status: "stored"` artifacts count.
4. `POST /versions/{id}/complete`, then `POST /versions/{id}/validate` →
   `Validation {status, errors, warnings, totals, categories, artifact_digests}`.
   Show `errors` and `warnings` as returned. Version statuses: `created`,
   `uploading`, `uploaded`, `validating`, `valid`, `invalid`, `failed`.
5. `GET /versions/{id}/summary` gives canonical record counts per category.

## 7. Analysis run lifecycle and polling

* Start: `POST /runs` `{submission_version_id, execution_mode: "graph" | "standard"}`
  with `Idempotency-Key` → `202 Run`. Requires a `valid` version. Runs
  created by the API always stop for human review.
* Poll `GET /runs/{id}` every 2–5 s while the status is not terminal. Use
  `status`, `current_stage`, `progress_completed`/`progress_total` and
  `steps[]` (`worker_name, status, attempt, started_at, finished_at`). These
  are persisted backend state; do not animate progress the backend has not
  reported.
* Statuses: `queued`, `running`, `awaiting_review`, `cancel_requested`,
  `completed`, `partial`, `failed`, `cancelled`. Terminal: `completed`,
  `partial`, `failed`, `cancelled`. `awaiting_review` means the analysis is
  done and waits for the supervisor.
* Cancel: `POST /runs/{id}/cancel` (supervisor/admin); cooperative.
* List: `GET /runs?entity_id=&status=`.

## 8. Findings, evidence, risk, priorities, recommendations

| UI need | Call |
|---|---|
| findings of a run | `GET /runs/{id}/findings` → `Finding {id, rule_or_category, rationale, statistic, effect, threshold, limitations, state, confidence, evidence_refs, scoped_subjects, content_digest}` |
| one finding | `GET /findings/{id}` |
| cited evidence | `GET /runs/{id}/evidence` → source pointers `{source_record_id, record_id, category, locator, artifact_id, canonical_record_digest, ...}` |
| evidence content | `GET /versions/{version_id}/records?category=` → `{record_id, category, payload, content_digest, source_record_id, locator, ...}`; join on `source_record_id` |
| security data view | `GET /versions/{version_id}/records?category=alerts` (and the other categories) for the entity's latest submission version |
| risk | `GET /runs/{id}/risk` → `{profile: {total_score, confidence_bucket, dimensions[{name, weight, score, finding_ids, rationale}], weights, correlation_clusters}, content_digest, algorithm_version}` |
| entity ranking | `GET /priorities` → `{entity_id, run_id, run_status, priority_score, risk_score, confidence_bucket, rationale, top_dimensions, high_signal_count}`, ordered highest first |
| recommendations | `GET /runs/{id}/recommendations` → `{finding_id, action, recommendation, content_digest}` |

An entity's "current" findings and risk are those of `run_id` in its
`/priorities` row. There is no organization-wide finding list; load findings
per run.

## 9. Review and decision (replaces `review-actions.ts`)

* The supervisory decision is **one per run**, not per finding:
  `POST /runs/{id}/decision` `{action: "confirm" | "dismiss" | "escalate", reason}`
  (reason ≤ 4000 characters). Supervisor/admin only. An identical retry
  returns the same decision; a different second decision is rejected
  (`409 DOMAIN_CONFLICT`).
* `GET /runs/{id}/decision` reads it (404 before a decision).
* After the decision the worker finalizes the run; poll `GET /runs/{id}`
  until it is `completed` or `partial`.
* The current UI actions `request_review`, `annotate`, `defer` and
  `false_positive` have no API equivalent. Remove them in API mode or keep
  them disabled with a label; do not map them onto `confirm`/`dismiss`.

## 10. TRUST-SAT

* `GET /runs/{id}/receipt` → the signed receipt `{state, key_id,
  algorithm_id, content_digest, ledger_entry_hash, signature_b64,
  public_key_b64, created_at}` once finalized.
* `POST /runs/{id}/verify` rebuilds the canonical supervisory state and
  checks signature and ledger: `{status: "verified" | "inconsistent" |
  "not_finalized" | "unavailable", code, message, verified_at}`. Show the
  status verbatim; `verified` is the only success state.

## 11. Audit and administration

* `GET /audit/events?run_id=` (auditor/admin) → `{event_id, timestamp,
  actor, action, resource, result}`.
* `GET/POST /members`, `DELETE /members/{user_id}` (admin). `POST /members`
  returns the new member's credential once; show it once and never store it.
* `GET/POST /organizations` (global identity administrators).

## 12. Errors

Every error body is
`{"error": {"code", "message", "request_id", "details": []}}`.

| Code | HTTP | UI treatment | Retry |
|---|---|---|---|
| `AUTHENTICATION_ERROR` | 401 | return to sign-in | after sign-in |
| `PERMISSION_DENIED` | 403 | "not permitted" (also for foreign IDs) | no |
| `NOT_FOUND` | 404 | "not found" | no |
| `VALIDATION_ERROR`, `DOMAIN_INVALID` | 422 | show `details` field messages | after correction |
| `DUPLICATE_ENTRY`, `DOMAIN_CONFLICT` | 409 | show message | no |
| `RATE_LIMITED` | 429 | "try again shortly" | yes, with backoff |
| `REQUEST_TOO_LARGE` | 413 | file too large | after change |
| `NOT_READY` | 503 | "service not ready" | yes |
| `INTERNAL_ERROR` | 500 | generic failure | yes |

Always display `request_id` (also in the `X-Request-ID` response header) so
an operator can trace the request in the backend logs. The API never returns
stack traces, SQL, file paths or secrets; the frontend must not add them.

## 13. Offline-only panels in API mode

`getMetaAudit`, `getValidation` (benchmark validation), `getSupervisorDecision`
and `listObservations` have no hosted API equivalent. In API mode, hide these
panels or show a labelled "available in the offline tool" state. Do not fill
them from the fixture.

## 14. Done means

With `SATSA_DATA_SOURCE=api`, a signed-in user can select an organization,
create or select an entity and assessment period, upload and validate
evidence, start a run, watch its persisted status, inspect findings,
evidence records, risk, priorities and recommendations, record the run
decision, and verify TRUST-SAT, with every value coming from the calls above.
`scripts/deployment_smoke.py` exercises the same sequence over HTTP and can be
used as the reference.
