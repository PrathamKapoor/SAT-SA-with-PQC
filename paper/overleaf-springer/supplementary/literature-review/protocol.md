# Structured literature search for SAT-SA positioning (Phase 13)

This is a **structured, reproducible search for literature positioning**. It is
**not a systematic review**: there is a single screener, no second-reviewer
agreement, only the top-ranked results of broad queries were screened, no quality
appraisal was scored, and one planned source (arXiv) could not be searched. The
manuscript describes it with exactly these limits. The Phase 12 focused review
(`../literature-matrix.csv`) is kept unchanged and is folded in as an additional
source.

## Questions the search serves

1. Which prior work assesses SOC or incident-handling quality, and from what
   evidence (self-assessment, metrics, operational records)?
2. Which prior work analyses workflow or process records of security or IT
   incident handling, including detecting missing work?
3. Which prior work prioritises alerts, incidents or entities for limited human
   attention, and who the user is?
4. Which prior work performs supervisor-side (SupTech) analysis over data that
   supervised entities submit?
5. Which prior work provides tamper-evident, provenance-bearing or post-quantum
   integrity for audit records or decisions?
6. Has prior work used the external dataset (UCI-498)?

## Sources

| Source | Interface | Field searched | Date filter | Status |
| --- | --- | --- | --- | --- |
| OpenAlex | REST API `works` | `title_and_abstract.search` | published 2005-01-01 or later | searched 2026-09-27 |
| Crossref | REST API `works` | `query.bibliographic` (relevance-ranked, OR semantics) | from 2005 | searched 2026-09-27 |
| arXiv | export API | `abs:` field query | none | **not searched**: the API throttled every query (HTTP 406/429); only Q13 returned (0 results). Recorded as ERROR rows in `searches.csv` |
| dblp | search API | — | — | **not searched**: bot challenge page returned to scripted access |
| Snowballing | web search for the authors of the closest prior work | — | — | one source added (BenchIMP) |
| Phase 12 focused review | `../literature-matrix.csv` | — | — | 25 sources not retrieved by the searches carried forward |

Publisher author-guideline pages for venues are a separate evidence stream, kept
in `../venue-matrix.csv`.

## Queries

The 20 queries (Q01–Q20) are defined in `run_searches.py` (`QUERIES`) and
recorded with date, filters, total count and retrieved count in `searches.csv`.
They cover:

- SOC performance measurement, maturity and metrics (Q01–Q03)
- security-operations analytics and workflow (Q04)
- alert prioritisation, alert fatigue and human-in-the-loop SOCs (Q05–Q07, Q19)
- security process mining, conformance checking, absence of activities and
  incident-response workflow analysis (Q08–Q11)
- peer-group analytics (Q12)
- SupTech and cybersecurity supervision (Q13–Q14)
- tamper-evident logs, audit-log integrity, cryptographic provenance and
  post-quantum audit logging (Q15–Q18)
- IT-service-management incident logs with SLAs, which is the context of the
  external data (Q20)

For each query and source, the first 25 records in the source's relevance order
were retrieved. **Records beyond rank 25 were not screened.** OpenAlex returned
more than 25 hits for 12 of the 20 queries; for example, Q10 returned 1,266 and
Q15 returned 532. Crossref totals are OR-match counts in the millions and do not
measure relevance; only their top 25 were used.

## Deduplication

Records are deduplicated by DOI, case-insensitive. Records without a DOI are
deduplicated by normalised title (lower case, alphanumerics only), and a title
match to a record that has a DOI also merges. The result: 859 retrieved records
reduced to 656 unique candidates (`candidates.csv` in the repository, with
abstracts; `screening.csv` lists the same 656 candidates with their decisions).

## Screening

Screening was done by a single screener in two stages.

1. **Title stage.** All 656 titles were read, and 106 passed. Excluded titles
   were given a reason code by rule after the manual decision (`screen.py`):
   E1 for non-research items, E3 for titles in the security-operations, incident
   or audit domain, and E2 for everything else.
2. **Abstract stage.** Abstracts, venue and type were read for the 106 records.
   Where the search record had no abstract, the DOI was resolved through
   OpenAlex or Semantic Scholar. The decisions and notes are in
   `abstract-stage-decisions.json`.

Inclusion criteria:

- the work addresses at least one of questions 1–6;
- it is peer-reviewed, an authoritative standard or report (NIST, World Bank,
  SupTech survey), or a thesis carried forward from Phase 12;
- it is in English.

Exclusion reason codes:

| Code | Meaning |
| --- | --- |
| E1 | not a research item: front matter, index, peer-review report, proceedings volume or advertisement |
| E2 | outside scope |
| E3 | in the domain but does not address the positioning questions |
| E4 | insufficient scholarly content for comparison |
| E5 | duplicate or superseded version |
| E6 | not peer reviewed (preprint server, SSRN, Zenodo, Research Square) |

E6 removes several recent preprints on post-quantum audit trails and "decision
receipts" (for example SOMA-DR and a PQ-resilient audit-evidence preprint). They
are topically close to TRUST-SAT, and they are listed in `excluded.csv` so a
reader can check them.

## Classification

Included sources are classified into six groups:

- directly comparable
- related work
- methodological foundation
- security infrastructure
- dataset/data source
- background

The directly comparable and key related sources are extracted in
`extraction.csv`, with problem, data, method, evaluation, main result, relevance,
difference from SAT-SA and the evidence basis. The evidence basis is usually the
abstract; full text is noted where it was read.

## Outcome (counts from `screen.py`)

| Stage | Count |
| --- | --- |
| Retrieved (60 query-source pairs, 41 of them successful) | 859 |
| Unique candidates | 656 |
| Excluded at title stage | 550 (E1 38, E2 174, E3 338) |
| Screened on abstract | 106 |
| Included from search | 51 |
| Excluded at abstract stage | 55 (E3 28, E4 4, E5 4, E6 19) |
| Additional included (Phase 12 focused review 25, snowballing 1) | 26 |
| **Included in total** | **77** |

Included sources by class: directly comparable 8, related work 28, methodological
foundation 9, security infrastructure 14, dataset/data source 5, background 13.
These are regenerated by `python screen.py`. The excluded-by-reason counts in
`screen.py` output combine both stages.

## Findings that changed the manuscript

1. **Palma et al. (Computers & Security, 2024)** is the closest prior work. It is
   a system that automatically assesses the compliance of an incident-management
   process with a reference model (ITIL / ISO 27035). It combines trace alignment
   with a cost model that prioritises deviations, supports an auditor, and was
   shown on a public real incident-management log. Automated, record-based
   assessment of incident handling for an auditor therefore **exists**, and
   SAT-SA's application framing is weaker than Phase 12 assumed. The manuscript
   now cites this work and narrows the gap statement to the specific combination
   SAT-SA implements. Novelty confidence for the framing stays **low**.
2. **Swain and Garza (Information Systems Frontiers, 2023)** modelled SLA
   attainment on **the same UCI incident log** used in X02b (141,712 records,
   24,918 incidents, `made_sla`). This is now cited in the external-data section
   as prior use of the dataset. It does not change SAT-SA's result.
3. **SAIBERSOC (ACSAC 2020)** evaluates operational SOC performance by injecting
   synthetic attacks and includes a human-subject experiment (n = 124). It is the
   closest prior *empirical SOC-performance* evaluation and is cited.
4. **DomainPrio (IEEE Access, 2022)** analyses the population of SOC
   investigations rather than single alerts. It is cited as prior work that takes
   the population of work records as the analytical unit.

## What the search does not establish

- **Absence of prior work.** Only the top 25 results per query were screened,
  arXiv and dblp were not searched, and there was a single screener.
- **Recall.** Of 19 Phase 12 sources with DOIs, only 3 were retrieved by these
  queries. The queries target positioning topics, not the methodological and
  standards references. Even so, some SOC papers from Phase 12 were not
  retrieved (for example Agyepong et al. 2023 and Kokulu et al. 2019), so
  relevant work may be missing.
- **Novelty.** The search provides no basis for a novelty claim, and the
  manuscript makes none.

## Reproduce

```powershell
cd paper/literature-review
python run_searches.py   # reuses raw/ responses; delete raw/ to re-query (counts will drift)
python screen.py
```
