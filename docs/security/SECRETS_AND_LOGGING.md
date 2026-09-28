# Secrets, keys and logging: Phase 20 review

## Inventory

| Secret | Created by | Stored | Exposure paths | Rotation |
|---|---|---|---|---|
| PostgreSQL password | operator (`openssl rand -hex 32`) | `deploy/production.env` (0600, git-ignored); container environment of database, migrate, key-init, api, worker | `docker inspect` (host root only) | change in the env file and in PostgreSQL (`ALTER ROLE`), then `up -d` |
| S3 access key / secret | operator or storage provider | as above; bundled store gets them from the same file | as above | provider rotation, then `up -d` |
| TRUST-SAT ML-DSA-65 signing key | `key-init` on first start | `/data/keys/satsa_trust_key.json` on the durable volume; file 0600, directory 0700, owned by the non-root service user (10001) | api and worker containers; backups | see "Signing key" |
| Member credentials (`key_id.secret`, 256-bit secret) | `POST /api/v1/members`, bootstrap script | only a salted SHA3-256 digest (`identity_credentials`); the raw value is shown once | the administrator who issued it; the login form | revoke (`DELETE /api/v1/members/{id}` or bearer logout) and re-invite |
| API session tokens | `POST /api/v1/session` | SHA3-256 digest in `satsa_sessions`; raw token in the web tier's HttpOnly `satsa_session` cookie (Secure in production, SameSite=Lax) | browser cookie jar | expire after `SATSA_SESSION_TTL_SECONDS` (8 h); revoked on sign-out |
| CSRF tokens | derived: HMAC-SHA3(session token) | not stored | API cookie clients only | follow the session |
| Caddy ACME account and certificates, local CA | Caddy | `caddy_data` volume | host | automatic |

## Findings

- **No secret in the repository or its history.** `.gitignore` excludes
  `deploy/production.env`, `deploy/*.env` and `.env*` (examples excepted);
  detect-secrets and a history search (Phase 19) found only test fixtures.
  CI generates throwaway secrets per run and masks every issued credential.
- **Credentials and sessions are stored as digests**; a database dump does
  not yield usable credentials or sessions. Credential secrets are 256-bit
  random values, so a fast salted hash is sufficient (no password stretching
  is needed for non-human-chosen secrets).
- **The signing key is the most sensitive item.** It is outside the database
  (a DB-only attacker cannot sign), owner-only on disk, never logged, never
  served. It is in backups by necessity: the backup runbook requires
  encryption and off-host storage (`deploy/README.md` section 7).
- **Environment variables are visible to the host root** (`docker inspect`).
  That is inside the accepted host trust boundary (threat model, residual
  risks). Docker secrets would not change it on a single host.
- **The web tier never sees credentials after sign-in**: the credential is
  exchanged for a session token in one server action and discarded.

### Signing key rotation

Receipts stay verifiable after rotation because each receipt stores the
public key that signed it and the ledger binds its key id. To rotate: stop
api and worker, take a backup (it keeps the old key), move the key file
aside, start `key-init` to provision a new key, start the stack, run
`deploy/smoke.sh`, and record the rotation (date, old and new key ids) in
the operations log. Never delete the old key file from backups.

## Logging leakage audit

What the services log (`satsa/api/__init__.py`, `satsa/analysis/execution.py`,
`satsa/submissions/service.py`, `qsmlops/security/identity/service.py`):

- API: one structured line per response with request ID, organization ID,
  user ID, method, **route template** (not the raw path or query), status,
  duration. Unhandled errors log only the exception type; the client gets a
  generic message and the request ID.
- Worker: run and execution IDs; stack traces for failed stages (these carry
  SQL errors and IDs, never request bodies, credentials or evidence content).
- Validation: version and category on storage/integrity failures.
- Uvicorn access log: method, path, status and client address; credentials
  and tokens never appear in URLs (they travel in headers and cookies).
- Web (Next.js): no application logging of requests, cookies or tokens
  (no `console.*` calls in `web/src`).

Verification: the production-stack CI job collects the logs of every service
after the full workflow, browser E2E, the security smoke and the rate-limit
test, and fails if any issued credential secret, the PostgreSQL password, the
S3 secret, a session cookie value or a bearer header appears.
