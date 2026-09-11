# Project Handoff

## 1. Current Phase

- **Phase**: P26/P27 ("agent-taxonomy expansion + hardening checklist" and
  "public-dataset benchmark framework"), plus a following **release-readiness
  correction pass** and a **Git/GitHub publish**.
- **Subphase**: release-readiness correction (package discovery fix + claim-
  wording correction + stale-doc cleanup) → commit → push to GitHub.
- **Objective of this subphase**: make the repository's documentation
  strictly consistent with actual evidence (no overclaiming what public
  datasets or the workflow-augmentation layer prove), fix a real Python
  packaging bug, and ship the accumulated P26/P27 work to the project's
  GitHub remote without touching any UI-facing file (another agent was
  reportedly working on the UI concurrently) and without any destructive
  git operation.
- **Overall project objective**: SAT-SA — a periodic, offline,
  evidence-driven supervisory analytics tool for SIH 26157 / NCIIPC, with a
  post-quantum trust layer (TRUST-SAT). See `README.md` for the full
  product description.
- **Status**: **COMPLETE for what was scoped.** The correction pass fixed
  everything it identified, the narrow test set + a full-suite run both
  passed, and the commit was pushed and verified against the GitHub remote
  (local HEAD == `newrepo/main`, ahead=0/behind=0, confirmed via `git fetch`
  + `git ls-remote`, not just trusted from `git push` output). Explicitly
  **NOT** complete, and not claimed complete anywhere in the repo: real
  BOTS/CIC-IDS2017 file execution, real NCIIPC/SOC expert validation, CI/
  Docker execution — see section 8/9 below.

## 2. Work Completed

### A. P26/P27 feature work (already in the repo before this subphase started)

This subphase did not implement these; it verified and documented them
honestly. They are load-bearing context for what the correction pass then
had to fix:

- **Agent roster** grew 26 → 31 → 32 (9 MLOps + 23 SAT-SA). New this
  session: Entity & Asset Resolution, Workflow Reconstruction, Evidence &
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
  session-expiry remain explicitly NOT implemented (disclosed, not
  fabricated).
- **`satsa/analysis/review.py`**'s `verify_ledger_integrity()` — closes a
  previously-disclosed gap (`docs/TRUST_MODEL.md`: review-decision
  deletion/reordering was "⚠️ not detected") by mirroring every recorded
  decision into an independent hash-chained `EvidenceLedger` (reusing the
  same class the identity-audit trail already used) and cross-checking the
  DB table against it in both directions.
- **`public_benchmarks/`** — the three-layer public-dataset benchmark
  framework:
  1. `public_benchmarks/cicids2017/` and `public_benchmarks/bots/` —
     adapters converting CIC-IDS2017/Splunk-BOTS-shaped rows into SAT-SA
     canonical alert/asset dicts. **Schema-compatible, NOT run against real
     downloaded dataset files** — see section 6/8 below, this is the
     single most important fact about this package.
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

### B. This subphase's actual work (the release-readiness correction pass)

1. **Fixed a real Python packaging bug.** `pyproject.toml`'s
   `[tool.setuptools.packages.find]` declared `include = ["qsmlops*",
   "satsa*"]` only — `evaluation*` and `public_benchmarks*` were absent.
   `satsa/cli.py::cmd_ablate` imports `evaluation.ablation.runner` at call
   time; a `pip install` built from the old config would omit both
   packages, and `sat-sa ablate` would raise `ModuleNotFoundError` in that
   installed environment (masked in this source checkout because the repo
   root is directly importable). Fixed by adding both prefixes to
   `include`. Verified via `setuptools.find_packages()` — the actual
   discovery function the build backend calls — run against the repo with
   the include patterns read live from `pyproject.toml` (not a hardcoded
   duplicate), in a new test file
   `tests/test_phase86_packaging_discovery.py` (3 tests, all passing). A
   genuine isolated `pip install`/wheel build was **not** performed: the
   `build` and `wheel` packages are not installed locally, and installing
   them would require network access, which this task forbade. This
   boundary is disclosed, not silently assumed away.
2. **Corrected public-dataset claim wording** so no document implies real
   BOTS/CIC-IDS2017 files were downloaded and processed (they were not).
   The one genuine violation found: `docs/PUBLIC_BENCHMARKS.md`'s own
   "What you can claim" section literally listed `"Validated on public
   BOTS/CIC-IDS-derived benchmark data"` as an allowed claim — contradicting
   its own "critical, disclosed limitation" section two paragraphs above.
   Rewrote that section to lead with an explicit "not yet claimable"
   statement and replaced it with the five framework-scoped claims the
   task specified verbatim. Extended "What you must NOT claim" with the
   exact forbidden phrases. Applied the same correction (schema-compatible
   *framework*, not "validated on X data") to `README.md` (two places),
   `CHANGELOG.md` (P27 section header + intro), `docs/CLAIMS.md` (row
   label), and `docs/roadmap-status.md` (P27 phase-entry status line).
3. **Corrected "exactly" wording.** Several places claimed each scenario
   triggers "exactly" one detector family — true for `healthy_control`
   (the negative control, exhaustively asserted clean) but not
   demonstrated for the other 11, whose tests use presence-only (`in
   families`) assertions and do not rule out legitimate cross-detector
   side effects (e.g. `multi_signal`'s minimal, zero-investigation-step
   alert also legitimately draws a `negative_space` finding). Changed
   wording from "exactly its declared family" to "its declared family;
   known/permitted cross-detector side effects are documented" in
   `public_benchmarks/workflow_augmentation/policy.yaml`'s header comment,
   `tests/test_phase84_public_benchmarks_workflow_augmentation.py`'s module
   docstring, `docs/PUBLIC_BENCHMARKS.md`, `docs/roadmap-status.md`, and
   `CHANGELOG.md`. **Did not** add stricter test assertions or an
   allow-list mechanism — the task explicitly said only to do that after
   proving the scenario contract defines a complete allow-list, which it
   does not, and forbade suppressing/filtering findings to force scenario
   purity.
4. **Removed stale test-count claims.** `docs/deployment.md` said
   `# ~850 tests, ~8 min, 0 failed expected`; `docs/phase25/demo-runbook.md`
   said `# 717 passed, 17 skipped, 0 failed` as a literal pre-flight
   command comment a fresh user would run today. Both replaced with
   `# release acceptance requires 0 failed` (no invented number).
   `README.md`'s "full suite (1000+, ...)" was also replaced with a
   non-numeric form, since Part 5's instruction was to avoid asserting a
   number not proven by an executed final command in *this* task session.
   **Preserved as historical** (per the task's own instruction): numbers in
   `docs/FINAL-READINESS-AUDIT.md` ("887 → 926"), `docs/autonomous-run/
   24-hour-final-report.md` and `post-24h-hardening-final-report.md`
   ("717 passed"), and the P27 roadmap entry's "98 new tests" — all are
   self-dated retrospective records of a specific historical run, not
   current operational instructions.
5. **Inspected `SAT-SA-with-PQC/`** (untracked nested directory) — it is a
   **separate, complete nested git clone** (has its own `.git/`) of
   `https://github.com/PrathamKapoor/SAT-SA-with-PQC`, currently at the
   same commit the `release-fresh` branch was at *before* this subphase's
   commit. It is almost certainly a verification checkout from an earlier
   session (used to prove a prior push was clean). **Not modified, not
   deleted, not added to git** — git does not recurse into a nested `.git`
   directory, so it correctly stays untracked by the parent repo. Its
   disposition (keep, delete, or turn into a real submodule) is the
   repository owner's decision, not made in this subphase.
6. **Improved `.gitignore`** — added `.coverage`, `.mypy_cache/`,
   `.ruff_cache/`, `htmlcov/`, a defensive `.env`/`*.pem`/`*.key`/
   `credentials.json`/`secrets.json` block (none currently exist in the
   repo — this is future-proofing per the task's Phase 3/7 instructions),
   and a general `*.db`/`*.sqlite*` pattern (no `.db` file was tracked
   before or after; all DB usage in this codebase is via `pytest`'s
   `tmp_path` or explicit `--db` CLI flags, never a committed file).
7. **Committed and pushed** everything above plus all pending P26/P27 work
   to `https://github.com/PrathamKapoor/SAT-SA-with-PQC`, branch `main`
   (pushed from local `release-fresh`, now tracking `newrepo/main`).
   Commit `f6a515289414c688598bb5a2327761fceb6be851`. **No UI file was
   touched** — verified via `git status`/timestamps before and after; the
   pre-existing UI diffs (`satsa/ui/**`) were authored in an *earlier*
   part of this same overall session, before this subphase's "don't touch
   UI" constraint was given, and were committed as-is without further
   edits (leaving them alone was the explicit instruction).

## 3. Files Changed

Full diff is in commit `f6a515289414c688598bb5a2327761fceb6be851`
(`git show --stat f6a5152`). The subphase-specific edits (as opposed to
pre-existing P26/P27 work already in the working tree) are:

| Path | What changed | Why it matters |
|---|---|---|
| `pyproject.toml` | `include` list gained `"evaluation*"`, `"public_benchmarks*"` | Real packaging bug fix — `sat-sa ablate` and the benchmark adapters would not import from an installed (non-source-tree) distribution otherwise |
| `tests/test_phase86_packaging_discovery.py` (new) | 3 tests verifying the fix via real `setuptools.find_packages()` | The one new test file this subphase added |
| `docs/PUBLIC_BENCHMARKS.md` | Rewrote "What you can claim" / "What you must NOT claim"; fixed "exactly one detector family" wording | This is the *authoritative* claims-boundary doc for `public_benchmarks/` — every other doc points here |
| `README.md` | Two spots: the Validation-section bullet and the Project-structure comment for `public_benchmarks/` | Both previously implied real BOTS/CIC-IDS2017 data was processed |
| `docs/CLAIMS.md` | Row 50 label gained "**framework**"; body tightened | Same claim-boundary correction, in the claims table specifically |
| `docs/roadmap-status.md` | P27 phase-entry `status:` line + `acceptance:` line | Same correction, in the detailed phase record |
| `CHANGELOG.md` | P27 section header + intro paragraph + one bullet | Same correction, in the release summary |
| `public_benchmarks/workflow_augmentation/policy.yaml` | Header comment block | Same "exactly" correction, at the source-of-truth config level |
| `tests/test_phase84_public_benchmarks_workflow_augmentation.py` | Module docstring only (no assertions changed) | Same correction; test logic itself was already correctly scoped (presence checks) |
| `docs/deployment.md` | One line: stale `~850 tests` comment → non-numeric | Part of Part 5's stale-count cleanup |
| `docs/phase25/demo-runbook.md` | One line: stale `717 passed` comment → non-numeric | Same |
| `.gitignore` | Expanded (coverage/cache/env/db patterns) | Release-cleanliness (Phase 5 of the git-publish instructions) |
| `handoff.md` (new, this file) | — | This document |

Everything else in the commit (`satsa/analysis/calibration.py`,
`correlation.py`, `evidence_assembly.py`, `meta_audit.py`,
`public_benchmarks/**`, `evaluation/ablation/**`, `evaluation/baselines/**`,
`tests/test_phase70_...` through `test_phase85_...`, and the modifications
to `satsa/analysis/review.py`, `risk.py`, `run.py`,
`workers/negative_space.py`, `workers/__init__.py`, `cli.py`,
`security.py`, `service.py`, `supervisor/agents.py`,
`supervisor/engine.py`, `qsmlops/security/permissions/model.py`, and the
several `tests/test_phase{4,5,6,8,53,54,56,57,63,64}_*.py` count-cascade
fixes) is **P26/P27 feature work that predates this subphase** — this
subphase reviewed, tested, and shipped it, but did not author it in this
pass. See `docs/roadmap-status.md`'s P26/P27 entries for the detailed
rationale behind each of those files.

## 4. Current Architecture / State

- **Entry points**: `sat-sa` CLI (`satsa/cli.py`, `main()`) and the FastAPI
  UI (`satsa/ui/__init__.py`, `create_app()`, launched via
  `scripts/serve_ui.py`). Both call the same `SatsaService`
  (`satsa/service.py`) — no logic duplicated between CLI and UI.
- **Data flow**: CSE submission (CSV/JSON/JSONL/SQLite) → `satsa/ingest/`
  normalizes into canonical domain records (`satsa/domain/`) → persisted
  to SQLite (`satsa/store/`) → `satsa/analysis/run.py`'s `RunService` runs
  the 16-worker default set (`satsa/analysis/workers/`) →
  `satsa/analysis/risk.py` aggregates into a 7-dimension risk profile
  (now also carrying `correlation_clusters` from
  `satsa/analysis/correlation.py`) → `satsa/analysis/prioritize.py` /
  `recommend.py` → human review (`satsa/analysis/review.py`, now with
  ledger-integrity verification) → TRUST-SAT signing
  (`satsa/analysis/trust.py`).
- **Agent registry**: `satsa/supervisor/agents.py` — 32 `AgentSpec`
  entries (9 MLOps retained, 23 SAT-SA), consumed by
  `satsa/supervisor/engine.py` (`SupervisorEngine`, two decision
  vocabularies) and the UI's `/agents`/`/architecture` pages.
- **Auth**: `satsa/security.py` wires the UI/CLI to the existing
  `qsmlops.security.identity` system (salted API-key credentials, role/
  permission checks). New this session: `verify_csrf()` (double-submit
  cookie, header-auth exempt) and `LoginRateLimiter` (in-memory,
  per-client-address, single-process — does not survive a restart or
  scale across workers, disclosed).
- **`evaluation/`** and **`public_benchmarks/`** are both deliberately
  independent of `satsa/analysis/` (ground truth / expected signals
  defined before, not derived from, the detectors being measured) — this
  is a load-bearing architectural invariant across the whole project, not
  specific to this session's additions.
- **Configuration**: `configs/settings.{development,testing,production}.yaml`
  — no secrets in any of them (verified this session). No `.env` file
  exists or is expected; the project's actual runtime configuration
  surface is the SQLite DB path + trust-key directory, both passed as CLI
  flags/env vars (`SATSA_CREDENTIAL`), not a `.env` file.
- **Dependencies**: declared in `pyproject.toml` (`dependencies = [...]`);
  `requirements.txt` is a separate, parallel dependency list (both are
  referenced in different docs — `README.md`'s Installation section uses
  `requirements.txt`; `pyproject.toml` is what `pip install .`/`-e .`
  would actually use). **These were not reconciled in this subphase** —
  see section 8.
- **Git remotes** (as of this handoff): `origin` → `https://github.com/
  PrathamKapoor/SAT-SA.git` (the OLD/abandoned repo — an earlier session
  incident put a Claude co-author trailer in a commit there; the user made
  it private and abandoned it — **never push to `origin`**). `newrepo` →
  `https://github.com/PrathamKapoor/SAT-SA-with-PQC.git` (the correct,
  current, intended destination — this is what `README.md`'s "Author:
  Pratham Kapoor" and the whole project's public identity now points to).
  Local branches: `release-fresh` (current, tracks `newrepo/main`,
  single-lineage history starting from an orphan "Initial commit"),
  `main` (tracks `origin/main` — the OLD repo's history — **do not use**),
  `backup/pre-undo-accidental-satsa-push` (a preserved backup branch from
  the earlier incident — **do not touch**).

## 5. Decisions Made

- **Decision**: Push to `newrepo` (SAT-SA-with-PQC.git) on branch `main`,
  never to `origin` (SAT-SA.git).
  **Reason**: `origin` is the repo the user abandoned after an earlier
  session accidentally pushed a commit with a Claude co-author trailer
  there; `newrepo` is the fresh, clean, orphan-history repo created
  specifically to avoid that history, and matches the URL the user gave
  in this task (`https://github.com/PrathamKapoor/SAT-SA-with-PQC`).
  **Consequence for future work**: any future push must target `newrepo`
  (or whatever remote currently points to that URL) explicitly — never
  assume `origin` is safe just because it is the conventional default
  remote name in this particular repo.
- **Decision**: No `Co-Authored-By: Claude` trailer (or any AI-attribution
  line) on the commit, despite a standing system-level instruction earlier
  in this session that said commits should carry one.
  **Reason**: this exact project has direct, documented user history of a
  strong negative reaction to exactly this attribution appearing on a
  commit, leading to the SAT-SA → SAT-SA-with-PQC repo migration in the
  first place. This task's own instructions repeated "do not reveal that
  it was pushed by you." The user's specific, repeated, contextual
  instruction was treated as controlling over the generic system default
  for this one project.
  **Consequence**: any future agent committing to this repo should
  default to **no AI co-author attribution** unless the user explicitly
  says otherwise for this specific project.
  **Alternatives considered**: including the trailer (rejected — directly
  contradicts explicit user history); asking the user (rejected — the
  task's own instructions were explicit enough that asking would have
  been redundant given "Do NOT ask me for GitHub credentials if the
  existing authentication works" and the overall directive to just get it
  shipped).
- **Decision**: Did not attempt a real isolated `pip install`/wheel build
  to verify the packaging fix end-to-end.
  **Reason**: the `build` and `wheel` packages are not installed in this
  environment, and installing them would require network access, which
  every layer of instruction in this task explicitly forbade ("Do not
  download anything from the internet").
  **Alternative used**: verified the fix via `setuptools.find_packages()`
  — the real discovery function the build backend calls — parameterized
  from `pyproject.toml`'s own config, which proves the discovery *logic*
  is correct without an actual isolated build.
  **Consequence**: a genuinely fresh `pip install` from a built
  sdist/wheel has still never been performed for this project — this
  remains an open verification gap (see section 8).
- **Decision**: Did not add strict "no other signal family fired"
  assertions to the 11 non-`healthy_control` scenario tests in
  `test_phase84_public_benchmarks_workflow_augmentation.py`, even though
  the module docstring now explicitly discloses the gap.
  **Reason**: the task explicitly said to only add such assertions "if
  you first prove the scenario contract actually defines a complete
  allow-list of permitted signal families" (it does not — `policy.yaml`
  declares one *target* family per scenario, not an exhaustive allow-list
  of every family permitted to co-occur), and explicitly forbade
  "brittle assertions that merely make tests pass" or "suppress or filter
  real detector findings to force scenario purity."
  **Consequence**: this is intentionally left as documented, honest,
  known scope — not a bug to silently fix later without first designing
  what a real allow-list would mean for each scenario.
- **Decision**: Excluded `SAT-SA-with-PQC/` from every git operation
  (staging, committing, inspecting-for-modification) entirely, treating
  it as fully out of scope.
  **Reason**: explicit, repeated instruction ("do not remove," "do not
  modify... for modification purposes," "report its nature ... before
  release" — never "clean it up" or "decide what to do with it").
  **Consequence**: it remains on disk, untracked, unexplained-to-git,
  exactly as found. A future agent should not assume it needs cleanup
  without a fresh, explicit instruction to do so.

## 6. Requirements and Constraints

- **No UI file may be touched** while another agent is reportedly working
  on the UI concurrently: `satsa/ui/**` (including `templates/**`,
  `static/**`), any `frontend/**`, any CSS/JS/HTML/Jinja file. This
  constraint was scoped to *this specific subphase* by the user's
  instructions — it is not a permanent project rule, but any agent
  resuming work immediately after this handoff should confirm with the
  user whether the concurrent UI work is still in progress before
  touching those paths.
- **No destructive git operations, ever, without explicit fresh
  instruction**: no `git reset --hard`, `git checkout --`, `git clean`,
  force-push, deleting branches/directories. This is a standing
  discipline for this project (see `main` and `backup/pre-undo-...`
  branches — both exist precisely because of a prior incident where a
  destructive-adjacent operation was needed and handled carefully).
- **No AI/Claude attribution in commits or PR descriptions for this
  project** — see Decision in section 5. Also: never add Claude as a
  GitHub collaborator, never reveal in commit history that an AI agent
  made the change.
- **Never fabricate validation claims.** This project has an unusually
  strict, explicit, self-enforced honesty discipline (`docs/CLAIMS.md`,
  `docs/PUBLIC_BENCHMARKS.md`, the "Limitations" section of `README.md`).
  Every claim must cite a real test or an explicit "pending"/"unverified"
  label. This is not optional stylistic preference — it is a repeated,
  explicit, load-bearing project requirement going back to the original
  SIH mega-prompt this project was built against.
- **Real NCIIPC/SOC data and real expert validation are explicitly,
  permanently out of scope** until the user has real data to provide —
  do not attempt to simulate, fabricate, or "close" this gap by any means
  other than actually obtaining real data.
- **Never delete or weaken a test to make the suite pass.** Stated
  explicitly in `README.md`'s Testing section.
- **Package discovery must include every first-party package a
  documented CLI command imports** — this is now a tested invariant
  (`tests/test_phase86_packaging_discovery.py`); if a new top-level
  package is ever added (a fourth sibling to `satsa`/`qsmlops`/
  `evaluation`/`public_benchmarks`), `pyproject.toml`'s `include` list and
  that test's `REQUIRED_PACKAGE_PREFIXES` tuple both need updating.

## 7. Testing and Verification

Commands actually executed in this subphase, with actual results:

- `git status --short`, `git diff --name-only`, `git log -3 --oneline` —
  run at the start (Part 1 fact-finding). Confirmed the repository's
  dirty-but-coherent starting state.
- `python -m pytest tests/test_phase86_packaging_discovery.py -q` — **3
  passed.**
- `python -m pytest tests/test_phase77_evaluation_baselines.py
  tests/test_phase78_evaluation_ablation.py
  tests/test_phase81_public_benchmarks_provenance.py
  tests/test_phase82_public_benchmarks_cicids2017.py
  tests/test_phase83_public_benchmarks_bots.py
  tests/test_phase84_public_benchmarks_workflow_augmentation.py
  tests/test_phase85_public_benchmarks_review_packet.py
  tests/test_phase86_packaging_discovery.py -v` — **124 passed** (the
  narrow set the task specified, run together after the doc/comment
  edits, to confirm no test assertion was accidentally weakened by a
  wording-only change).
- `python -m compileall -q satsa evaluation public_benchmarks qsmlops
  tests` — **exit 0**, no syntax/import errors across every first-party
  package.
- Live end-to-end check: ingested a real one-alert submission via
  `satsa_cli.main([..., "ingest", ...])` then ran
  `satsa_cli.main([..., "ablate", entity_id, assessment_id])` from a
  fresh Python process — **both returned rc 0**, `sat-sa ablate` produced
  a correct, real ablation report (confirms the packaging-fix import
  path works end-to-end from source, though not from an installed
  distribution — see section 8).
- `python -m pytest tests/ -q` (the **full** suite, run twice in this
  overall session: once before this subphase's edits began, once after
  all edits and the commit) — **both runs exited 0, full green, no
  failures.** (Exact pass/skip counts were not captured precisely due to
  a tooling/path quirk when trying to grep the background-task output
  file from a different shell than the one that produced it; this does
  not affect the exit-code result, which was directly observed as `0`
  both times.)
- Secret scan: `git grep` / `Grep` tool searches across the full working
  tree, the new untracked packages, the actual diff content, and the
  existing single commit's full history for private-key headers, AWS/
  Slack/GitHub/OpenAI/Google key patterns, and `password=`/`api_key=`
  literal assignments — **zero matches** in all cases.
- `git ls-files | grep` for `.db`/`.sqlite`/`__pycache__`/cache/build
  patterns — **zero matches** (nothing risky was ever tracked).
- Post-push verification: `git fetch newrepo` then `git ls-remote newrepo
  main` — returned `f6a515289414c688598bb5a2327761fceb6be851`, exactly
  matching local `HEAD`; `git rev-list --left-right --count
  release-fresh...newrepo/main` — **`0	0`** (zero ahead, zero behind).

**What could not be verified**: a genuine isolated `pip install`/wheel
build (see section 5's Decision on this — `build`/`wheel` not installed,
installing them forbidden by the no-network constraint). No CI run, no
Docker build/run (both remain as previously disclosed:
`docs/roadmap-status.md`/`README.md`'s Limitations section already say
these are "written, consistent with local commands, but never actually
executed" — this subphase did not change that state and did not claim
otherwise).

**No test was skipped, deleted, or weakened to make anything pass in this
subphase.**

## 8. Known Issues / Risks

Confirmed problems (not speculation):

- **Packaging discovery was broken** for `evaluation`/`public_benchmarks`
  until this subphase's fix. Anyone who had already built a wheel/sdist
  from a pre-fix checkout has a broken artifact; they need to rebuild
  after pulling this commit.
- **`requirements.txt` and `pyproject.toml`'s `dependencies` list are two
  separate, hand-maintained lists** that were not reconciled or
  deduplication-checked in this subphase. They were not observed to
  conflict, but no test enforces they stay in sync. Risk: they drift.
- **A genuine isolated-install test has never been performed** for this
  project (not in this subphase, and no earlier evidence of one in
  `docs/roadmap-status.md` either). The packaging fix is verified at the
  *discovery-configuration* level, which is strong evidence but not
  proof that `pip install .` in a truly clean venv succeeds end-to-end
  (e.g. it does not catch a missing `MANIFEST.in` entry for a non-Python
  data file, if one were ever needed — `public_benchmarks/*/expected_
  signals.json` and `scenario_manifest.json` and `policy.yaml` are
  package data files; whether `setuptools`' default behavior includes
  them in a built wheel without an explicit `package_data`/
  `MANIFEST.in` entry was **not checked** in this subphase and is a real
  open question for the next agent to verify before claiming the
  packaging fix is fully complete).

Things that merely might be problems (not confirmed):

- The full test suite was run to completion twice in this session with
  exit code 0 both times, but exact counts were not captured due to a
  tooling issue reading a background task's output file cross-shell —
  this is a verification-tooling annoyance, not evidence of an actual
  test problem.
- `SAT-SA-with-PQC/`'s exact provenance (which session created it, for
  what specific purpose) was inferred from its git remote + matching
  commit hash, not from any explicit prior documentation found in this
  session. Reasonably confident, not certain.

## 9. Unfinished Work

Everything below was explicitly, deliberately deferred — not overlooked:

- **Real BOTS/CIC-IDS2017 file execution.** The adapters
  (`public_benchmarks/cicids2017/ingest_adapter.py`,
  `public_benchmarks/bots/ingest_adapter.py`) have never been run against
  an actual downloaded dataset file. Blocked on: obtaining the files
  (registration-gated for both; BOTS is a multi-gigabyte Splunk index
  export, CIC-IDS2017 is a multi-gigabyte CSV set from UNB), which this
  and prior sessions' environments cannot do without network/registration
  access this agent does not have. **Next agent action**: if the user
  supplies local copies of either dataset, run `convert_file`/
  `convert_jsonl` against them, treat any parse failure as a real bug
  (per `docs/PUBLIC_BENCHMARKS.md`'s own instructions), and only then
  update the claims in `docs/PUBLIC_BENCHMARKS.md` to the "actually
  validated" tier — never before that point.
- **Real practitioner review data.** `public_benchmarks/review_packet.py`
  is a built, tested instrument; zero real `ReviewResponse` records exist.
  Needs actual humans (per the user's own suggestion: cybersecurity
  faculty, SOC practitioners, CTF mentors, experienced students — never
  NCIIPC-affiliated) to review real generated packets.
- **Real NCIIPC/SOC expert validation** — permanently out of scope until
  the user supplies real data. Do not attempt to simulate this.
- **CI/Docker execution** — `.github/workflows/ci.yml` and `Dockerfile`
  are written but have never actually run (no GitHub Actions run
  triggered, no Docker daemon available in any session's environment so
  far). This subphase did not attempt either — triggering a CI run would
  require pushing (already done) and then watching Actions run remotely,
  which was outside this subphase's verification scope; a follow-up
  should check `https://github.com/PrathamKapoor/SAT-SA-with-PQC/actions`
  after this push to see whether CI actually runs and passes now that
  there is a real commit on `main` for it to trigger against.
- **Package-data inclusion for `public_benchmarks/*.json`/`*.yaml`** — see
  section 8's "known issue," not yet verified either way.
- **`requirements.txt` vs. `pyproject.toml` reconciliation** — not
  attempted.

## 10. Next Subphase

Recommended order:

1. **Check whether CI actually ran** on the just-pushed commit
   (`https://github.com/PrathamKapoor/SAT-SA-with-PQC/actions`) — this is
   now possible for the first time since there's a real commit history to
   trigger against, and costs nothing to check.
2. **Verify package-data inclusion** for `public_benchmarks/`'s non-`.py`
   files (`*.json`, `policy.yaml`) — either confirm `setuptools` includes
   them automatically for this project's layout, or add an explicit
   `[tool.setuptools.package-data]` entry and a test proving it, following
   the same "verify via the real discovery/build function, not a guess"
   pattern `tests/test_phase86_packaging_discovery.py` already
   established.
3. **If real BOTS/CIC-IDS2017 files become available**: follow
   `docs/PUBLIC_BENCHMARKS.md`'s own "How to actually run this against
   real data" section (already written, step-by-step) — do not re-derive
   this process from scratch.
4. **Confirm with the user whether the concurrent UI work has landed**
   before touching anything under `satsa/ui/`.
5. Do **not** start the N9/N10 Fusion split, N17 calibration extension for
   more workers, or any other net-new feature without a fresh, explicit
   instruction — this handoff's scope was release-readiness correction and
   publishing, not new feature work.

Files likely involved in step 2: `pyproject.toml`, possibly a new
`MANIFEST.in`, a new/extended test alongside
`tests/test_phase86_packaging_discovery.py`.

Expected outcome of the next subphase: either confirmation that the
package is genuinely installable end-to-end (ideally via a real, network-
permitted `pip install` test if that constraint is ever lifted), or a
clearly documented, still-open gap if it is not.

## 11. Critical Context

- **Two GitHub remotes exist and only one is safe.** `origin` →
  `SAT-SA.git` is a **prior, abandoned, private repo** with a
  history-contamination incident in it (a Claude co-author trailer the
  user did not want). `newrepo` → `SAT-SA-with-PQC.git` is the correct,
  current, public destination. **Never** assume `origin` is the right
  remote just because it has the conventional name — check the URL every
  time.
- **`release-fresh` is an orphan branch** — its history starts from a
  single "Initial commit" with no connection to the old `SAT-SA.git`
  history. This was deliberate (see prior session's incident response).
  Do not attempt to merge/rebase it onto `main` (the branch that tracks
  the old `origin`) — they are intentionally disconnected histories.
- **Why `public_benchmarks/` exists at all and what it can/cannot prove**
  is fully explained in `docs/PUBLIC_BENCHMARKS.md` — read that file
  before making ANY claim about BOTS/CIC-IDS2017 in a pitch, demo, or
  further doc edit. It is the single source of truth for this, and this
  subphase spent significant effort making sure every other doc actually
  matches what it says.
- **`evaluation/` and `public_benchmarks/` share one architectural rule**
  with `satsa/analysis/synth.py`: ground truth / expected results must be
  defined independently of, and before, the detector logic being tested
  against them. This is why `policy.yaml`'s scenarios reference real
  worker threshold constants (e.g. `FastClosureThresholds.
  absolute_floor_seconds`) directly by import rather than guessing safe
  numbers — the generator needs to know the real thresholds to construct
  a scenario that reliably lands on the correct side of them, without
  that knowledge leaking into what's asserted as the *ground truth*
  (which stays the scenario's own declared intent in `policy.yaml`, not
  a value copied from the detector's own output).
- **The `.coverage` file and other caches were never actually committed**
  — they were untracked-but-not-ignored before this subphase (now fixed).
  If a future `git status` ever shows `.coverage` as untracked-and-
  ignorable-looking but NOT actually ignored, the `.gitignore` regression
  should be treated as a real bug, not cosmetic.
- **This project's honesty discipline is not a suggestion.** Multiple
  files (`docs/CLAIMS.md`, `docs/PUBLIC_BENCHMARKS.md`,
  `docs/roadmap-status.md`) exist specifically to make every claim
  traceable to a real test or an explicit "pending" label. A future agent
  asked to "make the pitch sound stronger" should push back or, at
  minimum, route the change through `docs/CLAIMS.md`'s own stated rule:
  "When a new claim is added anywhere in this repository's documentation,
  it must either get a row here with real evidence, or not be made."

## 12. Agent Instructions

- **Current repository state**: clean working tree (except the
  intentionally-untouched, intentionally-untracked `SAT-SA-with-PQC/`
  nested directory). Branch `release-fresh`, up to date with
  `newrepo/main`. Latest commit `f6a515289414c688598bb5a2327761fceb6be851`,
  pushed and verified on GitHub at
  `https://github.com/PrathamKapoor/SAT-SA-with-PQC`.
- **Inspect first**: `git log -5 --oneline`, `git remote -v`, `git status`,
  and this file, in that order, before making any change. Then
  `docs/roadmap-status.md`'s most recent entries (P26/P27 and this
  subphase's correction-pass note, if one gets added there) for the
  detailed technical record this file intentionally does not duplicate.
- **Do not unnecessarily rewrite**: the P26/P27 feature code (section 2A)
  — it is tested and working; the claims-boundary documents (section 2B)
  — they were carefully worded against this task's exact rules, re-check
  `docs/PUBLIC_BENCHMARKS.md`'s rules before changing any claim elsewhere;
  the git remote configuration (section 4/11) — it encodes a real
  incident's resolution, not an arbitrary choice.
- **Must be preserved**: the no-AI-attribution commit convention for this
  project (section 5); the "no UI touch while concurrent UI work is in
  progress" constraint (re-confirm with the user whether it still
  applies); the historical-report preservation rule (don't "fix" old
  numbers in self-dated retrospective docs); zero destructive git
  operations without fresh explicit instruction.
- **Next objective**: see section 10. Do not begin new feature work
  without a fresh, explicit instruction — this handoff's own scope was
  strictly release-readiness correction and publishing.
