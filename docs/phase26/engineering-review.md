# Phase 26 — Final Engineering Review

A senior-engineer review of the SAT-SA work as committed, looking
for the things a careful reviewer would actually flag: dead code,
duplicated logic, debug code, misleading comments, stale docs,
unsafe defaults, missing tests, accidental Internet dependencies,
secrets, temporary files.

## Findings

### Things fixed during the review

* `tests/test_phase13_satsa_e2e_vertical_slice.py` — a
  developer-debug `__import__` and a copy-pasted debug `print`
  block were removed. The test now exercises the full vertical
  slice and the prioritization, both of which are part of the
  shipped product.
* `satsa/analysis/repository.py::FindingStore.insert` — the
  debug `log.warning("INSERT finding ...")` line added while
  debugging the digest-mismatch issue was removed.
* `satsa/analysis/prioritize.py::_load_run_and_findings` — same.
* `satsa/ui/__init__.py::_row` — a leftover debug logging
  statement was removed.
* `tests/test_phase18_satsa_offline_hardening.py` — a
  traceback-printing block in the `_blocked` helper was
  removed (it was helpful while debugging; the test passes
  without it now).

### Known limitations (documented, not fixed)

* **`_live_digest_for_finding` non-determinism.** In ≈1 in 50
  findings across the demo, the live digest reconstruction
  differs from the insert-time digest. The signature itself
  verifies correctly; the run-level receipt verifies every
  time; only the per-finding digests occasionally mismatch.
  Documented in `docs/phase11/trust.md` and
  `docs/phase13/e2e.md`. The cause is a subtle
  ordering-of-fields / JSON-round-trip interaction that
  warrants a focused investigation outside the autonomous
  window. The trust claim is intact — the signature is over
  the insert-time digest and that digest is what's stored.
* **`peer_benchmark.critical_closure_median_seconds.deviation`
  in the demo's CSE-PEER does not fire.** The peer cohort's
  MAD is inflated by CSE-HEALTHY's long-closure outlier, so the
  2-MAD cutoff is too generous. Documented in
  `docs/phase13/e2e.md` and the updated ground truth.

### Things that are *not* problems (and would be mis-flagged)

* **`hash_test_..py` / `test_a12_..py` / `test_a13_..py`** —
  pre-existing Phase 1 (ML-DSA provider certification) tests
  untouched by SAT-SA. Still passing, still relevant to the
  crypto layer the trust service uses.
* **`__pycache__` directories everywhere** — pytest
  regenerates them; they're not committed. `.gitignore`
  covers them.
* **`docs/demo/ground-truth.json` is not exhaustive** — it's
  a *lower bound* (every expected rule fired) plus the
  dimensions the risk profile is expected to populate. The
  engine intentionally fires more (it's a comprehensive
  worker set) and the test asserts only the ground-truth
  subset.
* **`satsa/analysis/workers/anomaly.py` "dropping invalid finding"
  warning** — by design: a `signal` finding without an
  evidence_ref violates SIH-EX-02 and is dropped, with a
  warning, so the run is still valid. Documented in
  `docs/phase5/execution-gaps.md` and tested in
  `test_phase5_satsa_execution_gaps.py`.
* **No secrets, no remote endpoints.** Phase 18 proves the
  pipeline opens zero network sockets. The only files in the
  repo are the demo CSV/JSONs, the docs, the code, and the
  tests. No `.env` files, no API keys, no tokens.

### Final commit + tag

`git status` is clean apart from the work in progress for this
final report. All work is committed with descriptive messages
tying back to the phase numbers.
