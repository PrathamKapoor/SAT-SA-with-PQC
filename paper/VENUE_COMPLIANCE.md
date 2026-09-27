# IEEE Access compliance checklist

- **Target:** IEEE Access, article type *Applied Research* (see `VENUE_DECISION.md`).
- **Requirements verified:** 2026-09-27, from the official pages in
  `venue-matrix.csv` and the official LaTeX template dated 2026-05-13.
- **Package checked:** `paper/release-candidate/`, assembled from
  `paper/submission/` and compiled from the package itself (13 pages).

Status values:

- **PASS:** met without change.
- **FIXED:** met by a Phase 13/14 change.
- **AUTHOR INPUT:** only the author can supply or decide it. See
  `submission/AUTHOR_INPUT_REQUIRED.md`.
- **PENDING EXTERNAL ACTION:** needs an action outside the manuscript
  (publishing code, portal entry).
- **NOT APPLICABLE**

| Item | Requirement (source) | Status | Evidence / action |
| --- | --- | --- | --- |
| Template | Official IEEE Access template, LaTeX or Word, plus a matching PDF (submission guidelines; preparing-your-article) | FIXED | `ieeeaccess.cls` (2026-05-13), unmodified; the PDF is built from the same source; the release candidate is recompiled from itself |
| Page limit | No limit; under 20 pages strongly recommended; more than 20 needs Editor-in-Chief permission | PASS | 13 pages |
| Font / columns / margins | Template defaults, double column, single spaced | FIXED | Class defaults; no overrides |
| Abstract | 150–250 words, one paragraph, no abbreviations, references, equations or tables (template) | FIXED | One paragraph within range after macro expansion; no citations; acronyms spelled out except the system name |
| Keywords | 3–10, alphabetical | FIXED | 10 in the manuscript. They must also be entered in the portal at upload (part of the upload action) |
| Figures | Readable at final size | FIXED | 6 generated vector figures at column width, plus Figure 1 (vector, from TikZ); visually checked |
| Tables | Readable | FIXED | 12 generated tables, byte-identical to the freeze build; 8 span both columns via `\widetable` |
| References | IEEE numeric style; every citation resolves | FIXED | `IEEEtran.bst`; 48 cited = 48 bib = 48 verified matrix rows; 0 undefined citations in the release-candidate build |
| Editorial consistency | Grammar standard (submission guidelines) | FIXED (automated) | Oxford spelling, acronyms at first use, cross-reference punctuation. A human proofread is a separate row |
| Human grammar proofread | "Any articles submitted with poor grammar will be immediately rejected" | AUTHOR INPUT | No human proofread has taken place |
| Author names, affiliations, e-mail, corresponding author | Template author block | AUTHOR INPUT | Placeholders in the wrapper; the "PrathamKapoor" / "Pratham Kapoor" discrepancy was not resolved by inference |
| ORCID | Portal metadata | AUTHOR INPUT | No LaTeX field |
| Biographies | Required for all authors, below the references | AUTHOR INPUT | Placeholder `IEEEbiographynophoto`; guidance in the author checklist |
| Funding statement | `\tfootnote` | AUTHOR INPUT | Placeholder |
| Conflicts of interest | Portal declaration | AUTHOR INPUT | Not stated anywhere yet |
| AI disclosure | AI-generated text, figures, images or code disclosed in the Acknowledgment; system, sections and level identified (IEEE Access; IEEE AI-text guidelines) | AUTHOR INPUT | The draft covers all required elements (system, "all sections", level: drafting, code, screening). It is kept unchanged; the author must confirm its accuracy and add their review statement |
| Article type | Chosen in the portal | AUTHOR INPUT | Recommended: Applied Research |
| Originality / prior publication | "Results reported must not have been submitted or published elsewhere" | AUTHOR INPUT | Only the author can confirm |
| APC | US$2,160 plus taxes on acceptance | AUTHOR INPUT | Not approved yet |
| Code availability | Statement must be true for reviewers | PENDING EXTERNAL ACTION | The release commit is not on the public `newrepo/main`. Push plus tag, or archive with a DOI, then finalise the sentence in `sections/11-reproducibility.tex` |
| Data availability | Not mandated on the pages consulted | FIXED | Statement in Section XI: synthetic data regenerable; UCI-498 cited (CC BY) and not redistributed |
| Supplementary material | May be submitted for review | PASS | S1–S10 plus the literature-search material in `supplementary/` |
| Ethics | — | NOT APPLICABLE | No human participants, personal data or real SOC data |
| Anonymization | Single-anonymized review | NOT APPLICABLE | Authors are named |
| File format and size | Source plus PDF; at most 40 MB | PASS | Release candidate about 3 MB, PDF about 0.5 MB (exact sizes in `release-candidate/MANIFEST.json`) |
| Upload | IEEE Author Portal | PENDING EXTERNAL ACTION | After every AUTHOR INPUT row is resolved |

## Summary

| Status | Count | Rows |
| --- | --- | --- |
| PASS | 3 | page limit, supplementary, file format/size |
| FIXED | 9 | template, fonts/columns/margins, abstract, keywords, figures, tables, references, editorial consistency (automated), data availability |
| AUTHOR INPUT | 10 | human proofread, author block, ORCID, biographies, funding, conflicts, AI disclosure, article type, originality, APC |
| PENDING EXTERNAL ACTION | 2 | code publication, portal upload |
| NOT APPLICABLE | 2 | ethics, anonymization |

The AUTHOR INPUT rows map onto the ten author blockers in
`../docs/SUBMISSION_GATE.md`. The author block and ORCID are one blocker there
("full author names / affiliation / e-mail / ORCID").
