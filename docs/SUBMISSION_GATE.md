# Submission gate (Phase 14)

- **Venue:** IEEE Access.
- **Article type:** Applied Research (author confirmation required).
- **Release candidate:** `paper/release-candidate/`.
- **Release record:** `research/evidence/submission-release.json`.
- **Author checklist:** `paper/submission/AUTHOR_INPUT_REQUIRED.md` (with
  machine-readable status in `author-inputs.json`).

Every item has exactly one class:

- **A. Automatically resolvable:** machine-checkable work, done in Phases 13–14,
  with its status.
- **B. Needs author input:** only the author can supply or decide it.
- **C. Must not be changed:** frozen record; changing it would alter the science.
- **D. Must remain explicitly unverified:** not executed, and must be stated as such.

## A. Automatically resolvable

| Item | Status | Evidence |
| --- | --- | --- |
| IEEE Access template | RESOLVED | Official `ieeeaccess.cls` (2026-05-13), vendored unmodified |
| Page count | RESOLVED | 13 pages (IEEE; under 20 recommended); venue-neutral version 23 pages |
| Abstract length and form | RESOLVED | One paragraph within 150–250 words; no citations; acronyms spelled out |
| Keywords | RESOLVED | 10, alphabetical |
| References | RESOLVED | 48 cited = 48 bib entries = 48 verified matrix rows; IEEEtran style |
| Numbers | RESOLVED | 286 values from freeze-v2 via `\V{}`; no typed decimals (paper audit) |
| Tables and figures | RESOLVED | 12 tables and 6 figures regenerate byte-identically; Figure 1 compiled from its TikZ source |
| Supplementary | RESOLVED | S1–S10 plus the literature-search protocol |
| Editorial consistency (automated) | RESOLVED | Oxford spelling in the prose; acronyms defined at first use (SLA, CI, NDCG, IQR, TP/FN); cross-references resolve. The spelling of frozen identifiers and freeze-derived text is kept verbatim |
| Stale facts in companion documents | RESOLVED | "33 verified sources" corrected to 48 in `PAPER_HANDOFF.md` and S9; S9 now lists publication-v1, v2 and v3 |
| SIH do-not-say list | RESOLVED | "human-validated" added to `research/sih-evidence.json` and the narrative |
| Release candidate, manifest, release record | RESOLVED | `paper/release-candidate/MANIFEST.json`; `research/evidence/submission-release.json` |
| Build from the package itself | RESOLVED | The release candidate is compiled in an isolated copy (`scripts/build_submission_release.py`) |
| Fresh-clone reproduction | RESOLVED | See `docs/RELEASE_READINESS.md` |
| Full test suite on final code | see `docs/RELEASE_READINESS.md` | the exact counts are recorded there |

## B. Needs author input

These are split into author input, author decision and author action. The details
and exact locations are in `paper/submission/AUTHOR_INPUT_REQUIRED.md`.

| # | Item | Kind | Status |
| --- | --- | --- | --- |
| 1 | Full author name(s), co-authors. The manuscript says "PrathamKapoor" and the LICENSE says "Pratham Kapoor"; not resolved by inference | author input | NEEDS AUTHOR INPUT |
| 1a | Affiliation(s) | author input | NEEDS AUTHOR INPUT |
| 1b | E-mail(s), corresponding author | author input | NEEDS AUTHOR INPUT |
| 1c | ORCID(s) | author input | NEEDS AUTHOR INPUT |
| 2 | Biographies (all authors) | author input | NEEDS AUTHOR INPUT |
| 3 | Code availability: publish the release commit (push plus tag, or archive DOI), then finalise the statement | author action (external) | AUTHOR ACTION REQUIRED |
| 4 | AI disclosure: confirm or correct the draft in the Acknowledgment and add a review/responsibility statement | author decision | AUTHOR CONFIRMATION REQUIRED |
| 5 | Conflict-of-interest statement | author input | NEEDS AUTHOR INPUT |
| 6 | Funding statement | author input | NEEDS AUTHOR INPUT |
| 7 | Human grammar proofread | author action | AUTHOR ACTION REQUIRED (automated editorial audit complete; human proofread pending) |
| 8 | APC approval, US$2,160 | author decision | AUTHOR CONFIRMATION REQUIRED |
| 9 | Final article type: Applied Research | author decision | AUTHOR CONFIRMATION REQUIRED |
| 10 | Originality / not published elsewhere | author decision | AUTHOR CONFIRMATION REQUIRED |

## C. Must not be changed

| Item | Reason |
| --- | --- |
| `research/evidence/freeze-v1`, `freeze-v2` | Canonical experiment record; hash-verified |
| `research/evidence/publication-v1`, `publication-v2` | Write-once historical snapshots |
| Every reported value (286 claims) and its experiment, n and qualifiers | Generated from freeze-v2; changing a value requires a new experiment and freeze |
| Negative findings | Closure-speed baseline comparable; ties with fixed-threshold and MAD rules; external ρ = −0.11 (95% −0.42 to 0.21) against slowest resolution ρ = 0.94; construct mismatch; detector saturation; silent stale and contradictory evidence; peer-cohort dependence |
| External-result framing | Real public IT incident data, not SOC data; feasibility and construct-validity evidence; the risk model was not changed |
| Risk weights, thresholds, baselines, populations | No tuning on evaluation data |
| Literature status | "Structured and reproducible, not a systematic review"; 77 included sources; 48 cited |
| Contribution position | Framing low confidence; no novelty claim; security is an integration of standard primitives; reproducibility is good practice |
| Venue decision | IEEE Access, Applied Research; backup Computers & Security |

## D. Must remain explicitly unverified

| Item | Status |
| --- | --- |
| Docker / container image | UNVERIFIED (Docker not installed) |
| Compose topology / container startup | UNVERIFIED (not executed) |
| PostgreSQL (live) | UNVERIFIED (`SATSA_TEST_POSTGRES_DSN` not set) |
| SeaweedFS / S3 object storage | UNVERIFIED (not executed) |
| CI topology job | UNVERIFIED (runs only when pushed; not executed) |
| Hosted API/worker deployment | UNVERIFIED (not executed) |
| Local API + worker HTTP workflow | VERIFIED locally: 18/18 checks pass (SQLite, local storage) |
| Human / supervisor study | NOT EXECUTED (protocol only) |
| Expert-labelled findings | NOT EXECUTED (pipeline only; no labels) |
| Real SOC data | NOT AVAILABLE |
| Environment reproduction (Level 4) | NOT DEMONSTRATED |
| Third-party reproduction | NOT DEMONSTRATED |
