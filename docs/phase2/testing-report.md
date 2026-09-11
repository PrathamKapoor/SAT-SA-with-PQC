# SAT-SA Phase 2 — Testing report (Part O), error handling (Part M), observability (Part N)

## Test suite growth, by file, with what each closes

| File | Tests | Closes |
|---|---|---|
| `tests/test_phase2_crypto_config.py` | 8 | Part B/C — crypto suite configuration mismatch |
| `tests/test_phase2_identity_auth.py` | 14 | Part D — actor/approver authentication foundation |
| `tests/test_phase2_evidence_persistence.py` | 9 | Part E — observation/finding/decision/provenance persistence |
| `tests/test_phase2_offline_hardening.py` | 9 | Part F/G — network dependency audit, host/trusted-origin config |
| `tests/test_phase2_satsa_domain.py` | 23 | Part H/I — domain records and their validation rules |
| `tests/test_phase2_satsa_orchestration.py` | 7 | Part K — worker/orchestration skeleton |
| **New total** | **70** | |

Existing suite: 469 collected / 452 passed / 0 failed / 17 skipped at Phase 2's start ([baseline.md](baseline.md)). With the 70 new tests plus one updated test (`test_foundation.py::test_identity_endpoint_lifecycle`, changed with an inline comment explaining why — Part O's explicit procedure for a test whose behavior intentionally changes), the full suite is **539 collected**. Every regression checkpoint through this phase (after crypto hardening, after identity auth, after evidence persistence, after offline/host hardening, after the satsa package) was run to completion in the isolated scratch copy with **0 failures, 0 errors, 17 skipped** at every checkpoint — the 17 skips are the same SoftHSM2-hardware-absent skips present at baseline, unchanged by anything in this phase.

No existing test was deleted. No existing test's assertion was weakened to make it pass — where a test's premise changed (the one case: identity creation now requires authentication), the implementation changed first, then the test was updated to match the new real contract, with the reason documented inline in the test itself.

## Coverage against Part O's checklist

- **Crypto**: configuration, signing/selection (suite resolution), invalid configuration (fail-closed), algorithm mismatch (end-to-end settings-to-runtime agreement) — all in `test_phase2_crypto_config.py`. Tampered-payload/wrong-key signature tests already existed pre-Phase-2 in `test_crypto.py`/`test_foundation.py` and were not duplicated.
- **Identity**: actor validation, approver validation (via the ownership-mismatch check), authorization boundaries — `test_phase2_identity_auth.py`.
- **Persistence**: observations, findings, decisions, provenance, transactions (including a real rollback-on-partial-failure test) — `test_phase2_evidence_persistence.py`.
- **Data contracts**: valid records, missing data, malformed data, invalid relationships — `test_phase2_satsa_domain.py` (each domain record's positive and negative validation cases).
- **Offline**: no unexpected external dependency — `test_phase2_offline_hardening.py`, both by source trace and by active socket-connection trapping during real execution.
- **Configuration**: invalid configuration, safe defaults, host configuration — split across `test_phase2_crypto_config.py` (crypto) and `test_phase2_offline_hardening.py` (host/trusted-hosts/docs).
- **Regression**: the full existing suite, unmodified in behavior except the one documented case, verified green at every checkpoint.

## Part M — error handling, audited across this phase's own new code

Every new module raises a specific, typed error rather than letting a generic exception surface or silently swallowing a failure:

- **Malformed/invalid crypto configuration**: `AgilityEngine` raises `ProviderError` with the specific unknown algorithm named, or naming the "must be configured together" inconsistency ([crypto-hardening.md](crypto-hardening.md)).
- **Invalid identity/credential**: `IdentityService.authenticate()` raises `AuthenticationError` uniformly for every failure mode (unknown key_id, hash mismatch, revoked, inactive) — deliberately not distinguishing them in the exception, so a caller cannot use exception type to enumerate valid credentials ([identity-security.md](identity-security.md)).
- **Database/foreign-key failures**: verified directly (not merely inspected) that inserting a credential row referencing a nonexistent identity raises `qsmlops.core.errors.StorageError` naming the failing statement — the existing `SQLiteDatabaseEngine._translate` path already handles this (it special-cases `UNIQUE` violations into `DuplicateEntryError` and falls through to `StorageError` for other integrity errors, including foreign-key violations); no new error-translation code was needed, only confirmed by direct execution.
- **Missing evidence / invalid references**: `EvidenceStore` read methods (`get_observation`, `get_findings_for_observation`, `get_decision`) return `None`/`[]` for an unknown ID rather than raising — tested explicitly (`test_missing_observation_returns_none_not_error`), since a missing reference during read is an expected, common case (not yet linked, not an application bug), while a missing reference during a *write* that declares a foreign key (identity_credentials -> identities) correctly does raise.
- **Interrupted analysis**: `Orchestrator.run()` isolates a crashing worker into a `failed` Job with the exception captured as `error`, never propagating to abort the whole run or corrupt another worker's Job ([orchestration-foundation.md](orchestration-foundation.md)).
- **Partial transactions**: `DatabaseEngine.transaction()` rolls back every statement in the block on any exception, verified by a test that forces a `finding_id` collision partway through a multi-row `persist_observation()` call and confirms *nothing* from that attempt persisted, not even the row that would have succeeded alone ([evidence-persistence.md](evidence-persistence.md)).
- **Duplicate submission-equivalents**: `IdentityRepository.insert`/`ObservationRepository.insert`/`FindingRepository.insert` all raise on a primary-key/unique collision (`DuplicateEntryError`), tested directly for observations; `ProvenanceEdgeRepository.insert` is the one deliberate exception — it treats a duplicate edge as an idempotent no-op by design, since re-asserting the same provenance fact during reprocessing is expected, not an error (documented and tested).

## Part N — observability

New structured log events introduced this phase, all following the existing `qsmlops.core.logging` field convention (`event`, `service`, `actor`, `resource`): `api.non_loopback_bind` (Part G, warns with host/port when the API binds beyond loopback), and the existing `identity.credential.issued`/`identity.credential.revoked` audit events (via `AuditService`, the same mechanism every other identity lifecycle change already uses — no new logging mechanism was invented for these). No secret, key, passphrase, or raw credential value is ever passed to a logger anywhere in this phase's new code — verified by direct review of every `log.*`/`AuditEvent` call site added.

## What Part O explicitly says not to do, and this report does not do

No fabricated pass/fail numbers: every count above was produced by an actual `pytest` run against the actual current source, in the isolated scratch copy, with the JUnit XML retained (`phase2-after-*.xml` files, session-local, not release artifacts — same convention [technology-baseline.md](../phase1/technology-baseline.md) used). No test was deleted to make a red run look green.
