# Changelog

This project's phase-by-phase implementation history, evidence, and
disclosed limitations live in `docs/roadmap-status.md` (P0 through the
entries below) — that is the authoritative, detailed record for
P0–P27. This file is the short, release-oriented summary of what
changed and why, per checklist item 10 (release discipline). The
P28–P31 release-gate phases below are documented in commit history
and `docs/CLAIMS.md` rather than `docs/roadmap-status.md`.

Dates are approximate to the working session in which each phase
landed, not calendar-precise release dates (this project has not yet
made a tagged release).

## Unreleased — Phases P28–P31: release-gate verification, green

No new product features. Release engineering and verification only:

- **CI release gate green on both supported Pythons.** GitHub Actions
  run [34667939977](https://github.com/PrathamKapoor/SAT-SA-with-PQC/actions/runs/34667939977)
  at commit `a72f079`: Python 3.11 and Python 3.13 full suites,
  package + import integrity, and Docker build/smoke all `success`
  on GitHub-hosted Ubuntu. The workflow installs dependencies from
  `requirements.txt`, then installs the project editable (`pip install
  -e . --no-deps`) so the `sat-sa` console entry point exists in CI.
- **Python 3.13 failure root-caused and fixed** (`a72f079`): fresh
  Python 3.12+ environments no longer bundle setuptools, so the
  packaging-discovery test (which intentionally calls the real
  `setuptools.find_packages`) failed with `ModuleNotFoundError` in a
  clean 3.13 environment. Fix: `setuptools>=68` added to the dev/test
  dependency set in `pyproject.toml` and `requirements.txt`. Reproduced
  locally under Python 3.13 before the fix (exactly one failing test);
  full suite exit 0 after.
- **Docker image build + `sat-sa doctor` smoke verified** in the same
  green run (`docker-build-smoke` job). Hosted-CI build/smoke scope
  only — no target air-gapped deployment has been performed.
- **Offline packaging checks added earlier in this window**
  (`6cdbe97`): dependency-manifest consistency test
  (`tests/test_phase87_dependency_manifest_consistency.py`), wheel
  package-data fix for `public_benchmarks` resources, and the
  documented offline-install path (`docs/deployment.md` §8). The
  wheelhouse exercise was performed on the development host only.
- Exact claims boundary for all of the above (what is and is not
  proven): `docs/CLAIMS.md`.

## Unreleased — Phase P27: public-dataset benchmark framework, honestly

Added `public_benchmarks/`: a three-layer benchmark **framework**
(schema-compatible CIC-IDS2017/Splunk BOTS adapters + a controlled
workflow-augmentation layer + a practitioner-review instrument),
scoped to what public telemetry datasets actually can validate
(ingestion, detection mechanics, prioritization) without overclaiming
what they cannot (real SOC investigation/escalation behavior). The
adapters have **not** been run against actual downloaded BOTS/
CIC-IDS2017 files in this development environment — see
`docs/PUBLIC_BENCHMARKS.md` for the complete claims boundary, the
authoritative reference for what this phase does and does not support
citing.

- Source-derived alert/asset adapters for CIC-IDS2017 and BOTS,
  schema-conformant against each dataset's publicly documented format
  (neither actually downloaded in this development environment —
  disclosed prominently, not hidden).
- 12 controlled workflow-augmentation scenarios, each proven to
  trigger its declared SAT-SA detector family through the real
  `satsa.ingest` → `RunService` → detector pipeline (known/permitted
  cross-detector side effects are documented, not suppressed).
- Machine-checked provenance tagging on every generated record
  (`derived_from_source` vs. `derived_synthetic_workflow` — never
  real SOC data).
- An independent-practitioner review-packet instrument (five fixed
  questions, reusing the real UI's own explanation engine), with a
  reviewer-role allowlist that structurally rejects any
  NCIIPC-affiliated label.
- 98 new tests (`tests/test_phase81_...` through `test_phase85_...`).

## Unreleased — Phase P26: agent-taxonomy expansion and hardening

Added, in response to a user-supplied proposed agent taxonomy
(9 RETAIN + 17 proposed new SAT-SA agents) validated against the real,
running registry, plus an 11-item hardening checklist (items 1 and 11
explicitly deferred pending real NCIIPC/SOC data):

- **Agent roster grew 26 → 31 → 32** (9 MLOps + 23 SAT-SA). New
  components: Entity & Asset Resolution, Workflow Reconstruction,
  Evidence & Explainability Assembly, Meta-Audit, formal registration
  of Report Generation, and Correlation & Signal Fusion (split from
  Entity Risk Scoring). See `docs/AGENT_INVENTORY.md`.
- **Correlation & Signal Fusion** (`satsa/analysis/correlation.py`):
  clusters signal findings sharing a scoped subject, flags
  cross-detector-family corroboration, wired additively into
  `EntityRiskProfile.correlation_clusters`.
- **N17 calibration workflow** (`satsa/analysis/calibration.py`,
  `sat-sa calibrate`): propose → test-against-labeled-data →
  supervisor-approval (new `calibration.approve` permission) →
  versioned-deployment for a worker's detection thresholds. Scoped to
  `fast-closure` today; extending to more workers is a registry
  addition.
- **Baselines + ablation studies** (checklist item 2):
  `evaluation/baselines/` (z-score, MAD, IQR, fixed-threshold, random,
  severity-only, scored head-to-head against a real SAT-SA worker) and
  `evaluation/ablation/` (`sat-sa ablate`: each default worker's
  measured, unique finding-family contribution).
- **Security hardening** (checklist item 7): CSRF protection
  (double-submit cookie, header-auth exempt) on
  `/findings/{id}/review` and `/ingest`; login rate limiting. TLS,
  encryption at rest, and credential/session expiry remain disclosed
  as not implemented — see `docs/roadmap-status.md` P26 addendum for
  why each was scoped out rather than fabricated.
- **Evidence integrity vs. stronger threats** (checklist item 8):
  closed the exact gap `docs/TRUST_MODEL.md` disclosed as "⚠️ not
  detected" — `satsa_review_decisions` deletion and out-of-band
  insertion are now caught via an independent hash-chained ledger
  (`ReviewService.verify_ledger_integrity`, reusing the same
  `EvidenceLedger` class already used for identity audit), wired into
  `sat-sa audit`'s meta-audit sweep. Still bounded by filesystem-level
  trust — no external anchor.
- **Release discipline** (checklist item 10, this file + coverage/type
  check baseline — see `docs/roadmap-status.md` P26 addendum for the
  measured numbers).

Real bugs found and fixed incidentally while building the above (not
the primary goal of the work that found them):

- `satsa/analysis/run.py`'s `_build_run_extras()` had a latent
  `NameError` (a variable referenced after a `try`/`except` where it
  was only conditionally assigned).
- `satsa/analysis/workers/negative_space.py`'s missing-escalation rule
  had a gate that contradicted its own module docstring, silently
  suppressing a finding that should have fired at attenuated
  confidence.

## Earlier phases (P0–P25)

See `docs/roadmap-status.md` for the full phase-by-phase record,
including: authentication + RBAC (P18), fresh-database E2E proof
(P19), the tamper matrix (P20), the manual-sampling workload
experiment (P21), peer-benchmark hardening (P22), the claims table and
requirements traceability (P23), CI/deployment artifacts (P24), the
browser-facing CSE data upload (P25-lite), and the initial 26-agent
expansion (P25).
