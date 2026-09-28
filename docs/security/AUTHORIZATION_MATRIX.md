# SAT-SA API authorization matrix

Derived from the implemented routes (`satsa/api/__init__.py`), the role
permissions (`qsmlops/security/permissions/model.py`) and the service checks
(`satsa/tenancy.py`, `satsa/submissions/service.py`,
`satsa/analysis/execution.py`). `tests/test_phase20_authorization.py` holds
the same matrix as data, fails if a route is added without an entry, and
checks every route for every role on SQLite and PostgreSQL.

Every tenant route requires (1) an authenticated caller (bearer credential,
bearer session token, or the API session cookie with a CSRF token for
mutations), (2) `X-Organization-ID` naming an organization where the caller
has an **active** membership, with the user, identity and organization all
active, and (3) the permission below. Objects are always looked up within
that organization; a foreign object is indistinguishable from a missing one.

Roles: **V** viewer, **An** analyst, **S** supervisor, **Au** auditor, **Ad** admin.

| Route | V | An | S | Au | Ad | Check |
|---|---|---|---|---|---|---|
| `POST /api/v1/session` | public | | | | | valid credential; 5/min per address; exact-origin check |
| `GET, DELETE /api/v1/session` | any authenticated caller | | | | | own session; bearer-key logout revokes that key |
| `GET /api/v1/organizations` | own memberships only | | | | | |
| `POST /api/v1/organizations` | | | | | ✓ | identity role `identity.manage`; creator becomes its admin |
| `GET /api/v1/members` | | | | | ✓ | `identity.read`; shows membership status (revoked members read as revoked) |
| `POST /api/v1/members` | | | | | ✓ | `identity.manage` |
| `DELETE /api/v1/members/{user_id}` | | | | | ✓ | `identity.manage`; member of this organization; not the caller |
| `GET` entities, assessments, submissions, versions, runs, steps, findings, evidence, risk, priorities, recommendations, decision, receipt, artifacts, validation, summary, records | ✓ | ✓ | ✓ | ✓ | ✓ | `finding.view` / `evidence.view` / `review.read` |
| `POST` entities, assessments | | ✓ | ✓ | | ✓ | `analysis.run` |
| `POST` submissions, versions, artifacts (upload), complete, validate | | ✓ | ✓ | | ✓ | `analysis.run` |
| `POST /api/v1/runs` | | ✓ | ✓ | | ✓ | `analysis.run`; version must be valid |
| `POST /api/v1/runs/{id}/decision` | | | ✓ | | ✓ | `review.create` **and** membership role supervisor or admin |
| `POST /api/v1/runs/{id}/cancel` | | | ✓ | | ✓ | as decision |
| `POST /api/v1/runs/{id}/verify` | ✓ | ✓ | ✓ | ✓ | ✓ | `evidence.view` (read-only integrity check, audited) |
| `GET /api/v1/audit/events` | | | | ✓ | ✓ | `audit.read`; events of this organization only |
| `GET /health/live`, `/health/ready` | public (internal network only) | | | | | no data |

## Review of sensitive endpoints

- **Decision and cancel** check both the permission and the membership role,
  so a custom role holding `review.create` still cannot decide unless it is a
  supervisor or administrator membership: the human-authority rule of the
  design.
- **Verify** is available to every role on purpose: verification reads and
  reports, and a viewer being able to confirm integrity is a feature. It is
  audited (`trust.verification_requested`).
- **Audit events** are limited to auditor and administrator; the run filter
  refuses a foreign run.
- **Member revocation** was the one inconsistency found: an administrator
  could revoke their own membership (possibly leaving the organization with
  no administrator), and revoked members still listed as `active`. Both are
  fixed in Phase 20; nothing else needed a permission change.
- **Organization creation** uses the identity-level role, so any identity
  with the administrator role can create organizations. It cannot reach
  existing organizations (it grants membership only in the new one); this is
  recorded as a provisioning choice in the threat model.
