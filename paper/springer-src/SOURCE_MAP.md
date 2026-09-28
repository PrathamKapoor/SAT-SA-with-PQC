# Source map (repository maintenance; not needed in Overleaf)

This file maps each part of the Springer manuscript to its source in the repository
and to the evidence behind it. The Overleaf package is generated from
`paper/springer-src/` by `python paper/build_overleaf.py`.

Values:

- `\V{claim-id}` macros are replaced by literal values from `paper/data/values.tex`,
  which is generated from `research/evidence/freeze-v2`.
- Every replacement is recorded in `CLAIM_TRACE.csv` with its file, source line,
  claim identifier, value and experiment.
- The provenance of each claim (bundle, JSON path, manifest hash, sample size) is in
  `paper/data/paper-data.json`.

| Manuscript part | Source file | Evidence / experiments | Figures / tables |
| --- | --- | --- | --- |
| Title, author block | `metadata.tex` | — (fixed title; author block from the author's own paper) | — |
| Abstract | `sections/00-abstract.tex` | CODE, C01, R01b, T01, O02, X02b | — |
| 1 Introduction | `sections/01-introduction.tex` | literature (`paper/literature-matrix.csv`) | — |
| 2 Related work | `sections/02-related-work.tex` | Phase 13 structured search and 2026-09-27 update search (`paper/literature-review/`) | table `tables/tab-related.tex` (literature) |
| 3 Problem formulation | `sections/03-problem-formulation.tex` | code facts: `satsa/analysis/risk.py` (Eq. 3), `satsa/analysis/prioritize.py` (Eq. 4), `satsa/analysis/workers/peer_benchmark.py` (Eq. 2), `qsmlops/evidence/ledger.py`, `satsa/analysis/trust.py` | — |
| 4 System and methodology | `sections/04-system.tex` | code facts: agent registry `satsa/supervisor/agents.py` (32 = 23 supervisory + 9 retained MLOps), 16 default workers (`satsa/analysis/run.py:_default_workers`), 5 graph nodes, ML-DSA-65; worker confidence rules `satsa/analysis/workers/*.py`, `satsa/domain/evidence.py` | Fig. 1 `figures/fig-architecture.tex` (TikZ; no data); table `tables/tab-architecture.tex`; table `tables/tab-workers.tex` |
| 5 Experimental methodology | `sections/05-experimental-methodology.tex` | `docs/STATISTICAL_AUDIT.md`, all bundles | table `tables/tab-design.tex` |
| 6.1 Detection and baselines | `sections/06-results.tex` | C01, A01 | — |
| 6.2 Prioritization | `sections/06-results.tex` | PR01 | table `tables/tab-prio.tex`; Fig. 2 `fig-prioritization.pdf` (PR01) |
| 6.3 Ablation | `sections/06-results.tex` | A01 | table `tables/tab-ablation.tex` |
| 6.4 Imperfect evidence | `sections/06-results.tex` | R01b | table `tables/tab-robust.tex`; Fig. 3 `fig-robustness.pdf` (R01b) |
| 6.5 Peer sensitivity | `sections/06-results.tex` | P01 | Fig. 4 `fig-peer.pdf` (P01) |
| 6.6 Orchestration and recovery | `sections/06-results.tex` | O01, O02 | table `tables/tab-orch.tex` |
| 6.7 Integrity | `sections/06-results.tex` | T01 | table `tables/tab-trust.tex` |
| 7 External evaluation | `sections/07-external-evaluation.tex` | X02b, X03 | table `tables/tab-external.tex`; Fig. 5 `fig-external.pdf` (X02b, X03) |
| 8 Discussion | `sections/08-discussion.tex` | O01, P01, PR01, A01, X03 | — |
| 9 Threats | `sections/09-threats.tex` | PR01, D01 (deployment smoke) | — |
| 10 Reproducibility | `sections/10-reproducibility.tex` | freeze verification; publication snapshots | — |
| 11 Conclusion | `sections/11-conclusion.tex` | — | — |
| Declarations | `sections/12-declarations.tex` | — (ethics approval statement) | — |

Figures 2–5 are copied unchanged from `paper/figures/`, generated from freeze-v2 with
provenance in `paper/figures/figures.json`. Methodology constants (bootstrap resamples
and thresholds such as 3 peers or 2·MAD) are code or configuration facts, not
experimental results.
