# SAT-SA: Springer proceedings manuscript (Overleaf project)

This is a self-contained LaTeX project: *Record-Level Supervisory Analytics for
Security Operations Centres: Controlled Evaluation, Cryptographic Decision Binding,
and an External Negative Result*. It uses Springer's official **LaTeX2e Proceedings
Template** (`llncs.cls` v2.25, bibliography style `splncs04`) and does not name any
particular conference or series.

## Upload and compile

1. In Overleaf, choose **New Project → Upload Project** and select the ZIP. `main.tex`
   sits at the root of the ZIP.
2. Compile with the default settings (pdfLaTeX + BibTeX). Only standard TeX Live
   packages are used, and no external files, network access or scripts are needed.
3. For a local build, run `latexmk -pdf main.tex`, or
   `pdflatex main; bibtex main; pdflatex main; pdflatex main`.

## Where things live (all editable)

| What | File(s) |
| --- | --- |
| Main file (orchestration only) | `main.tex` |
| Title, running title, authors, affiliations, e-mails, ORCIDs | `metadata.tex` (the only place to edit them) |
| Abstract and keywords | `sections/00-abstract.tex` |
| Sections 1–11 | `sections/01-introduction.tex` … `sections/11-conclusion.tex` |
| Acknowledgments, AI declaration, disclosure of interests | `sections/12-declarations.tex` |
| Tables (native LaTeX) | `tables/*.tex` |
| Figure 1 (native TikZ source) | `figures/fig-architecture.tex` |
| Figures 2–5 (vector PDF) | `figures/*.pdf` |
| References (BibTeX) | `references.bib` |
| Springer class and style (do not edit) | `llncs.cls`, `splncs04.bst` |
| Supplementary material (not compiled) | `supplementary/` |

Numbers in the text and tables are ordinary LaTeX, so edit them directly. Nothing in
the project is generated at compile time.

## Items the authors must complete (placeholders)

| Item | Location | Status |
| --- | --- | --- |
| Author names, affiliations, e-mails, ORCIDs | `metadata.tex` | AUTHOR INPUT: placeholders in `[...]`; nothing inferred |
| Acknowledgments and funding | `sections/12-declarations.tex` | AUTHOR INPUT |
| AI declaration | `sections/12-declarations.tex` | AUTHOR CONFIRMATION REQUIRED (see below) |
| Disclosure of interests (required by Springer) | `sections/12-declarations.tex` | AUTHOR INPUT |
| Target venue and series | not set | AUTHOR DECISION: the manuscript is Springer-proceedings-compatible and names no conference |
| Ethics | — | No human participants or personal data were used; no ethics approval is claimed |

**AI declaration.** Springer Nature's policy on AI in manuscript preparation (checked
2026-09-27) has the following rules:

- AI use beyond copy editing must be described in the manuscript, and the authors
  must confirm their accountability.
- AI may not be listed as an author.
- Grammar and readability editing alone need not be declared.

The draft declaration states the recorded preparation history. The authors must
confirm or correct it and add their review statement. Do not delete it without an
accurate replacement.

## Evidence and reproducibility

- **Source of the numbers.** Every number was generated from a frozen,
  hash-verified evidence set (`satsa-evidence-freeze-v2`) in the public repository
  https://github.com/PrathamKapoor/SAT-SA-with-PQC (branch `main`, commit
  `43f8d65`).
- **How they entered the source.** They were written into the LaTeX source when
  the project was generated. Their mapping to claim identifiers and experiments is
  kept in the repository (`paper/overleaf-springer/CLAIM_TRACE.csv`).
- **If you change a number,** change it in the repository's evidence pipeline too,
  or record why.
- **Levels demonstrated:**
  - Level 1: artifact verification.
  - Level 2: result regeneration.
  - Level 3: experiment reproduction, for two experiments.
  - Level 5: external-data reproduction, once on the same machine.
- **Not demonstrated:** Level 4, environment (container) reproduction.
- **External dataset:** UCI dataset 498 (CC BY 4.0). It is not included here.

## Template provenance

`llncs.cls` and `splncs04.bst` are unmodified copies from Springer's "LaTeX2e
Proceedings Template (ZIP)", linked from Springer's information for authors and
editors (retrieved 2026-09-27). The layout matches the single-column Springer
proceedings format:

- centred title, authors and institutes;
- keywords separated by ·;
- numbered sections;
- captions below figures and above tables;
- numbered references.

Springer adds copyright lines, DOIs and series footers at production; they are not
part of the manuscript.
