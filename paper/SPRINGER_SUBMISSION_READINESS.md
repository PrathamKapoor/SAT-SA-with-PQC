# Springer proceedings manuscript: readiness matrix

- **Package:** `paper/overleaf-springer/`.
- **ZIP:** `paper/overleaf-springer.zip`.
- **Source:** `paper/springer-src/`, built by `python paper/build_overleaf.py`.
- **Source commit of the build:** `c4acc1d`. Evidence: `satsa-evidence-freeze-v2`.

## Verification matrix

| Check | Status | Evidence |
| --- | --- | --- |
| Official Springer template identified | [x] | Springer "LaTeX2e Proceedings Template (ZIP)" from link.springer.com/series/558 ("Information for authors and editors"). `llncs.cls` v2.25 (2026-09-03) and `splncs04.bst`, unmodified. ZIP SHA-256 `42afb32e…a197b9` (`paper/venue/springer-template/README.md`) |
| Format matches supplied reference | [x] | Reference = Springer LNEE 601 chapter (ICDSMLA 2019). Both use the single-column Springer proceedings layout: centred title, authors and institutes; typewriter e-mails; "·"-separated keywords; numbered bold sections and subsections; numbered equations; captions below figures; numbered references; running heads. Copyright footer and DOI are added by Springer at production. No conference or series is named |
| `main.tex` at project root | [x] | ZIP listing: `main.tex`, `metadata.tex`, `references.bib`, `llncs.cls`, `splncs04.bst`, `sections/`, `tables/`, `figures/`, `supplementary/`, `README.md` |
| All sections editable | [x] | 13 files in `sections/`; `main.tex` only orchestrates |
| All tables editable | [x] | 8 native LaTeX tables in `tables/` |
| All figures included | [x] | Fig. 1 native TikZ (`figures/fig-architecture.tex`); Figs. 2–5 vector PDFs |
| Bibliography included | [x] | `references.bib`: the 48 cited, verified entries |
| No absolute paths | [x] | Build check for drive-letter paths, `/mnt/data` and repository path segments: 0 hits (after removing one local path from S9) |
| No hidden dependencies | [x] | No `\V` macros, no data files, scripts, shell escape or network access needed; only standard TeX Live packages |
| Overleaf-oriented structure | [x] | See `overleaf-springer/README.md` |
| Clean local compile (TeX available: MiKTeX 25.12) | [x] | Package compiled in an isolated copy (author typography: Times 12 pt, title 14 pt, bold headings only): 32 pages, 0 errors, 0 undefined references, 0 undefined citations, 0 missing files, 0 overfull boxes |
| Fresh-directory compile | [x] | ZIP extracted into an unrelated temporary directory and compiled: same result |
| Editability test | [x] | Edited a section sentence, a table caption, a table number and a reference title in an extracted copy; all appeared in the recompiled PDF with 0 errors |
| ZIP structure validated | [x] | Root-level `main.tex`; 55 files; no nested project folder |
| No build junk | [x] | No `.aux/.log/.synctex.gz/.fls/.fdb_latexmk/.out/.toc/.bbl/.blg` in the ZIP; `main.pdf`, `MANIFEST.json`, `version.json`, `CLAIM_TRACE.csv` and `SOURCE_MAP.md` are kept in the repository but excluded from the ZIP |
| Evidence frozen | [x] | freeze-v1, freeze-v2 and publication-v1/v2/v3 unchanged |
| All numbers traceable | [x] | 275 resolved values (201 distinct claims) in `CLAIM_TRACE.csv` → claim id → experiment → bundle (`paper/data/paper-data.json`); source audit: 0 undefined claims, 0 hand-typed decimals |
| Citations verified | [x] | 48 cited = verified rows of `paper/literature-matrix.csv` (DOI and metadata checked via Crossref, OpenAlex or publisher record) |
| Literature reviewed | [x] | Phase 13 structured search (656 unique, 77 included) plus the 2026-09-27 update search for closest prior art and counterevidence (100 records, 8 included), in `paper/literature-review/`. Not a systematic review |
| No unsupported novelty | [x] | Prohibited-wording scan: 0 hits; framing stated as a low-confidence candidate; closest prior art (Palma et al.) discussed, including its use of the same public incident log |
| Negative external result preserved | [x] | Section 7: ρ = −0.11 (−0.42 to 0.21) against slowest resolution ρ = 0.94; construct mismatch, saturation, missing dimensions; no tuning |
| Limitations preserved | [x] | Section 9: synthetic/controlled data, construction labels, own generator, SQLite on one machine, no human study, no expert labels, deployment not executed; baseline ties; silent stale/contradictory evidence; peer-cohort dependence |
| Author block | [x] | `metadata.tex`: Pratham Kapoor; Department of Information Technology, Mukesh Patel School of Technology Management & Engineering, SVKM's NMIMS University, Mumbai, India (format of the author's own paper; no e-mail or ORCID line) |
| AI declaration | removed at the author's instruction | Springer Nature's policy (checked 2026-09-27) asks authors to declare AI use beyond copy editing; compliance is the author's responsibility at submission |
| Funding statement | pending | bracketed placeholder in `sections/12-declarations.tex` |
| Disclosure of interests | pending | bracketed placeholder (Springer requires this statement) |
| Human-study status preserved | [x] | "no study was executed"; "no expert-labelled data exist" |
| Deployment status preserved | [x] | Docker, compose, SeaweedFS, CI topology and hosted deployment not executed; SQLite-only measurements. The post-freeze local PostgreSQL maintenance run is stated as not part of the evaluation |

## Open items (author decisions; nothing was guessed)

1. Author block: done (see matrix).
2. Acknowledgments and funding, or deletion of that paragraph.
3. AI declaration: removed at the author's instruction (see matrix).
4. Disclosure of Interests statement.
5. Target conference and series. Check its page limit before submission.
   - **Current length:** 32 pages at the author's 12 pt typography (21 pages at the standard llncs 10 pt), including about 3.5 pages of references for
     48 sources. Springer's guidance is "full papers (12–15 (or more) pages)".
   - **If a limit applies, candidate cuts** that keep the essential evidence:
     - move Table 4 (ablation) and Fig. 4 (peer grid) to the supplementary
       material;
     - shorten Table 1 (related work);
     - trim references to the ones used in Sections 2 and 7.
6. Release tag or archive DOI for the code, if the venue wants one. The paper
   cites `main` at commit `43f8d65`; no tag exists.
7. Human proofread.
