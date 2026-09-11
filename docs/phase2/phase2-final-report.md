# SAT-SA Phase 2 — Final report

Repository: `TRUST-SAT`. Started and ended at commit `5995f0dab48819bd6fb2588cf4cc55c86861bf91` (Phase 2 does not commit; every change below is unstaged in the working tree, per Rule/Part T — "do NOT commit unless explicitly instructed"). Full before/after test evidence in [baseline.md](baseline.md) and [testing-report.md](testing-report.md).

## 1. Executive summary

Phase 2 hardened the foundation Phase 1 audited, without touching final analytics, UI, or demo mode. Six concrete defects were fixed with regression tests proving both the fix and its absence beforehand: a cryptographic suite that silently ignored its own configuration; an API route that let any unauthenticated caller mint a privileged identity; four database tables with no application behind them; a FastAPI default that phones home to a CDN; an unbounded Host-header surface; and a database engine with no multi-statement transaction guarantee. A new `satsa` package establishes validated domain types and a worker/orchestration contract for later analytics phases to build on — nothing in it performs analysis. 70 new tests were added across six files; the existing 469-test suite's behavior was preserved except one test whose premise intentionally changed (documented inline, per Part O). Every regression checkpoint through this phase ran clean: **539 collected, 0 failed, 0 errors, 17 skipped** (the 17 are the same SoftHSM2-hardware-absent skips present before Phase 2 began).

## 2. Baseline

Commit unchanged from Phase 1's audit. Working tree clean except Phase 1's own untracked `docs/phase1/`, left untouched throughout. Baseline test run (isolated scratch copy, to protect the tracked HSM certification sentinel files — see below): 469 collected, 452 passed, 0 failed, 17 skipped. Full detail, including the one environment-dependent test-result difference from Phase 1's own report (a `grep`-availability difference between PowerShell and Git Bash, not a code change) in [baseline.md](baseline.md).

**Process note, disclosed rather than hidden**: an early full-suite run in this phase was executed directly in the tracked repository rather than the isolated copy, and silently overwrote two tracked HSM certification evidence files (`tests/_a12_artifacts/real_provider_sentinel.txt`, `tests/_a13_artifacts/mldsa_provider_sentinel.txt`) with degraded results (no SoftHSM2 DLL in this checkout). Caught immediately via `git status`, reverted with `git checkout --`, and every subsequent full-suite run went through the isolated scratch copy. No other tracked file was affected at any point (verified by `git status` after every checkpoint).

## 3. Changes (every meaningful modification)

| File | Change | Reason |
|---|---|---|
| `qsmlops/crypto/agility.py` | `AgilityEngine` accepts optional configured suite; fails closed on inconsistent/unknown config; `effective_policy()` introspection | Part B/C |
| `qsmlops/config.py` | `PlatformConfig` gains optional `default_signature_algorithm`/`default_kem_algorithm` | wiring for the above |
| `qsmlops/pipeline/selfheal.py` | forwards config into `AgilityEngine` | wiring |
| `qsmlops/core/context.py` | `ServiceContainer` forwards `settings.crypto.*` into `PlatformConfig`; `IdentityService` shares the pipeline's engine instance; registers `evidence_store` | wiring (Part B/C, Part E) |
| `qsmlops/api/app.py` | `/security` exposes `crypto_policy` (additive) | Part C2 |
| `qsmlops/core/errors.py` | adds `AuthenticationError` | Part D |
| `qsmlops/security/identity/auth.py` (new) | credential generation/verification, `AuthenticatedPrincipal` | Part D |
| `qsmlops/security/identity/service.py` | `issue_credential`/`revoke_credential`/`authenticate`; accepts a shared `AgilityEngine` | Part D |
| `qsmlops/database/migrations.py` | migration 3 (`identity_credentials` table), migration 4 (`content_digest` columns) | Part D, Part E |
| `qsmlops/database/repositories.py` | `IdentityCredentialRepository`, `ObservationRepository`, `FindingRepository`, `SupervisorDecisionRepository`, `ProvenanceEdgeRepository` | Part D, Part E |
| `qsmlops/api/foundation.py` | `POST /identity` requires authentication after bootstrap; new `POST /identity/{id}/credential` | Part D |
| `qsmlops/agents/base.py` | `Finding` gains a stable `finding_id` | Part E (needed for provenance edges) |
| `qsmlops/database/engine.py` | `RLock` (was `Lock`); new `transaction()` context manager | Part E (atomicity) |
| `qsmlops/database/evidence_store.py` (new) | `EvidenceStore`: persist/read/verify observations, findings, decisions, provenance | Part E |
| `qsmlops/app.py` | disables `/docs`+`/redoc` by default in production; adds `TrustedHostMiddleware`; warns on non-loopback bind | Part F, Part G |
| `qsmlops/core/settings.py` | `ApiSettings.trusted_hosts` (default `["*"]`, no behavior change) | Part G |
| `pyproject.toml`, `requirements.txt` | add `satsa*` to package discovery; declare `starlette` as a direct dependency (it is now directly imported, not only transitively via FastAPI) | Part H, hygiene |
| `satsa/` (new package: `errors.py`, `domain/*.py`, `contracts/*.py`) | domain records + worker/orchestration contract | Part H/I/J/K |
| `tests/test_foundation.py` | one test updated (bootstraps as admin, authenticates subsequent calls) with inline reason | Part D, Part O |
| `tests/test_phase2_*.py` (6 new files, 70 tests) | regression coverage for every change above | Part O |

## 4. Cryptographic trust

Verified precisely: the running suite was ML-DSA-87+ML-KEM-1024 (auto-selected strongest) while every declared config source said ML-DSA-65+ML-KEM-768 — traced to `ServiceContainer._platform_config()` forwarding only `settings.home`, never the crypto section, into `PlatformConfig`, and `AgilityEngine()` being constructed with zero arguments everywhere. Fixed by making the configured suite authoritative when supplied, fail-closed on partial/unknown configuration, and unchanged (auto-select-strongest) when not supplied — preserving every existing call site's behavior. A parametrized end-to-end test across all three environment profiles now asserts the running pipeline's effective policy equals the declared settings; before the fix this assertion would have failed for all three. QT-01..06 (keystore lifecycle defects from Phase 1's audit) remain untouched — explicitly out of this phase's scope, tracked as GAP-09. Full detail: [crypto-hardening.md](crypto-hardening.md).

## 5. Identity

Two distinct instances of "unauthenticated actor claim" were found: the legacy dashboard's `actor`/`approver` request-body fields (Phase 1's original finding, re-confirmed), and — found fresh during this phase's own re-verification — `POST /identity` accepting an unauthenticated `role` field including `"admin"`. The second, more severe issue was fixed: a local API-key credential mechanism (salted-hash storage, constant-time comparison, rotation invalidates the prior credential) now gates identity creation after a documented first-run bootstrap exception, with ownership-based authorization reusing the existing role vocabulary (no new roles invented). The first issue (legacy dashboard) was deliberately not retrofitted — traced concretely to a standalone `create_app(pipeline)` with no identity service wired in at all, and fixing it would mean restructuring an entry point Phase 1's own target-architecture explicitly recommended preserving as a separate legacy bounded context. This is disclosed, not hidden — see the security review below. Full detail: [identity-security.md](identity-security.md).

## 6. Evidence persistence

`observations`, `findings`, `supervisor_decisions`, `provenance_edges` were migrated, indexed tables with zero repository or insert path — confirmed by grep, not assumed from Phase 1's write-up. Four new repositories and an `EvidenceStore` service close this, tested against **real** pipeline-produced `Observation`/`Finding`/`DecisionReport` objects (a real model is trained, evaluated by the actual nine agents, and its actual supervisor decision is persisted and linked) — not hand-built fixtures. Building this surfaced that the database engine had no multi-statement transaction support at all (`execute()` auto-commits every statement independently); added `DatabaseEngine.transaction()`, which required switching the engine's lock to `RLock` to avoid a deadlock on nested `execute()` calls. Verified by a test that forces a mid-write failure and confirms nothing partial persisted. Content digests provide tamper *detection* for these rows (verified: an out-of-band `UPDATE` is caught); this is explicitly not cryptographic signing or ledger commitment, which remain later-phase work (SAT-TR-03). Full detail: [evidence-persistence.md](evidence-persistence.md).

## 7. Offline readiness

Traced (not grepped-only) for network dependencies in `qsmlops/`: zero HTTP/cloud-SDK/socket imports, zero hardcoded URLs, zero raw subprocess/socket calls. Found one real, previously-undocumented issue: FastAPI's default `/docs`/`/redoc` pages load JS/CSS from a public CDN — now disabled by default in production. The SoftHSM2 bootstrap script's internet dependency (already known from Phase 1) was confirmed to be a dev-only tool with no runtime code path into the application, and a test now guards against that boundary silently eroding in the future. An active socket-connection trap proves container boot and a representative API call sequence make zero outbound connections — this is demonstrated by execution, not only inferred from absence of a grep match. Full detail: [offline-hardening.md](offline-hardening.md).

## 8. Domain foundation

`satsa/domain/` implements all fifteen concepts Part H named (Entity, Assessment, Submission, Alert, Case, InvestigationStep, Escalation, Disposition, Asset, SourceRecord, Observation, Finding, ReviewDecision, ProvenanceRecord, AnalysisRun) as validated dataclasses, following field lists already justified in Phase 1's data-architecture.md — no field was invented without that justification. Validation enforces the specific missing-data semantics Phase 1 called out by name (e.g. `Alert.acknowledged_at is None` is not zero duration; a `signal`-state `Finding` must cite evidence and a confidence vector, or it is invalid — SIH-EX-02 as a checked rule, not only documentation). No ingestion parsing, no persistence, no detector reads these yet — deliberately, per Rule 3. Full detail: [domain-foundation.md](domain-foundation.md), [data-contracts.md](data-contracts.md).

## 9. Orchestration

`satsa/contracts/` implements the worker contract exactly as Phase 1's agent-architecture.md specified it (`evaluate(snapshot, baselines, policy, run_context) -> ObservationBatch`) and a plain in-process `Orchestrator` that isolates a crashing or invalid-output worker into a `failed` Job without aborting the run or fabricating a result. `EchoWorker`/`CrashingWorker` are trivial test doubles that exist only to prove this plumbing executes end to end — no real detector exists yet. A future analytics phase implements `AnalyticalWorker` subclasses and, separately, persists `Job`/`ObservationBatch` reusing the transactional pattern Part E already proved. Full detail: [orchestration-foundation.md](orchestration-foundation.md).

## 10. Tests

70 new tests across 6 files (exact breakdown in [testing-report.md](testing-report.md)); 1 existing test updated with an inline documented reason; 0 existing tests deleted or weakened. Full suite: 539 collected, 0 failed, 0 errors, 17 skipped, at every regression checkpoint through this phase, executed in an isolated scratch copy to protect tracked HSM sentinel evidence. Every claim in this document set was subsequently re-verified by an independent execution pass (full suite re-run, live REPL reproduction of the crypto/identity/migration behavior, source re-read of every change) — exact reproduced numbers and the one discrepancy found and corrected are recorded in [verification.md](verification.md).

## 11. Security review (Part R)

| Area | Finding |
|---|---|
| Cryptographic algorithm selection | Fixed (Part B/C). QT-01..06 lifecycle defects remain, unaddressed, tracked (GAP-09). |
| Key handling | Unchanged from Phase 1 — plaintext staging file during keystore generation, retained passphrase after lock, both still present (QT-01/QT-02). |
| Actor identity | `POST /identity` fixed. Legacy dashboard `actor`/`approver` fields remain unauthenticated — disclosed above and in identity-security.md, not fixed (deliberate scope boundary, not an oversight). |
| Authorization | Wired for identity creation using the existing permission model; not extended anywhere else. |
| Persistence | Digest-based tamper detection added; not cryptographically signed. |
| Provenance | Edges recorded in-process (qsmlops) and as a domain concept (satsa); neither is ledger-committed yet. |
| Input validation | Domain records validate their own fields; no real ingestion parser exists yet to validate actual submitted files (later phase). |
| External network dependencies | Audited and actively tested; one real issue (docs CDN) found and fixed. |
| Host binding | `TrustedHostMiddleware` available (opt-in, default unchanged); non-loopback bind now logged. |
| Logging | Reviewed: no secret/key/passphrase/credential value is logged anywhere in this phase's new code. |
| Sensitive data exposure | Credential tokens shown exactly once, never logged, never returned again. `GET /identity`/`GET /audit` remain open to any network caller — not addressed (lower severity, disclosed). |
| Dependency configuration | `starlette` now declared as a direct dependency, matching its direct import — was previously an undeclared transitive dependency. |

No security issue found during this review was hidden or downplayed; several (legacy dashboard auth, plaintext keystore staging, open read routes) are explicitly carried forward as unresolved, with the reasoning for not fixing them in this phase stated plainly above and in the referenced docs.

## 12. Phase 3 readiness

Phase 3 can now build directly on: a crypto layer whose configured suite is the one that actually runs; an identity/credential mechanism a future review-decision API can require without inventing auth from scratch; a proven, transactional persistence path for observations/findings/decisions/provenance (for the qsmlops side; the same pattern applies directly to satsa's own records); validated SAT-SA domain types with no known gaps against Phase 1's canonical model; and a working worker/orchestration contract ready for real `AnalyticalWorker` implementations (execution-gap and negative-space detectors, per [gap-analysis.md](../phase1/gap-analysis.md) GAP-02/GAP-03) to plug into without any orchestration-layer redesign. Ingestion parsing (turning an actual CSV/JSONL submission into validated `satsa.domain` records) is the one piece not yet started that the first real detector will need — it is the natural next step, not a surprise, since Part H/I always scoped it as later-phase work.

## Remaining limitations (stated honestly)

Legacy dashboard `actor`/`approver` fields remain unauthenticated. `GET /identity`/`GET /audit` remain open to any network-reachable caller. QT-01..06 keystore lifecycle defects remain exactly as Phase 1 found them. No cryptographic signing or ledger commitment exists for any of the new persisted/domain records — only digest-based tamper detection. No ingestion adapter exists to populate `satsa.domain` records from a real file. No real `AnalyticalWorker` exists. These are not oversights; each is named in the part of this document set that scoped it as later-phase work, and none was silently dropped.

## STOP

Phase 2 is complete as of this report. Per the master brief's explicit instruction, this does not continue into execution-gap analytics, negative-space analytics, anomaly detection, peer benchmarking, risk scoring, UI, or demo mode. Those remain Phase 3+.
