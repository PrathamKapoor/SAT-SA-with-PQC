# SAT-SA Phase 2 — Independent verification record

This file is the evidence trail of a **second, independent verification pass** over the
completed Phase 2 working tree (a different session from the one that implemented it).
Nothing here re-states Phase 2's own claims as its own; every entry below was reproduced
by direct execution or source inspection during this pass. Where a claim could not be
reproduced or was found inaccurate, it is called out explicitly, with the correction made.

## Method

1. `git status` / `git diff` / `git log` — confirm the working tree contains exactly the
   17 modified tracked files and the intentional untracked additions this document set
   describes, at commit `5995f0d`, with no other drift.
2. Full test suite executed in an isolated scratch copy of the working tree
   (`robocopy` clone excluding `.git`, `.devtools`, caches), protecting the tracked HSM
   certification sentinel files exactly as [baseline.md](baseline.md) prescribes.
3. Live, direct reproduction of the flagship fixes (crypto suite resolution, identity
   authentication, migration schema) in a Python REPL against the real packages — not
   only via the pytest suite that embeds them.
4. Source-level re-read of every modified module, all six new test files, and the entire
   `satsa/` package, compared claim-by-claim against every document in `docs/phase2/`.

## Reproduced results

| Claim (source document) | Independent result |
|---|---|
| 539 collected, 0 failed, 0 errors, 17 skipped ([testing-report.md](testing-report.md)) | **Confirmed**: 539 / 0 / 0 / 17, 263.0 s, full suite in scratch copy with Git's `grep` on PATH (junit retained). A first run without `grep` on PATH produced exactly 1 failure — `test_phase10_adaptive_supervisor.py::...::test_boundary_still_clean_after_phase10`, `FileNotFoundError` spawning `grep` — the pre-existing portability defect [baseline.md](baseline.md) already documents; the same single test passes when `grep` is reachable. Baseline behavior precisely as documented. |
| 70 new tests across 6 files ([testing-report.md](testing-report.md)) | **Confirmed**: 8 + 14 + 9 + 9 + 23 + 7 = 70, all pass when the six files are run alone. |
| All three environment profiles run the configured suite ML-DSA-65 + ML-KEM-768 ([crypto-hardening.md](crypto-hardening.md)) | **Confirmed by direct execution**: `ServiceContainer(load_settings(env))` built for `development`/`testing`/`production`; `pipeline.agility.effective_policy()` reports `source: "configured"`, ML-DSA-65 + ML-KEM-768 in all three; `IdentityService` holds the pipeline's engine instance (`is` identity) in all three. |
| No-config `AgilityEngine()` behavior is unchanged ([crypto-hardening.md](crypto-hardening.md)) | **Confirmed**: auto-selects ML-DSA-87 + ML-KEM-1024, `source: "auto-selected-strongest"`. |
| Partial/unknown configuration fails closed ([crypto-hardening.md](crypto-hardening.md)) | **Confirmed**: one-of-two supplied raises `ProviderError` ("must be configured together"); `ML-DSA-99` raises `ProviderError` naming the unknown algorithm; an explicit weaker pair (ML-DSA-44 + ML-KEM-512) resolves correctly, proving the mechanism honors configuration rather than forcing the strongest. |
| Migrations 3/4 add `identity_credentials` and `content_digest` columns ([evidence-persistence.md](evidence-persistence.md), [identity-security.md](identity-security.md)) | **Confirmed**: fresh database applies `001..004`; `identity_credentials` carries `identity_id/key_id/key_hash/salt/created_at/revoked_at`; all four evidence tables carry `content_digest`. (Script used for this check leaked its temp-file handle on cleanup — a property of the throwaway check script, not of repository code; no repository change resulted.) |
| Zero network-capable imports in `qsmlops/` runtime ([offline-hardening.md](offline-hardening.md)) | **Confirmed**: pattern scan for `requests./urllib/http.client/socket./aiohttp/httpx/boto3/azure/google.cloud/...` across all `qsmlops/**/*.py` returns nothing. |
| `Finding` gained a stable `finding_id` that round-trips ([evidence-persistence.md](evidence-persistence.md)) | **Confirmed** in source: `qsmlops/agents/base.py` `to_dict()`/`from_dict()` round-trip it; `from_dict()` mints a fresh one only when absent; covered by `tests/test_phase2_evidence_persistence.py`. |
| `pyproject.toml` discovers `satsa`, `starlette` declared directly | **Confirmed** in diff: `include = ["qsmlops*", "satsa*"]`; `starlette>=0.36` added to both `pyproject.toml` and `requirements.txt`. |
| `test_phase2_platform.py` (file present, not in the six new files) | **Explained, not a discrepancy**: a *tracked* historical file from commit `6c14786` of the original project's own phase history — its name collides with this phase's naming convention. Not Phase 2 work, not modified by it. |

## Discrepancy found and corrected in this pass

`satsa/errors.py::DomainValidationError` carried a docstring claiming it is "raised by
`validate()`" — contradicting the deliberately implemented and tested contract that
`validate()` **returns a list and never raises** (documented in
[domain-foundation.md](domain-foundation.md) and `satsa/domain/base.py`). The error class
itself is a legitimate foundation for future ingestion/persistence boundaries that *must*
reject invalid records; only the docstring was wrong. Corrected in place (comment text
only); `tests/test_phase2_satsa_domain.py` + `tests/test_phase2_satsa_orchestration.py`
(30 tests) re-run afterward: all pass.

## Git state at the end of this pass

Identical to the state [phase2-final-report.md](phase2-final-report.md) §3 tabulates,
plus the one docstring correction above: 17 modified tracked files, untracked
`docs/phase1/`, `docs/phase2/`, `satsa/`, `qsmlops/database/evidence_store.py`,
`qsmlops/security/identity/auth.py`, six `tests/test_phase2_*.py`. The tracked HSM
sentinel files (`tests/_a12_artifacts/`, `tests/_a13_artifacts/`) show an empty diff —
no full-suite run was executed against the tracked tree. No secrets, debug artifacts, or
journal files found in any new or modified file (scanned). Nothing committed; nothing
pushed; Phase 1 documentation untouched.
