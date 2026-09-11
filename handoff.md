# Project Handoff

## 1. Current Phase

- **Phase**: P26 (agent-taxonomy expansion + hardening checklist) → P27
  (public-dataset benchmark framework) → P28 (release integrity, offline
  package verification, dependency-manifest reconciliation) → P29
  (deployment verification and packaging correction).
- **Subphase**: release-publishing correction. The P29 commit is on
  GitHub; this handoff records the subsequently discovered CI setup defect
  and its correction.
- **Overall project objective**: SAT-SA — a periodic, offline,
  evidence-driven supervisory analytics tool for SIH 26157 / NCIIPC, with a
  post-quantum trust layer (TRUST-SAT). See `README.md` for the full
  product description.
- **Status**: **COMPLETE for everything scoped through P28.** The full test
  suite passes (`python -m pytest tests/ -q`, exit 0), the current HEAD is
  pushed to GitHub and independently verified there (not just trusted from
  a push exit code), and a wheel built from this tree has been proven —
  twice, across two sessions — to contain everything an installed
  distribution needs, including the `sat-sa` CLI working end to end from
  outside the source tree. Explicitly **NOT** complete, and not claimed
  complete anywhere in the repo: real BOTS/CIC-IDS2017 file execution, real
  NCIIPC/SOC expert validation and fully dependency-isolated installation
  on a separate target machine — see section 8/9. CI has been executed and
  failed; Docker could not be executed because this host has no Docker
  executable or daemon.

## 2. Work Completed

### A. P26/P27 feature work (agent expansion + public-benchmark framework)

- **Agent roster** grew 26 → 31 → 32 (9 MLOps + 23 SAT-SA). Additions:
  Entity & Asset Resolution, Workflow Reconstruction, Evidence &
  Explainability Assembly, Meta-Audit, formal registration of Report
  Generation, Correlation & Signal Fusion (split from Entity Risk Scoring),
  N17 calibration workflow. See `docs/AGENT_INVENTORY.md`.
- **`satsa/analysis/correlation.py`** — clusters signal findings sharing a
  `scoped_subjects` id, flags cross-detector-family corroboration. Wired
  additively into `EntityRiskProfile.correlation_clusters`
  (`satsa/analysis/risk.py`) — does not change existing score math.
- **`satsa/analysis/calibration.py`** — propose → test-against-labeled-data
  → supervisor-approve (new `calibration.approve` permission in
  `qsmlops/security/permissions/model.py`) → deploy workflow for a
  worker's detection thresholds. CLI: `sat-sa calibrate`. Scoped to one
  worker (`fast-closure`) today.
- **`evaluation/baselines/`** (z-score/MAD/IQR/fixed-threshold/random/
  severity-only) and **`evaluation/ablation/`** (`sat-sa ablate` — disables
  one default worker at a time, measures which finding families
  disappear).
- **Security hardening**: CSRF (double-submit cookie, header-auth exempt)
  on `/findings/{id}/review` and `/ingest`; login rate limiting
  (`satsa/security.py`'s `LoginRateLimiter`). TLS/encryption-at-rest/
  session-expiry remain explicitly NOT implemented (disclosed).
- **`satsa/analysis/review.py`**'s `verify_ledger_integrity()` — closes a
  previously-disclosed gap (review-decision deletion/reordering was
  undetectable) by mirroring every recorded decision into an independent
  hash-chained `EvidenceLedger` and cross-checking the DB table against it.
- **`public_benchmarks/`** — the three-layer public-dataset benchmark
  framework:
  1. `public_benchmarks/cicids2017/` and `public_benchmarks/bots/` —
     adapters converting CIC-IDS2017/Splunk-BOTS-shaped rows into SAT-SA
     canonical alert/asset dicts. **Schema-compatible, NOT run against real
     downloaded dataset files** — see section 6/9, this is the single most
     important fact about this package.
  2. `public_benchmarks/workflow_augmentation/` — `policy.yaml` (12
     scenarios) + `generator.py` (one function per scenario) +
     `serialize.py` (CSV writers + `provenance_manifest.json` sidecar).
     Every generated record carries a `derived_synthetic_workflow`
     provenance tag.
  3. `public_benchmarks/review_packet.py` — an independent-practitioner
     review instrument (five fixed questions), with a reviewer-role
     allowlist that structurally rejects any NCIIPC-affiliated label.
  All 12 scenarios are proven end to end through the real
  `satsa.ingest` → `RunService` → detector pipeline in
  `tests/test_phase84_public_benchmarks_workflow_augmentation.py`.

### B. First release-readiness correction pass (post-P26/P27)

1. Fixed `pyproject.toml`'s package discovery, which excluded
   `evaluation*`/`public_benchmarks*` — `sat-sa ablate` would have failed
   to import from an installed distribution.
2. Corrected public-dataset claim wording repo-wide so no document implies
   real BOTS/CIC-IDS2017 files were downloaded and processed (they were
   not) — see `docs/PUBLIC_BENCHMARKS.md`, the authoritative claims
   boundary.
3. Corrected "exactly one detector family" wording to "its declared
   family; known/permitted cross-detector side effects are documented" —
   only `healthy_control` (the negative control) is actually proven
   exhaustively clean; the other 11 scenarios are presence-proven, not
   exclusivity-proven.
4. Removed stale hardcoded test-count comments from `docs/deployment.md`
   and `docs/phase25/demo-runbook.md`.
5. Improved `.gitignore` (coverage/cache/env/db patterns).
6. Committed and pushed to `https://github.com/PrathamKapoor/SAT-SA-with-PQC`
   — this was the **first** publish round (commit `f6a5152`, then a
   follow-up `d375916` adding the previous version of this handoff file).

### C. P28 — release integrity hardening (this is the most recent feature work)

1. **Stopped the ML-DSA certification test from dirtying a tracked file.**
   `tests/test_hsm_a13_mldsa_certification.py` used to overwrite the
   *tracked* `tests/_a13_artifacts/mldsa_provider_sentinel.txt` with a
   fresh, randomly-generated key-id fragment on every run (R6/R6.process
   generate real random keys by design — that's part of what they
   certify). Fixed by redirecting `_write_sentinel()`'s output to a
   `tmp_path_factory`-managed temp directory; the tracked file is now a
   stable, never-overwritten fixture. No cryptographic assertion (R1–R7,
   backend-selection matrix, fail-closed tests, secret-handling tests) was
   touched or weakened. Added `TestSentinelDoesNotDirtyTrackedFixture` (3
   tests) proving this property directly, with byte-for-byte sha256
   before/after verification.
2. **Reconciled `requirements.txt` and `pyproject.toml`.** All 14 runtime
   package versions already matched exactly; the only real inconsistency
   was that `requirements.txt` mixed its 2 dev-only packages (`pytest`,
   `httpx`) in with the 14 runtime ones with no separation. Fixed with
   clearly-labeled Runtime/Development comment sections in
   `requirements.txt` (kept as one file, since `README.md`'s documented
   install flow runs `pip install -r requirements.txt` immediately
   followed by `pytest`). New test:
   `tests/test_phase87_dependency_manifest_consistency.py` (5 tests,
   comparing the two manifests to each other — no network, no comparison
   against locally-installed package versions).
3. **Found and fixed a real packaging bug via an actual wheel build.**
   Building a wheel offline (`python -m pip wheel --no-deps
   --no-build-isolation . -w <tmp>`) and inspecting it with `zipfile`
   revealed `public_benchmarks/workflow_augmentation/policy.yaml` (and the
   sibling `.json` files) were **missing** from the wheel —
   `generator.py`'s `load_policy()` reads `policy.yaml` at runtime,
   relative to the installed package's own directory, so this would have
   broken `generate_workflow()`'s default policy load on any installed
   (non-source-tree) distribution. Fixed via a new
   `[tool.setuptools.package-data]` table in `pyproject.toml`. Verified by
   rebuilding the wheel and re-inspecting it — the fix works. This exact
   proof was **repeated a second time** in the second publish round with
   identical results (no drift).
4. Fixed `docs/deployment.md`'s "Core:" dependency list, which was missing
   `starlette` and `python-multipart` (both real, confirmed-via-source-
   search runtime dependencies).
5. Added one narrow `.gitignore` rule for `SAT-SA-with-PQC/` (see section
   6) plus `build/`/`*.egg-info/`/`dist/` (wheel-build byproducts that
   `pip wheel .` leaves in the repo root even when the output wheel itself
   goes elsewhere).
6. **Full end-to-end wheel verification performed twice** (once per
   publish round): built the wheel, installed it with `pip install
   --no-deps` into a fresh venv, `cd`ed to a directory outside the repo,
   and confirmed `import satsa` / `import evaluation` / `import
   public_benchmarks` all resolve to the installed `site-packages`, not
   the source tree. A `--no-deps`-only venv (no runtime deps installed at
   all) correctly imported `satsa`/`evaluation`/`public_benchmarks` but
   not `qsmlops` (needs `dilithium_py` etc. — expected, not a packaging
   bug). A second venv with `--system-site-packages` (explicitly disclosed
   as **not** fully dependency-isolated) completed the full picture:
   `sat-sa --version`, `sat-sa ablate --help`, `sat-sa calibrate --help`,
   and a real `sat-sa ablate <entity> <assessment>` invocation against a
   fresh empty DB (forcing past `--help` into the actual deferred `from
   evaluation.ablation.runner import run_ablation_study` line) all
   succeeded from outside the repository.

### D. Second Git/GitHub publish round (most recent action)

1. Fresh Phase-1-style inspection confirmed no drift since the first
   publish round: `newrepo/main` on GitHub still equaled local
   `release-fresh` HEAD exactly before this round's commit — a clean
   fast-forward was guaranteed.
2. Repeated the full secret/database/artifact safety audit (Phase 2) —
   clean, zero matches, same as before.
3. Re-verified the sentinel file has no semantic diff via `git diff`,
   `git diff --ignore-space-at-eol`, `git diff --check`, and sha256
   comparison against `HEAD` — all confirmed clean, both before and after
   running the targeted tests and the full suite in this round.
4. Added the narrow `SAT-SA-with-PQC/` `.gitignore` rule (this task's own
   instruction differed from an earlier, more restrictive one that said
   not to touch `.gitignore` for it at all — the later, more specific
   instruction was followed, since it was the controlling one for that
   task).
5. Re-ran every targeted test file plus `compileall` plus the full suite —
   all green, all confirmed via fresh command output in that session, not
   cited from memory.
6. Rebuilt and re-inspected the wheel — identical result to the first
   time (433,078 bytes, same 4-family + 4-data-file contents).
7. Staged exactly six files by explicit path (`git add -- <paths>`, never
   `git add .`/`-A`): `.gitignore`, `docs/deployment.md`, `pyproject.toml`,
   `requirements.txt`, `tests/test_hsm_a13_mldsa_certification.py`,
   `tests/test_phase87_dependency_manifest_consistency.py`. The sentinel
   file was deliberately left unstaged (nothing real to stage).
8. Committed as `chore: verify offline release packaging` and pushed with
   `git push newrepo HEAD:main` — a plain fast-forward
   (`d375916..6cdbe97`), no force used or needed.
9. **Verified independently**, not just trusted from the push output:
   `git fetch newrepo --prune` then `git ls-remote newrepo HEAD
   refs/heads/main` both returned `6cdbe97b6db6e6534c6225d1f608d5bb92ccb4f9`
   — exactly matching local `HEAD` and local `newrepo/main`. All three
   agree.
10. Confirmed `origin` (`https://github.com/PrathamKapoor/SAT-SA.git`) was
    completely untouched: `git ls-remote origin HEAD` returned the same
    `4e38d5a...` hash before and after this entire round.

## 3. Files Changed

**P29 release commit**: `9885373a58699097695a9f30183a968816055f5c`, pushed
to `https://github.com/PrathamKapoor/SAT-SA-with-PQC` branch `main`.

The P28-specific commit (`6cdbe97`, on top of the earlier P26/P27 commits
`f6a5152`/`d375916`) touched exactly:

| Path | What changed | Why it matters |
|---|---|---|
| `pyproject.toml` | Added `[tool.setuptools.package-data]` for `public_benchmarks = ["**/*.yaml", "**/*.json"]` | Fixes a real bug: `policy.yaml` was missing from built wheels, which would break `generate_workflow()`'s default policy load on any installed distribution |
| `requirements.txt` | Added Runtime/Development comment section headers; no package/version changed | Was previously mixing dev-only deps into the runtime list with no distinction |
| `docs/deployment.md` | Fixed the "Core:" dependency list (added missing `starlette`, `python-multipart`) | Was already inaccurate before this pass — now matches the real dependency set exactly |
| `.gitignore` | Added `build/`/`*.egg-info/`/`dist/` (wheel-build byproducts) and one line for `SAT-SA-with-PQC/` | Prevents accidental future tracking of generated artifacts and the nested clone |
| `tests/test_hsm_a13_mldsa_certification.py` | Redirected the sentinel write target to a pytest temp dir; added `TestSentinelDoesNotDirtyTrackedFixture` (3 tests) | The actual fix for the tracked-file-dirtying problem, plus a regression test proving it |
| `tests/test_phase87_dependency_manifest_consistency.py` (new) | 5 tests comparing `requirements.txt` and `pyproject.toml` | Automated enforcement of item 2 above |

Everything else in the repository (`satsa/analysis/calibration.py`,
`correlation.py`, `evidence_assembly.py`, `meta_audit.py`,
`public_benchmarks/**`, `evaluation/ablation/**`, `evaluation/baselines/**`,
`tests/test_phase70_...` through `test_phase86_...`, and the P26/P27
modifications to `satsa/analysis/review.py`, `risk.py`, `run.py`,
`workers/negative_space.py`, `cli.py`, `security.py`, `service.py`,
`supervisor/agents.py`, `supervisor/engine.py`,
`qsmlops/security/permissions/model.py`) predates this handoff's most
recent work — see `docs/roadmap-status.md`'s P26/P27/P28 entries for the
detailed rationale behind each.

**Not committed, not part of any release**: `SAT-SA-with-PQC/` (separate
nested git clone, gitignored, untouched), `build/` and `qsmlops.egg-info/`
(gitignored wheel-build byproducts, still physically present on disk from
verification runs — safe, but the repo owner may want to delete them
manually; this agent could not delete them under the constraints of the
task that created them).

## 4. Current Architecture / State

- **Entry points**: `sat-sa` CLI (`satsa/cli.py::main`) and the FastAPI UI
  (`satsa/ui/__init__.py::create_app`, launched via `scripts/serve_ui.py`).
  Both call the same `SatsaService` (`satsa/service.py`) — no logic
  duplicated between CLI and UI.
- **Data flow**: CSE submission (CSV/JSON/JSONL/SQLite) → `satsa/ingest/`
  normalizes into canonical domain records → SQLite (`satsa/store/`) →
  `satsa/analysis/run.py`'s `RunService` runs the 16-worker default set →
  `satsa/analysis/risk.py` aggregates into a 7-dimension risk profile
  (carrying `correlation_clusters`) → `satsa/analysis/prioritize.py`/
  `recommend.py` → human review (`satsa/analysis/review.py`, with ledger-
  integrity verification) → TRUST-SAT signing (`satsa/analysis/trust.py`).
- **Agent registry**: `satsa/supervisor/agents.py` — 32 `AgentSpec` entries
  (9 MLOps retained, 23 SAT-SA), consumed by
  `satsa/supervisor/engine.py`'s `SupervisorEngine`.
- **Auth**: `satsa/security.py` wires the UI/CLI to `qsmlops.security.identity`
  (salted API-key credentials). Includes `verify_csrf()` (double-submit
  cookie, header-auth exempt) and `LoginRateLimiter` (in-memory,
  per-client-address, single-process — disclosed limitation).
- **Package layout**: four top-level first-party packages —
  `qsmlops/` (retained MLOps infra), `satsa/` (the product),
  `evaluation/` (baselines/ablation/workload, deliberately independent of
  the detectors they measure), `public_benchmarks/` (BOTS/CIC-IDS2017
  adapter framework + workflow scenarios + review instrument, also
  deliberately independent of the detectors). All four are now correctly
  discovered by `pyproject.toml`'s `[tool.setuptools.packages.find]`, and
  `public_benchmarks`' non-Python resource files are now correctly
  shipped via `[tool.setuptools.package-data]`.
- **Dependency contract**: `pyproject.toml`'s `[project].dependencies` is
  authoritative; `requirements.txt` mirrors it exactly (same 14 packages,
  same version specifiers) with dev-only `pytest`/`httpx` clearly
  separated in their own labeled section of the same file.
- **Git remotes** (critical, easy to get wrong): `origin` →
  `https://github.com/PrathamKapoor/SAT-SA.git` — an **old, abandoned**
  repo from an earlier incident (a commit there once carried an AI
  co-author trailer the user did not want; the user made it private and
  started fresh). **Never push here.** `newrepo` →
  `https://github.com/PrathamKapoor/SAT-SA-with-PQC.git` — the correct,
  current, public destination; `README.md`'s "Author: Pratham Kapoor" and
  the whole project's public identity point here. Local branches:
  `release-fresh` (current, tracks `newrepo/main`, orphan history starting
  from a single "Initial commit"), `main` (tracks `origin/main` — do not
  use), `backup/pre-undo-accidental-satsa-push` (preserved backup from the
  earlier incident — do not touch).

## 5. Decisions Made

- **Redirect the sentinel write, don't remove the sentinel or weaken the
  test.** Reason: the sentinel write is a pure forensic side-effect (no
  test ever reads it back or asserts against it); the *randomness* in
  R6/R6.process's key-ids is itself part of what's being certified (a
  real, non-deterministic key surviving KeyStore recreation and a fresh
  process boundary), so it must not be made deterministic just to stop the
  file from changing. Consequence: the tracked file is now a frozen,
  historical fixture; fresh per-run evidence lives in pytest's own temp
  directory and is not committed.
- **`requirements.txt` stays one file, with labeled sections, rather than
  splitting into `requirements.txt` + `requirements-dev.txt`.** Reason:
  `README.md`'s documented install flow (`pip install -r requirements.txt`
  immediately followed by `pytest`) would break if dev deps were removed
  from this file; splitting into two files would have required updating
  that documented flow, which the task instructions said to avoid unless
  actually necessary. Consequence: a future agent wanting truly separate
  install paths (e.g. a slim production-only install) will need to
  revisit this — it was a deliberate, disclosed trade-off, not an
  oversight.
- **No AI/Claude/assistant co-author attribution on any commit, ever, for
  this project.** This is not a one-time preference — it has been
  explicitly re-stated across multiple separate tasks in this project's
  history, following a real incident where such attribution appeared
  unwanted on the old (`origin`) repo. Every commit made in every publish
  round used the user's own git identity only, with zero mention of any
  authoring tool anywhere in the message, the diff, or any doc this agent
  touched.
- **Add the `SAT-SA-with-PQC/` `.gitignore` rule.** An earlier task in
  this project's history explicitly said not to touch `.gitignore` for
  this path; a later, more specific task explicitly asked for exactly one
  narrow rule to be added. The later, more specific instruction was
  treated as controlling for that particular action. The directory itself
  was never modified, moved, or deleted — only prevented from being
  accidentally `git add`-able going forward.
- **Verify wheel packaging by actually building a wheel, twice, across two
  sessions, rather than trusting `setuptools.find_packages()` alone.**
  This is what caught the real `policy.yaml` packaging bug — a
  configuration-level check alone would not have caught a missing
  `package-data` declaration. Consequence for future work: any future
  change to what `public_benchmarks/` (or any other package) ships as
  non-Python resources should be verified the same way — build a real
  wheel, inspect it with `zipfile`, don't just trust the discovery config.

## 6. Requirements and Constraints

- **No UI file may be touched** without explicit fresh instruction:
  `satsa/ui/**` (including `templates/**`, `static/**`), any
  `frontend/**`, any CSS/JS/HTML/Jinja file, UI-focused README sections.
  This has been a standing constraint across every recent task in this
  project's history (another agent has reportedly been working on the UI
  concurrently) — confirm with the user before assuming it has lapsed.
- **No destructive git operations without explicit fresh instruction**:
  no `git reset --hard`, `git checkout --`, `git clean`, `git restore`,
  force-push, deleting branches/directories.
- **No AI/Claude attribution in commits, PR descriptions, docs, or
  comments, ever, for this project** — see Decision in section 5.
- **Never fabricate validation claims.** `docs/CLAIMS.md` and
  `docs/PUBLIC_BENCHMARKS.md` exist specifically to keep every claim
  traceable to a real test or an explicit "pending" label. Any new claim
  added anywhere must get a row in `docs/CLAIMS.md` with real evidence, or
  not be made at all — this is the project's own stated rule.
- **Real NCIIPC/SOC data and real expert validation are permanently out of
  scope** until the user has real data to provide.
- **Never delete or weaken a test to make the suite pass.**
- **Package discovery must include every first-party package a documented
  CLI command imports, and package-data must include every non-Python
  resource file a package reads at runtime** — both are now tested
  invariants (`tests/test_phase86_packaging_discovery.py`,
  and the wheel-inspection procedure documented in section 5's last
  bullet). If a fifth top-level package or a new resource-file-reading
  module is ever added, update both the config and the relevant test.
- **Never `git add .` / `git add -A`.** Every commit in this project's
  history has staged explicit paths after reviewing the diff.

## 7. Testing and Verification

Commands actually executed in the most recent (second) publish round, with
actual results — all re-run fresh in that session, not cited from an
earlier one:

- `python -m pytest tests/test_hsm_a13_mldsa_certification.py -q` — **31
  passed, 2 skipped** (SoftHSM2 unavailable in this environment — expected,
  pre-existing, unrelated to this work).
- Sentinel sha256 check before/after that run, and again after the full
  suite: `7ecbbe411634861c00b587493e525a15f40140401b93b2877ea13246590ad403`
  every time. `git diff -- tests/_a13_artifacts/mldsa_provider_sentinel.txt`
  empty every time.
- Each of `test_phase86_packaging_discovery.py`,
  `test_phase87_dependency_manifest_consistency.py`,
  `test_phase77_evaluation_baselines.py`,
  `test_phase78_evaluation_ablation.py`,
  `test_phase81_public_benchmarks_provenance.py` through
  `test_phase85_public_benchmarks_review_packet.py` — **all passed**, run
  individually.
- `python -m compileall -q satsa qsmlops evaluation public_benchmarks
  scripts tests` — **exit 0**.
- `python -m pytest tests/ -q` (full suite) — **exit 0, full green**.
- Public-benchmark claim-boundary regression search (the exact `rg`/grep
  pattern list from the task) — re-run, zero new violations; every match
  found is the documentation explicitly *forbidding* a phrase, not
  asserting it.
- `python -m pip wheel --no-deps --no-build-isolation . -w <temp dir
  outside repo>` — **succeeded**, no network access, using only local
  `setuptools` 84.0.0 (the separate `wheel`/`build` PyPI packages are not
  installed and were not needed for this code path).
- `zipfile` inspection of the built wheel — **all four package families
  present** (`qsmlops/` 86 files, `satsa/` 68, `evaluation/` 8,
  `public_benchmarks/` 15) and **all four `public_benchmarks` data files
  present** (`bots/expected_signals.json`, `bots/scenario_manifest.json`,
  `cicids2017/expected_signals.json`,
  `workflow_augmentation/policy.yaml`) — identical result to the first
  time this was checked, confirming no drift.
- Secret scan (private-key headers, AWS/GitHub/Slack/OpenAI/Google key
  patterns, `password=`/`api_key=` literals) across tracked files, the
  staged diff, the new test file, and `git log --all -p` for `*.pem`/
  `*.key` paths — **zero matches** every time this has been run across
  every task in this project's recent history.
- `git ls-files` for `.db`/`.sqlite`/`.env`/`.pem`/`.key`/
  `credentials.json`/`service-account.json` patterns — **zero matches**.
- Post-push: `git fetch newrepo --prune` + `git rev-parse HEAD` +
  `git rev-parse newrepo/main` + `git ls-remote newrepo HEAD
  refs/heads/main` — **all four values identical**:
  `6cdbe97b6db6e6534c6225d1f608d5bb92ccb4f9`.
- `git ls-remote origin HEAD` — **`4e38d5a...`**, unchanged from before
  this round, confirming `origin` was never touched.

**What has not been verified, anywhere in this project's history so far**:
a genuinely dependency-isolated wheel install (only `--no-deps` alone, and
separately `--system-site-packages`, both disclosed) on a truly separate
target machine; Docker build/run (this host has no Docker executable or
daemon).

**No test was ever skipped, deleted, weakened, or replaced with a mock to
make anything pass, in any round of this work.**

## 8. Known Issues / Risks

Confirmed, not speculative:

- `build/` and `qsmlops.egg-info/` are currently sitting in the repo root
  on disk (gitignored, so safe, but not deleted — no task so far has been
  authorized to delete files outside a temp directory it created itself).
  A human should remove them manually if repo-root cleanliness matters.
- `SAT-SA-with-PQC/`'s exact provenance (which session created it, for
  exactly what purpose) is inferred from its git remote + matching commit
  history, not from any explicit documentation predating this handoff.
  Reasonably confident (it is a verification checkout of the same
  `newrepo` used to confirm earlier pushes), not certain.
- `gh` CLI is not installed in this environment. Every "verified against
  GitHub" claim in this project's recent history has relied on
  `git ls-remote`/`git fetch` against the real remote, which is a valid,
  strong verification method, but is not the same as `gh repo view`'s
  richer output (stars, description, visibility, etc. were never checked).

Things that merely might be problems (not confirmed):

- No test currently enforces that `public_benchmarks`' `package-data`
  glob (`**/*.yaml`, `**/*.json`) stays correct if new resource files are
  added in subdirectories that don't match those patterns (e.g. a future
  `.csv` fixture). The wheel-inspection *procedure* is documented (section
  5) but not automated into a repeatable test — a future agent adding new
  package data should consider adding one.

## 9. Unfinished Work

Everything below is deliberately, explicitly deferred — not overlooked:

- **Real BOTS/CIC-IDS2017 file execution.** The adapters have never been
  run against an actual downloaded dataset file (registration-gated,
  multi-gigabyte, no network access in any session so far). If real files
  ever become available: follow `docs/PUBLIC_BENCHMARKS.md`'s own "How to
  actually run this against real data" section — it is already written,
  step by step. Only update the claims in that document to the "actually
  validated" tier after a real file has genuinely been processed in a
  reproducible session — never before.
- **Real practitioner review data.** `public_benchmarks/review_packet.py`
  is a built, tested instrument; zero real `ReviewResponse` records exist.
- **Real NCIIPC/SOC expert validation** — permanently out of scope until
  the user supplies real data.
- **CI** — executed for P29 and failed: Python 3.13 failed the full suite;
  Python 3.11 failed CLI smoke. The test workflow omitted installation of
  the project that supplies the `sat-sa` console script; the release
  correction adds `pip install -e . --no-deps` after requirements.
- **Docker** — not executed because this host has no Docker executable or
  daemon.
- **A genuinely dependency-isolated wheel install on a separate target
  machine** — only same-machine smoke tests have been performed so far
  (see section 7's "what has not been verified").
- **Package-data drift protection** — see section 8's "might be a
  problem" item.

## 10. Next Subphase

No specific next subphase has been assigned as of this handoff. If one is
requested, recommended order:

1. Confirm with the user whether the concurrent UI work is still in
   progress before touching anything under `satsa/ui/`.
2. Check the CI run triggered by the release-correction commit and inspect
   any remaining failure before making a release-success claim.
3. If real BOTS/CIC-IDS2017 files become available, follow
   `docs/PUBLIC_BENCHMARKS.md`'s existing procedure rather than
   re-deriving it.
4. Do **not** start new feature work (N9/N10 Fusion extensions, N17
   calibration for more workers, UI changes, etc.) without a fresh,
   explicit instruction — this handoff's own scope was release integrity
   and publishing, not new features.

## 11. Critical Context

- **Two GitHub remotes, only one is safe.** `origin` → `SAT-SA.git` is
  old/abandoned/history-contaminated. `newrepo` → `SAT-SA-with-PQC.git` is
  correct. Check the URL every single time before pushing — never assume
  based on the remote's name.
- **`release-fresh` is an orphan branch** with no connection to the old
  `SAT-SA.git` history. Do not attempt to merge/rebase it onto `main`
  (which tracks the old `origin`) — they are intentionally disconnected.
- **The wheel-packaging bug this session found (`policy.yaml` missing from
  built wheels) was real and would have broken production use of
  `public_benchmarks` from an installed distribution.** It was only caught
  because someone actually built a wheel and inspected it with `zipfile` —
  a `setuptools.find_packages()`-level check alone (which was the only
  verification performed in an earlier round) is not sufficient to catch
  missing `package-data`. Apply this lesson to any future packaging change.
- **Why `public_benchmarks/` exists and what it can/cannot prove** is
  fully explained in `docs/PUBLIC_BENCHMARKS.md` — read it before making
  any claim about BOTS/CIC-IDS2017 in a pitch, demo, or doc edit.
- **This project's honesty discipline is not a suggestion.**
  `docs/CLAIMS.md`, `docs/PUBLIC_BENCHMARKS.md`, and
  `docs/roadmap-status.md` exist specifically to make every claim
  traceable to a real test or an explicit "pending" label. Multiple
  separate tasks across this project's history have independently
  re-verified and re-corrected claim wording — treat any request to "make
  the pitch sound stronger" with the same skepticism those tasks applied.

## 12. Agent Instructions

- **Current repository state**: branch `release-fresh`, with the P29
  release commit `9885373a58699097695a9f30183a968816055f5c` pushed to
  `newrepo/main`. Inspect `git status` before acting; do not treat prior
  CI/Docker claims as current evidence.
- **Inspect first**: `git log -5 --oneline`, `git remote -v`,
  `git status`, and this file, in that order. Then
  `docs/roadmap-status.md`'s most recent entries for the detailed
  technical record this file intentionally does not duplicate.
- **Do not unnecessarily rewrite**: the P26/P27/P28 feature code — it is
  tested and working; the claims-boundary documents — they were carefully
  worded against explicit rules across multiple tasks; the git remote
  configuration — it encodes a real incident's resolution.
- **Must be preserved**: the no-AI-attribution commit convention; the "no
  UI touch while concurrent UI work may be in progress" constraint
  (re-confirm with the user); zero destructive git operations without
  fresh explicit instruction; explicit-path staging only, never
  `git add .`/`-A`.
- **Next objective**: none currently assigned — see section 10. Do not
  begin new feature work without a fresh, explicit instruction.
