# SAT-SA Phase 2 — Baseline verification

## Git state (start of Phase 2)

- Branch: `main`, up to date with `origin/main`.
- Commit: `5995f0dab48819bd6fb2588cf4cc55c86861bf91` — identical to the commit Phase 1 audited; the repository had not changed between phases except for Phase 1's own untracked `docs/phase1/` files, which were left untouched.
- Working tree: clean except `docs/phase1/` (untracked, intentional, preserved).

## Baseline test run

Command: `python -m pytest tests -q -ra --junitxml=...`, run in an isolated scratch copy (not the tracked repo) to avoid rewriting the two tracked HSM certification sentinel files (`tests/_a12_artifacts/real_provider_sentinel.txt`, `tests/_a13_artifacts/mldsa_provider_sentinel.txt`) — Phase 1 used the same precaution for the same reason, and a first attempt at a full-suite run directly in the tracked repo during this phase confirmed why: it silently rewrote both sentinel files with degraded results (no `.devtools/softhsm2` DLL in this checkout), which were reverted with `git checkout --`.

Result: **469 collected, 452 passed, 0 failed, 0 errors, 17 skipped, 230.322s.**

This differs from Phase 1's reported 451 passed / 1 failed. The one difference is `tests/test_phase10_adaptive_supervisor.py::TestDeterminismAndQuiet::test_boundary_still_clean_after_phase10`, which shells out to `grep` via `subprocess.run(["grep", ...])`. Phase 1 ran under a shell without `grep` on PATH (PowerShell); this phase's Bash tool is Git Bash, which bundles `/usr/bin/grep`. Read directly: the test does a source-tree scan for a stray string (`"guardrailed"`) left over from a historical refactor, unrelated to any Phase 2 concern. This is a **pre-existing test-portability defect** (the test never checks `subprocess` exit status, so a missing `grep` raises `FileNotFoundError` loudly in one shell and simply runs in another) — not a repository regression, and not something Phase 2's mandate (crypto/identity/persistence/offline/domain/orchestration) covers. It is documented here, left unmodified, and not counted as a Phase 2 defect.

The 17 skips are unchanged from Phase 1: SoftHSM2/PKCS#11 hardware not present in this checkout (`.devtools/softhsm2/lib/*.dll` absent).

## Type checking / lint / build

No `mypy`, `ruff`, or `flake8` installed in this environment (`pip show` returns nothing for all three); no `pyproject.toml` `[tool.mypy]`/`[tool.ruff]` section exists; no CI configuration exists anywhere in the tree (confirmed in Phase 1). There is no type-check or lint command to run — this is a genuine tooling gap, not a result being omitted. `python -m py_compile` is not a substitute for real type checking and was not used to manufacture a false "type check passed" signal. There is no separate build step: the package is pure Python, installed via `pip install -e .`; `python -m pytest` succeeding against the installed package is the closest available build-verification signal, and it passed (above).

## Environment

Python 3.13.14 (Windows Store distribution), same machine as Phase 1. `pytest` 9.1.1. Package versions unchanged from [Phase 1's technology-baseline.md](../phase1/technology-baseline.md) table — no dependency was installed, upgraded, or removed during this baseline check.

## Known failures / caveats carried into Phase 2

- The `grep`-dependent test above is shell-dependent, not fixed (out of scope; noted for a future portability pass).
- SoftHSM2/PKCS#11 hardware path remains untested in this environment (unchanged from Phase 1; addressed at the level of "what is required to test it" in [offline-hardening.md](offline-hardening.md), not by installing hardware here).
