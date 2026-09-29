# Phase 20 closure record

Phase 20 hardened the hosted SAT-SA system (threat model, authorization,
tenant isolation, uploads, rate limits, concurrency, worker recovery,
TRUST-SAT tampering, secrets, image scanning, HTTP security smoke,
backup/restore). This file records how the phase was verified and closed,
including what could not be established.

## Reconciliation

| Item | Status | Evidence |
|---|---|---|
| 20A CI baseline | PASS | Phase 19 HEAD `2f47314`: run 36448905143 green |
| 20B Threat model | PASS | `THREAT_MODEL.md`, each threat mapped to a control and a test |
| 20C Auth/session | PASS | revoked/expired sessions, cookie CSRF, logout, disabled identities: `test_phase6_api.py`, `test_phase63_satsa_auth_rbac.py`, `test_phase20_authorization.py` |
| 20D Tenant isolation | PASS | `test_phase20_tenant_isolation.py` (per object path, A-vs-B) |
| 20E Authorization matrix | PASS | `AUTHORIZATION_MATRIX.md`; `test_phase20_authorization.py` fails if a route has no matrix entry |
| 20F Upload hardening | PASS | `test_phase20_upload_hardening.py`; edge limits exercised in the `production-stack` CI job |
| 20G Rate limiting | PASS | login + forged `X-Forwarded-For` (`test_phase6_api.py`, `web/e2e/security/login-rate-limit.spec.ts` through Caddy); per-user mutation cap (`test_phase20_rate_limits.py`) |
| 20H Idempotency/concurrency | PASS | `test_phase20_concurrency.py` (two interleavings run on PostgreSQL only) |
| 20I Worker recovery | PASS | lease/retry-exhaustion/cancellation tests in `test_phase3_analysis_execution.py`, `test_phase4_langgraph.py`, `test_phase5_trust_finalization.py`; `FAILURE_MODEL.md` |
| 20J TRUST-SAT tampering | PASS | `test_phase20_trust_adversarial.py`, `test_phase66_satsa_tamper_matrix.py` (36 cases) |
| 20K Secrets | PASS | pattern scan of tracked files, history and built web bundle: no hits; `test_phase20_secret_hygiene.py` |
| 20L Image scan | PASS | Trivy in CI; every HIGH/CRITICAL classified in `IMAGE_SCAN.md` |
| 20M HTTP security smoke | PASS (limited) | `deploy/http_security_check.py` against the CI HTTPS stack; a smoke check, not a penetration test |
| 20N Dependencies | PASS | npm audit 0, pip-audit 0 (CI `dependency-audit`) |
| 20O Headers/proxy | PASS | `deploy/caddy/site.caddy`; asserted by the HTTP security check in CI |
| 20P Logging | PASS | CI scans service logs for every issued credential and deployment secret |
| 20Q Backup/restore | PASS (CI) | `deploy/backup.sh`, `deploy/restore.sh`, `scripts/verify_restored_state.py`, run in the `production-stack` job |
| 20R Single-VM failure | PASS | `FAILURE_MODEL.md` |
| 20S Regression | PASS | see below |
| 20T Paper integrity | PASS | no `paper/` or `research/` file changed by Phase 20 commits |
| 20U Scope | PASS | no `nosec`, `xfail`, `continue-on-error`, `.trivyignore` or disabled test added |

## Regression

- Local, SQLite: 1638 collected, 1568 passed, 70 skipped (all PostgreSQL-only), 0 failed.
- Local, PostgreSQL 17: 1638 collected, 1619 passed, 19 skipped, 0 failed.
- CI: three consecutive green runs, 10/10 jobs each, on an unchanged tree:
  36529105868 (`d952213`), 36533223455 (`2c463ec`), 36534035127 (`94867e7`).

## Historical CI failures: unclassified, not reproduced

Two CI runs failed during Phase 20 and their cause is **not known**.

| Run | Commit | Job | Step | Step duration |
|---|---|---|---|---|
| 36520211487 | `d8ef6c7` | test (py3.13) | Full test suite | 7m47s |
| 36520964908 | `ad8493d` | test (py3.11) | Full test suite | 9m53s |

What is known:

- Only the "Full test suite" step failed; the other Python version and all
  other jobs passed in the same runs.
- The step ran for the length of a full suite (passing runs: 4m30s to 7m41s),
  so it was not a collection/import failure. The py3.11 run was 2 to 3 minutes
  slower than usual.
- The failing test id and traceback were not retrieved: job logs require an
  authenticated GitHub session, which was not available, and credentials were
  deliberately not extracted from local stores. The public check annotations
  contain only "Process completed with exit code 1."
- `d8ef6c7` was the first run to include `test_phase20_rate_limits.py`. Its
  clock was pinned in `ad8493d`, which still failed, so that test is not
  established as the cause.

What was done to try to reproduce it:

- Full suite locally against PostgreSQL 17: 0 failures.
- The Phase 20, API and TRUST-SAT finalization test files repeated
  against PostgreSQL 17: 3 iterations, each 276 passed, 2 skipped (SQLite-only interleavings), 0 failed, pytest exit 0.
- Eight later CI runs green, three of them consecutive on an unchanged tree.

No test was disabled, skipped or marked xfail, and no CI step was made
non-blocking in response. To make a recurrence diagnosable, the CI test step
now emits failing pytest ids as public annotations (`4e15d9c`).

Classification: **unclassified / not reproduced.** It is not called flaky,
because there is no evidence of what failed. If it recurs, the annotation
will name the test.
