# SAT-SA paper — reproducibility package

This directory is the publication package for the manuscript
`manuscript.tex`. Every number, table and figure in it is generated from the
canonical evidence freeze `research/evidence/freeze-v2`
(`satsa-evidence-freeze-v2`, `freeze.json` SHA-256
`2ac93ef3f2967f908c35b05c1fed97dc60282aa503d1a97594275deae3a1ff0a`).

## What is here

| Path | Content | Generated? |
| --- | --- | --- |
| `manuscript.tex`, `sections/` | venue-neutral LaTeX manuscript | hand-written; numbers only through `\V{claim-id}` |
| `data/claims-spec.json` | where each of the paper's values comes from (bundle + JSON path, derivation, supporting file or code fact) | hand-written spec |
| `data/paper-data.json`, `data/values.tex` | every value with experiment, bundle, manifest hash, metric, sample size, dataset | generated |
| `tables/*.tex` | the manuscript tables, with source-bundle comments | generated |
| `figures/*.pdf`, `figures/figures.json` | figures with experiments, source, data hash, axes, units, aggregation, sample size, caption | generated |
| `supplementary/generated/` | S1 configurations, S3–S6 and S10 result tables, `experiments.json` | generated |
| `supplementary/*.md` | S2 metric definitions, S7 dataset mapping, S8 limitations, S9 index | hand-written |
| `references.bib`, `literature-matrix.csv` | 48 verified, cited sources and their review matrix | hand-written, audited |
| `literature-review/` | structured literature search (queries, counts, screening, extraction, gap matrix; 77 included sources) | scripts + single-screener decisions |
| `manuscript.pdf` | compiled manuscript (MiKTeX, latexmk) | build output |

## Environment

Recorded in every bundle manifest (`supplementary/generated/experiments.json`):
Windows 11 (10.0.26200), Python 3.13.14, LangGraph 1.2.12, NumPy 2.5.2,
SciPy 1.17.1; dependency definitions `pyproject.toml` and `requirements.txt`
are hashed per bundle. Figures: matplotlib 3.10.3. PDF: MiKTeX 25.12
(pdfTeX 4.23), latexmk 4.88, BibTeX with `plainnat`. No container image was
executed (Docker was not installed), so the environment itself has not been
reproduced.

## Commands

```powershell
# Level 1 - artifact verification
python scripts/verify_evidence_freeze.py research/evidence/freeze-v2

# Level 2 - regenerate paper values, tables, figures, supplementary; then audit
python scripts/build_paper_assets.py
python scripts/audit_paper.py          # numbers, citations, claim wording
python scripts/export_paper_tables.py --freeze research/evidence/freeze-v2 --out <dir>
cd paper; latexmk -pdf manuscript.tex

# Level 3 - re-run experiments under NEW experiment ids (bundles are write-once)
python scripts/run_evidence_robustness_experiment.py --out <dir> --experiment-id <new-id>
python scripts/run_orchestration_experiment.py overhead --out <dir> --experiment-id <new-id> --trials 30
python scripts/run_orchestration_experiment.py recovery --out <dir> --experiment-id <new-id> --trials 3
python scripts/run_trust_integrity_experiment.py --out <dir> --experiment-id <new-id>
python scripts/run_peer_sensitivity_experiment.py --sweep --out <dir> --experiment-id <new-id>
python scripts/run_ablation_experiment.py --out <dir> --experiment-id <new-id> --seeds 5
python scripts/run_prioritization_experiment.py --out <dir> --experiment-id <new-id> --seeds 20
# C01 (controlled-final-seed-17): run_controlled_benchmark.py with the configuration in S1

# Level 5 - external data (UCI-498, CC BY 4.0)
curl -L -o incident_event_log.zip "https://archive.ics.uci.edu/static/public/498/incident+management+process+enriched+event+log.zip"
#   ZIP SHA-256 6294e29a311647306bfdfc85783f7df66517c197b9cd49aa5ee36ba9c525d1d6
python scripts/run_external_itsm_experiment.py --source-csv <dir>/incident_event_log.csv --expected-sha256 fd184bbfd62329cfe093e99da2ea7071905f2ead91900b448eb2635870821bef --out <dir> --experiment-id <new-id>
python scripts/run_external_failure_analysis.py --help   # X03 diagnostic
```

Check out the commit recorded in each bundle before re-running it
(S1 lists commits, seeds and configurations). The external run takes about
25 minutes locally.

## Canonical experiments and seeds

| Experiment | Bundle | Seed | Code commit |
| --- | --- | --- | --- |
| C01 | controlled-final-seed-17 | 17 | 82085d2 |
| R01b | EXP-R01b-evidence-robustness | 0 | 400f2d6 |
| O01 | EXP-O01-orchestration-overhead | 0 | 698b507 |
| O02 | EXP-O02-orchestration-recovery | 0 | 698b507 |
| T01 | EXP-T01-trust-mutation-matrix | — (deterministic) | 9325fdd |
| P01 | EXP-P01-peer-sweep | — (deterministic) | 9325fdd |
| A01 | EXP-A01-component-ablation | 300 | 9325fdd |
| PR01 | EXP-PR01-prioritization-replicated | 100 (+ replicate index) | 9325fdd |
| X02b | EXP-X02b-external-itsm | 0 | c1206dd |
| X03 | EXP-X03-external-failure-analysis | 0 | c1206dd |

Superseded bundles kept for history and never cited for results: EXP-X02
(ingestion bookkeeping bug; analytical outputs identical to X02b), EXP-R01,
evidence-robustness-pilot, trust-integrity-final. `freeze-v1` is kept
unchanged as history.

## Reproduction levels (only demonstrated levels are claimed)

| Level | Status | Evidence |
| --- | --- | --- |
| 1 Artifact verification | **demonstrated** | `verify_evidence_freeze.py` reports `intact: true`, 17 items (15 bundles, 2 supporting files); passed in a fresh clone in Phase 11; a mutation drill rejected edited manifests, raw results, metrics and configurations |
| 2 Result regeneration | **demonstrated** | `audit_paper.py` rebuilds paper data, tables, figures and supplementary byte-identically; `export_paper_tables.py --freeze` regenerated all 72 freeze exports byte-identically (2026-09-27) |
| 3 Experiment reproduction | **demonstrated for T01 and P01** | re-run at commit `311d56b` as REPRO-T01-trust-mutation-matrix and REPRO-P01-peer-sweep (in a scratch directory outside the repository): config, metrics and raw results identical on every analytical field (T01 125 raw leaves, P01 2,248 raw leaves; timings, ids, digests, keys and signatures excluded). Timing experiments (O01, O02) reproduce only in distribution; the others were not re-run in Phase 12 |
| 4 Environment reproduction | **not demonstrated** | container image and compose topology were never executed; one Windows machine only |
| 5 External-data reproduction | **demonstrated once, same machine** | X02 (commit 8f63aeb) and X02b (commit c1206dd) ran from the checksum-verified public CSV with identical analytical outputs; no third-party reproduction |

## What cannot be reproduced, and why

- Bit-identical bundles: timestamps, run ids, hosts, generated keys and
  ML-DSA signatures differ per run by design.
- Timing values (O01, O02, analysis times): hardware- and load-dependent;
  repeated runs give distributions, not identical values.
- PostgreSQL, SeaweedFS/S3, containers, CI topology and hosted deployment:
  never executed; no measurement depends on them.
- Human study and expert labels: not executed / no data exist.
- The external dataset depends on the UCI repository remaining available;
  the recorded checksums detect a changed file.

## Publication snapshot

`research/evidence/publication-v1/` (Phase 12 manuscript), `publication-v2/`
(Phase 13 IEEE Access draft) and `publication-v3/` (Phase 14 release candidate)
are write-once copies of this package. Each has a `publication.json` recording:

- the freeze id and `freeze.json` hash;
- the commit containing the paper;
- dataset versions and the literature snapshot date;
- the environment;
- the SHA-256 of every file.

Verify a snapshot with:

```powershell
python scripts/build_publication_snapshot.py --verify research/evidence/publication-v3
```
