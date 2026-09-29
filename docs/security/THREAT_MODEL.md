# SAT-SA hosted system: threat model

Scope: the system as deployed by `deploy/compose.production.yml` on one Linux
host (Phase 19), and the code paths it runs. Each threat names the control
that exists and the test that exercises it. Residual risks are stated, not
hidden. This is the basis for the Phase 20 hardening; it is not a penetration
test report.

## Assets

| Asset | Where | Why it matters |
|---|---|---|
| Tenant evidence (SOC alerts, cases, steps, escalations, dispositions, assets) | object storage, `satsa_version_records` | confidential operational data of each supervised organization |
| Findings, risk, recommendations | PostgreSQL | supervisory conclusions; wrong or leaked results mislead a regulator |
| Supervisory decisions | `satsa_run_review_decisions` | the human authority the system must bind to its results |
| TRUST-SAT records | finalizations, receipts (DB); hash-chained ledger (durable volume) | the integrity claim itself |
| ML-DSA-65 signing key | durable volume `/data/keys` (0600, dir 0700) | anyone holding it can sign supervisory state |
| Credentials, session tokens | salted SHA3 digests (DB); raw only in transit and in the HttpOnly `satsa_session` cookie | account takeover |
| Deployment secrets | `deploy/production.env` (0600, git-ignored), container environment | database, object storage |

## Actors

- **Anonymous internet client**: reaches only Caddy on 80/443.
- **Authenticated member of organization A**: any of five roles.
- **Member of organization B** (including B's administrator): must learn
  nothing about A and change nothing in A.
- **Compromised browser session** (XSS elsewhere, stolen cookie).
- **Host operator** with shell/Docker on the VM: trusted (see residual risks).
- **Database-only attacker** (leaked DB credentials, SQL access without the
  host): can change rows but not the ledger file or the key.

## Trust boundaries and entry points

```
internet --443--> Caddy --(edge net)--> web (Next.js, server-only API client)
                                           |
                                    (backend net, 172.30.0.0/24)
                                           v
                          api:8000 ---- PostgreSQL:5432
                          worker   ---- object storage (HTTPS)
                          api/worker share the durable volume (ledger, key)
```

Only Caddy publishes ports (CI asserts it). The browser never talks to the
API: the web tier holds the session token server-side and calls the API with
`Authorization: Bearer`. The API accepts `Host: api` only, and trusts
`X-Forwarded-For` only from the web tier's fixed address (172.30.0.10).

## Threats, controls, evidence

| # | Threat | Control | Evidence |
|---|---|---|---|
| T1 | Cross-tenant read by ID (IDOR) on any object | every query carries `organization_id`; membership re-checked per request (`TenantRepository._require`) | `tests/test_phase20_tenant_isolation.py` (22 read paths, both engines) |
| T2 | Cross-tenant write: attach A's entity/assessment/version to B, decide/cancel/verify A's run, revoke A's member | ownership checked below the route in the services | same file, 11 mutation paths, row counts of 15 organization-scoped tables unchanged |
| T3 | Forged `X-Organization-ID` | membership required for the named organization; malformed values rejected | `test_forged_organization_header_is_refused_for_every_role` |
| T4 | Enumeration: foreign vs missing IDs distinguishable | identical status and code for both | `test_unknown_and_malformed_identifiers_do_not_leak_existence` |
| T5 | Privilege escalation between roles | route matrix enforced by permission + membership role (decide/cancel) | `tests/test_phase20_authorization.py` (every route x 5 roles), `docs/security/AUTHORIZATION_MATRIX.md` |
| T6 | Stale sessions: logout, expiry, revoked credential, disabled user or identity, revoked membership | session resolution joins user and identity status; credential re-checked; membership per request | `test_revoked_or_expired_sessions_and_disabled_identities_are_rejected`, `test_revoked_membership_is_listed_as_revoked_and_denied` |
| T7 | CSRF against cookie sessions (API) and server actions (web) | API: HMAC CSRF token for cookie mutations; web: SameSite=Lax HttpOnly cookie, Next.js server-action origin check, CSP `form-action 'self'` | `test_cookie_sessions_require_csrf_for_every_mutation`, HTTP smoke |
| T8 | Credential guessing | 5 login attempts/min per client address, identical error for all failures | `test_failed_logins_do_not_distinguish_credential_states`, `web/e2e/security/login-rate-limit.spec.ts` through the proxy |
| T9a | Authenticated request flooding | per-IP cap plus per-user, per-operation caps (30 mutations/min, 300 reads/min by default); limit belongs to the user, not the organization | `tests/test_phase20_rate_limits.py` |
| T9 | Rate-limit bypass by forging `X-Forwarded-For` | Caddy overwrites the header; API trusts it only from the web tier | same E2E, run against the production stack in CI |
| T10 | Malicious upload: traversal names, NUL, wrong type, binary, oversize, parser bombs | filename rules, type/extension agreement, 16 MiB service limit, 17 MiB edge limit, 18 MB proxy limit, opaque storage keys (no filename in the key) | `tests/test_phase20_upload_hardening.py` |
| T11 | Malformed input reaching PostgreSQL (NUL bytes) as a 500 | edge rejects NUL in path/query; schemas reject NUL in strings | `test_nul_bytes_are_rejected_as_input_not_database_failures` (fixed in Phase 20) |
| T12 | Replays and races: duplicate submissions, uploads, runs, validations, decisions; decision vs cancel | idempotency keys scoped per organization; row lock on the run for decide/cancel; atomic claim of a version for validation; a concurrent identical upload replays instead of conflicting | `tests/test_phase20_concurrency.py` (fixed in Phase 20) |
| T13 | Tampering with recorded supervisory state | TRUST-SAT: canonical SHA3-256 digest, ML-DSA-65 receipt, ledger binding (key id, signature digest), DB constraints | `tests/test_phase5_trust_finalization.py`, `tests/test_phase20_trust_adversarial.py` |
| T14 | Premature or partial finalization (worker crash, missing key, cancel) | finalization is resumable at durable boundaries; a supervised run completes only after verification | `test_finalization_recovers_at_durable_boundaries`, `test_missing_signing_key_never_completes_a_supervised_run` |
| T15 | Deleting the finalization to downgrade "inconsistent" to "not finalized" | verify reports a completed supervised run without finalization as inconsistent | `finalization_deleted` case (fixed in Phase 20) |
| T16 | XSS / clickjacking / content injection in the workbench | React escaping, no `dangerouslySetInnerHTML`, CSP, `X-Frame-Options: DENY`, `frame-ancestors 'none'` | HTTP smoke in CI |
| T17 | Sensitive pages cached by browsers or intermediaries | `Cache-Control: no-store` on every non-asset response; API adds it to all responses | HTTP smoke |
| T18 | Internal services exposed | only Caddy publishes; API/PostgreSQL/object store on the backend network only | CI port assertion |
| T19 | Secrets in logs | structured logs carry IDs, route templates and error types, never tokens or bodies | CI log scan for every issued credential, session cookie and deployment secret |
| T20 | Container breakout / persistence | non-root processes, `cap_drop: ALL`, `no-new-privileges`, read-only backend root filesystem | compose file, production-stack CI |
| T21 | Vulnerable dependencies and base images | npm audit, pip-audit, Trivy in CI; Bandit gates HIGH-severity findings in application and deployment code (Medium findings reviewed by hand: request-path SQL is parameterized, the rest are operator-only tools) | `dependency-audit`, `image-scan` jobs; findings and decisions in `docs/security/IMAGE_SCAN.md` |
| T22 | Loss of the host or its disk | executable backup/restore, restore verified in CI | `deploy/backup.sh`, `deploy/restore.sh`, production-stack job |

## Residual risks (accepted, documented)

- **Host root / Docker access is total access**: the operator can read the
  signing key and the environment, and could rewrite the database, ledger and
  key together. TRUST-SAT detects tampering by anyone who lacks the key and
  the ledger volume, not by the host owner. An HSM-held key (the code has a
  PKCS#11 path, `docs/HSM_IMPLEMENTATION.md`) and off-host ledger anchoring
  would narrow this; neither is deployed.
- **Receipts are not pinned to a configured public key.** A key substitution
  is caught through the ledger binding (key id and signature digest), so it
  needs the ledger volume as well as the database; see `attacker_key` in
  `tests/test_phase20_trust_adversarial.py`.
- **CSP allows inline scripts and styles.** Next.js hydration needs them
  unless every page is rendered with per-request nonces; the policy still
  blocks third-party script sources and outbound connections.
- **Any organization administrator can create new organizations**
  (identity-level `identity.manage`). This cannot reach existing tenants'
  data; it is a provisioning choice.
- **Rate limits are per address and fixed-window.** A distributed guesser is
  slowed, not stopped; credentials carry 256-bit secrets, so guessing is not
  a practical attack.
- **Single host**: no high availability; see `docs/security/FAILURE_MODEL.md`.
- **The backend network has outbound internet access** (needed for external
  S3). A compromised API could exfiltrate; egress filtering belongs on the
  host firewall when the storage endpoint is known.
