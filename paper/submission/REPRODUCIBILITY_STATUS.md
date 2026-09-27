# Reproducibility status (Phase 14 release candidate)

Only levels that have actually been demonstrated are claimed. Details and
commands are in `supplementary/S9-reproducibility.md`.

| Level | Status | Evidence |
| --- | --- | --- |
| 1 Artifact verification | **Demonstrated** | `scripts/verify_evidence_freeze.py research/evidence/freeze-v2` reports intact (17 items). It passed in the working repository and in fresh clones (Phase 11, Phase 13, Phase 14). A mutation drill rejected edited manifests, raw results, metrics and configurations |
| 2 Result regeneration | **Demonstrated** | `scripts/build_paper_assets.py` plus `scripts/audit_paper.py` regenerate all 286 paper values, 12 tables, 6 figures and the generated supplementary files byte-identically from freeze-v2. This was shown in the working repository and in a fresh clone |
| 3 Experiment reproduction | **Demonstrated for two experiments** | T01 (integrity mutation matrix) and P01 (peer sweep) were re-run under new experiment identifiers with identical analytical outputs. O01 and O02 (timing) reproduce only in distribution. The other experiments were not re-run |
| 4 Environment reproduction | **Not demonstrated** | Docker is not installed. The container image and compose topology were never executed. All runs used one Windows 11 machine (Python 3.13) |
| 5 External-data reproduction | **Demonstrated once, on the same machine** | X02 and X02b ran at different commits from the checksum-verified public UCI-498 CSV, with identical analytical outputs. There is no third-party reproduction |

## Evidence chain

- **Freeze:** `research/evidence/freeze-v2`, with `freeze.json` SHA-256
  `2ac93ef3f2967f908c35b05c1fed97dc60282aa503d1a97594275deae3a1ff0a`. It is
  unchanged since Phase 11.
- **Publication snapshots:** these are write-once and never edited.
  - `publication-v1`: the Phase 12 manuscript.
  - `publication-v2`: the Phase 13 IEEE Access draft.
  - `publication-v3`: the Phase 14 release candidate.
- **Release candidate:** `paper/release-candidate/` and its `MANIFEST.json`.
  The release record is `research/evidence/submission-release.json`.

## Code availability (AUTHOR ACTION REQUIRED)

- **Public repository:** `https://github.com/PrathamKapoor/SAT-SA-with-PQC`,
  branch `main` (remote `newrepo`).
- **Public state:** at Phase 14, `newrepo/main` was commit `ba7fd96` (web UI
  import). It contains none of the research-evaluation, evidence-freeze, paper,
  literature or release commits.
- **Delta:** 50 local commits on `release-fresh` were missing from `newrepo/main`
  at the start of Phase 14, from the Phase 8 research commits through
  `a0abc17`. The Phase 14 commits add to that count.
- **Target:** the `source_commit` recorded in
  `paper/release-candidate/MANIFEST.json`.
- **Until the author publishes that commit** (push plus tag, or an archive DOI),
  the manuscript's availability statement is not verifiable by reviewers. No push
  was performed by tooling.

## What cannot be reproduced

- **Bit-identical bundles:** timestamps, ids, generated keys and ML-DSA
  signatures differ per run.
- **Timings:** they depend on hardware and load.
- **PostgreSQL, SeaweedFS/S3, containers, CI topology and hosted deployment:**
  never executed.
- **Human study and expert labels:** none exist.
- **Literature-search result counts:** they drift as the indexes change. The raw
  responses of 2026-09-27 are kept in `paper/literature-review/raw` in the
  repository.
