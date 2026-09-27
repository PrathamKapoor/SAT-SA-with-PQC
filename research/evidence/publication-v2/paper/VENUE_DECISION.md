# Venue decision (Phase 13)

Status: **target frozen** — IEEE Access, article type *Applied Research*.
Decision date: 2026-09-27. Sources and verification dates: `venue-matrix.csv`.

## Recommended target

**IEEE Access (IEEE), Applied Research article.**

## Backup target

**Computers & Security (Elsevier), full-length article, subscription route.**
A second alternative is **Cybersecurity (Springer Nature)**. Its requirements were
verified from the official page, and its fee is US$1,485.

Before any switch to Computers & Security, its guide for authors must be read in a
browser. The official page returned HTTP 403 to automated retrieval, so its length
limit, review model and template are unverified here.

## Reason

The choice follows from what the manuscript can defend. Prestige was not a
criterion.

| Criterion | What the manuscript is | IEEE Access (verified 2026-09-27) |
| --- | --- | --- |
| Scope fit | An applied security-analytics system with an evaluation | Scope emphasises "applications-oriented articles" across IEEE fields |
| Methodological fit | Engineering plus controlled quantitative evaluation | The *Applied Research* type requires "quantitative results for validation of the approach" |
| Negative-result compatibility | The central external result is negative (ρ = −0.11) and baselines tie | *Negative Result* is an accepted article type, so negative findings are not out of scope |
| Length | About 20 single-column pages; about 12–15 IEEE double-column pages after reformatting | No hard limit; fewer than 20 pages recommended |
| Reproducibility support | Frozen, hash-verified evidence; supplementary S1–S10 | Supplementary material may be submitted for review |
| Submission practicality | Ready now | Rolling submission; no deadline |
| Novelty | Low-confidence framing; no algorithmic novelty | The acceptance criteria ask for "original writing that enhances the existing body of knowledge". There is no "novel technique" requirement, which suits an empirical and engineering contribution |

Why the other candidates were not chosen:

- **ACSAC 2026 and WOSOC 2026:** both deadlines have passed, and neither venue has
  published its 2027 call. WOSOC's topic fit is the best of all candidates, but it
  accepts only 4–8 page papers.
- **DTRAP:** its stated scope favours "extant digital threats, rather than
  laboratory models" and "real-world threats". SAT-SA's evidence is controlled data
  plus non-SOC external data, so the scope does not fit.
- **Computers & Security:** the topic fit is strongest, since the closest
  SOC-measurement prior art was published there. However, its requirements could
  not be verified, and it expects a stronger novelty contribution than this paper
  claims. It is the backup.
- **International Journal of Information Security and Journal of Information
  Security and Applications:** plausible, but either the fit is more general (IJIS)
  or the requirements could not be verified (JISA).

## Paper-format implications

- Move from `article` 11pt to the official `ieeeaccess.cls` (template dated
  2026-05-13): double column, `IEEEtran.bst` numeric references, and `\cite`
  instead of natbib `\citep`.
- The abstract must be 150–250 words in one paragraph, with no references or
  displayed equations. The template also asks for no abbreviations, so acronyms in
  the abstract are spelled out.
- Keywords go in a `keywords` environment, alphabetical, 3–10 of them.
- Author block uses `\address`, `\corresp` and `\markboth`, and biographies are
  required for all authors below the references.
- The Acknowledgment section must carry the AI-content disclosure if applicable.
  The authors must decide this; see `VENUE_COMPLIANCE.md`.
- Figures and tables need resizing to column or page width. The TikZ architecture
  figure must fit one column.

## Technical risks

- The review is single-anonymized with a binary decision. There is no "major
  revision" round, so every reviewer-visible weakness must already be answered in
  the text.
- Grammar screening is strict: "Any articles submitted with poor grammar will be
  immediately rejected".
- Reviewers may see the lack of real SOC data, human study and expert labels as
  insufficient validation. The paper states these gaps explicitly and does not
  claim effectiveness.
- The system is named after a hackathon problem statement, SIH26157. It is
  mentioned once as context, which is acceptable.

## Cost implications

- The APC is **US$2,160** plus local taxes, payable on acceptance. There is a 5%
  discount for IEEE members, 20% for society members, and a low-income-country
  discount; discounts cannot be combined.
- **This cost has not been approved by the authors.** It is a PENDING item. If it
  is unaffordable, move to the backup, where the subscription route has no fee, or
  to Cybersecurity at US$1,485.

## Length implications

The IEEE Access version compiles to the page count recorded in
`VENUE_COMPLIANCE.md`, under the 20-page recommendation. No content was cut for
length, and no font or spacing was altered outside the template.

## Evidence gaps (not fixable by formatting)

1. There is no real SOC dataset with independent outcomes.
2. There is no human or supervisor study; the protocol exists but the study was not
   executed.
3. There are no expert labels.
4. Controlled labels are construction labels, and the populations come from
   SAT-SA's own generator.
5. The deployment topology was not executed: no Docker, PostgreSQL, SeaweedFS or
   hosted deployment.

These gaps are disclosed in the manuscript. No new evidence was produced for the
venue.

## Required revisions (performed in Phase 13)

1. Reformat to the IEEE Access template (`paper/submission/`), keeping `\V{}`
   macros and generated tables and figures.
2. Bring the abstract within 150–250 words with abbreviations spelled out.
3. Add the structured literature search: add a method paragraph to Related Work
   and cite only sources verified in `literature-review/`.
4. Add data, code and artifact availability statements.
5. Add an Acknowledgment containing the AI-use disclosure required by IEEE policy.
   The text must be confirmed by the authors (PENDING).
6. Add author biographies and affiliations. These must be supplied by the authors
   (PENDING); none were invented.
