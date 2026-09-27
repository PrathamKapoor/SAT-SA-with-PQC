# Release readiness (Phase 14)

- **State measured:** commit `af94370` on `release-fresh`, not pushed.
- **Release candidate:** `paper/release-candidate/`, built at `baa2950`.
  `MANIFEST.json` SHA-256 is
  `801efe3307c2e4726aac8c1f3f341f76a25abc4fedbf1b34e0076207d185871d`.
- **Release record:** `research/evidence/submission-release.json`, with
  `technical_checks_pass: true` and `submission_ready: false`.

Status values:

- **READY:** done and verified.
- **AUTHOR INPUT:** only the author can resolve it.
- **BLOCKED:** needs an external action or infrastructure.
- **NOT EXECUTED:** not done, and stated as such.

## Research evidence

| Item | Status | Evidence |
| --- | --- | --- |
| freeze-v2 integrity | READY | `verify_evidence_freeze.py` intact, in the working repository and in a fresh clone (`af94370`) |
| freeze-v1, publication-v1, publication-v2 unchanged | READY | publication-v1: 51 files intact; publication-v2: 275 files intact |
| publication-v3 (Phase 14 snapshot) | READY | 278 files intact; paper commit `baa2950` |
| Negative findings and qualifiers preserved | READY | Values via `\V{}` only; external result framed as IT incident data, not SOC data |

## Paper

| Item | Status | Evidence |
| --- | --- | --- |
| IEEE Access manuscript | READY | 13 pages; compiled from the release candidate itself: 0 LaTeX errors, 0 undefined references, 33 referenced assets present |
| Venue-neutral manuscript | READY | 23 pages; 0 errors (fresh clone) |
| Numerical audit | READY | `audit_paper.py` on `paper/` and `paper/submission/`: ok; 286 claims regenerate from freeze-v2; 155 used in the text; no typed decimals; no undefined macros |
| Citation audit | READY | 48 cited = 48 bib entries = 48 verified matrix rows; 0 problems |
| Prohibited wording | READY | 0 problems (26 files scanned) |
| Figures (6 generated + Figure 1) | READY | Source experiment in every caption; byte-identical regeneration; Figure 1 from TikZ source |
| Tables (12) | READY | Byte-identical regeneration; every table referenced; source experiments in caption or rows |
| Supplementary S1–S10 | READY | Generated sections regenerate identically. The hand-written S2/S7/S8 decimals are definitions, a DOI, or claim values rounded more coarsely (S8: 1.7–78% and 5–86% for 1.7–78.4% and 5.2–85.9%) |
| Editorial consistency (automated) | READY | Oxford spelling; acronyms at first use |
| Human proofread | AUTHOR INPUT | Not performed |

## Literature

| Item | Status | Evidence |
| --- | --- | --- |
| Structured search (not a systematic review) | READY | 859 retrieved, 656 unique, 106 abstract-screened, 51 included plus 26 carried forward = 77. `screen.py` reproduces the counts |
| Sources cited in the manuscript | READY | 48 (all verified in `literature-matrix.csv`) |
| Sources used only for positioning | READY | 29 of the 77 included sources are not cited (`literature-review/included.csv`); screened and excluded records are listed in `excluded.csv` |
| arXiv / dblp coverage | NOT EXECUTED | arXiv throttled every query and dblp blocked scripted access; stated in the protocol and the paper |

## Reproducibility

| Level | Status |
| --- | --- |
| 1 Artifact verification | READY (demonstrated, including in a fresh clone) |
| 2 Result regeneration | READY (demonstrated; fresh-clone regeneration left the tree unchanged) |
| 3 Experiment reproduction | READY for T01 and P01 only |
| 4 Environment reproduction | NOT EXECUTED |
| 5 External-data reproduction | READY once, same machine (X02, X02b) |

## Tests and static checks (final code state `af94370`)

| Check | Status | Result |
| --- | --- | --- |
| Full suite `python -m pytest tests/` | READY | **1,326 passed, 117 skipped, 0 failed**, 903.7 s. Skips: 99 need `SATSA_TEST_POSTGRES_DSN`; 15 PKCS#11 library absent; 2 SoftHSM2 unavailable; 1 S3 test extras not installed |
| Paper tests (`test_phase12_paper.py`) | READY | 12 passed |
| Release tests (`test_phase14_release.py`) | READY | 3 passed |
| Publication snapshot tests (`test_phase11_publication.py`) | READY | 3 passed |
| Evidence freeze tests (`test_phase10_evidence_freeze.py`) | READY | 7 passed |
| Research experiment tests (phase 8–10 research modules) | READY | 30 passed |
| mypy `evaluation/research scripts` | READY | 90 errors in 17 files, identical to the Phase 12 baseline. All 17 are pre-existing production modules reached through imports; **0 errors in Phase 13/14 code** (release, publication, paper_assets, build_submission_release, make_submission, literature scripts, release tests) |
| ruff check / format (Phase 13/14 Python files) | READY | 0 new errors; new files formatted; legacy files not reformatted |

## Security

| Item | Status |
| --- | --- |
| Integrity mutation matrix | READY: 13/13 tested mutations detected (T01); a detection result, not prevention |
| Key management, rotation, insider re-signing | NOT EXECUTED (out of scope; stated) |
| PKCS#11 / SoftHSM2 paths | NOT EXECUTED here (library absent; 17 tests skipped) |

## Deployment

| Item | Status |
| --- | --- |
| Local API + worker HTTP smoke | READY: 18/18 checks pass (SQLite, local storage) |
| Docker / container image | NOT EXECUTED (Docker not installed) |
| Container startup / compose topology | NOT EXECUTED |
| PostgreSQL (live) | NOT EXECUTED (no DSN; 99 tests skipped) |
| SeaweedFS / S3 | NOT EXECUTED |
| CI topology job | NOT EXECUTED (runs only when pushed) |
| Hosted deployment | NOT EXECUTED |

## SIH

| Item | Status | Evidence |
| --- | --- | --- |
| SIH evidence aligned with the paper | READY | 5 safe demo numbers each map to paper claims (test passes); no factual changes to the numbers |
| Do-not-say list | READY | Now includes "human-validated" (JSON and narrative) |
| Separation of capability, controlled evidence, external evidence and deployment | READY | Unchanged structure in `research/sih-evidence.json` and `docs/SIH_TECHNICAL_NARRATIVE.md` |

## Venue compliance

`paper/VENUE_COMPLIANCE.md`: 3 PASS, 9 FIXED, 10 AUTHOR INPUT, 2 PENDING
EXTERNAL ACTION, 2 NOT APPLICABLE.

## Author blockers (AUTHOR INPUT)

1. Full author name(s), affiliation(s), e-mail(s) and ORCID(s). The
   "PrathamKapoor" / "Pratham Kapoor" discrepancy is unresolved.
2. Author biographies.
3. Code-availability statement: final wording after publication (see external
   blockers).
4. AI-disclosure confirmation, plus the author's review statement.
5. Conflict-of-interest statement.
6. Funding statement.
7. Human grammar proofread.
8. Approval of the US$2,160 APC.
9. Final selection of "Applied Research".
10. Confirmation that the work has not been published elsewhere.

## External blockers

| Item | Status |
| --- | --- |
| Public code: `newrepo/main` (`ba7fd96`) lacks all research, paper and release commits (53 commits behind at `af94370`, plus this document's commit) | BLOCKED: author push plus tag, or archive DOI |
| IEEE Author Portal upload (metadata, keywords, declarations) | BLOCKED: after the author blockers |
| PostgreSQL / Docker / SeaweedFS / hosted deployment verification | BLOCKED: infrastructure not available on this machine |
