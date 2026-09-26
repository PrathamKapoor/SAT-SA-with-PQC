# Paper Evidence Index

Maps each candidate paper section and claim to the experiment and artifact
that supports it, and to its current status. Experiment definitions and
results: [EXPERIMENTS.md](EXPERIMENTS.md). Claims boundary:
[RESEARCH_CLAIMS.md](RESEARCH_CLAIMS.md).

Status values: **measured** (executed, bundle exists), **derived** (computed
from a measured bundle), **configured** (a design parameter, not a result),
**unverified**, **not executed**, **blocked**. "Artifact" paths are bundle
directories outside the repository; each manifest names the commit, dataset,
seed and configuration digest.

| Paper section | Claim (wording must match the evidence) | Experiment | Artifact | Status |
| --- | --- | --- | --- | --- |
| System / methodology | SAT-SA runs deterministic detectors, risk, recommendation, human review and TRUST-SAT finalization on one hosted path | code + EXP-O01, EXP-D01 | `EXP-O01-orchestration-overhead/`; `docs/deployment.md` verification record | measured (local SQLite, local processes) |
| Table 1 — dataset characteristics | Five authored catalog scenarios, 245 declared perturbations, 20-entity generated populations | EXP-C01, EXP-R01b, EXP-PR01 | respective `config.json` / `raw/results.json` | configured |
| Controlled detection | In the five executable catalog scenarios, SAT-SA emitted every declared family (recall 1.0) with extra families (precision 0.417 shared DB; 0.556 isolated DBs) | EXP-C01, EXP-A01 | `controlled-final-seed-17/`; `EXP-A01-component-ablation/` | measured (synthetic) |
| Table 2 — baseline comparison (closure) | Closure-time detector vs z-score/MAD/IQR/fixed/random on construction labels | EXP-C01 | `controlled-final-seed-17/processed/metrics.json` | measured (12 records) |
| Table 2 / Figure 2 — prioritization | On 20 generated populations SAT-SA ranked above random order and alert-volume ranking in 18–20/20 populations per metric, and matched or exceeded a closure-speed heuristic in most but not all (recall@20%: 8 higher, 11 equal, 1 lower) | EXP-PR01 | `EXP-PR01-prioritization-replicated/`; `tables/prioritization*.{csv,md,tex}` | measured (synthetic; descriptive intervals) |
| Table 3 / Figure 3 — ablation | Removing `fast-closure` or `negative-space` lowered catalog recall to 0.6; four workers lowered population ranking quality when present | EXP-A01 | `EXP-A01-component-ablation/` | measured (5 scenarios; 5 seeds, exploratory) |
| Table 4 / Figure 5 — robustness | Hosted validation matched its declared contract in 245/245 conditions; staleness and cross-record contradictions are not detected | EXP-R01b | `EXP-R01b-evidence-robustness/` | measured (synthetic) |
| Robustness — defect found | Evaluation exposed a withheld sequence-chronology finding, fixed in `da80046` | EXP-R01 → EXP-R01b | both bundles | measured |
| Table 5 — integrity | TRUST-SAT detected all 13 tested canonical-state mutations; an unsigned operational field did not affect verification | EXP-T01 | `EXP-T01-trust-mutation-matrix/` | measured (one workflow) |
| Table 6 — operational cost | Finalization median 0.288 s, verification 0.062 s, graph orchestration +0.096 s median (interval includes 0) on local SQLite | EXP-O01 | `EXP-O01-orchestration-overhead/` | measured (one machine) |
| Figure 6 — recovery | 36/36 injected interruptions recovered with identical outputs and no repeated completed stage | EXP-O02 | `EXP-O02-orchestration-recovery/` | measured (in-process injection) |
| Figure 4 — peer sensitivity | Peer finding requires ≥3 peers; detection depends on cohort spread and size | EXP-P01 | `EXP-P01-peer-sweep/` | measured (engineered cohorts) |
| Deployment | API + worker processes completed the HTTP supervisory workflow | EXP-D01 | smoke JSON report | measured for local SQLite processes only; PostgreSQL, S3 and containers **unverified** |
| Production-topology performance | Throughput/latency on PostgreSQL + S3 + API + worker | — | none | **blocked**: Docker unavailable; live PostgreSQL pending credentials |
| External validation | Behaviour on independent public/real data | EXP-X01 | none | **blocked / not executed** |
| Expert validation | Agreement with expert labels | — | none | **not executed** (template only) |
| Human evaluation | Review-time or accuracy effect for human reviewers | EXP-H01 | none | **not executed** (protocol ready) |
| Statistical inference | Any significance claim | — | none | **not made**: all comparisons are descriptive with bootstrap intervals |

## Wording rules

- Say "in the controlled synthetic scenarios" or "in the evaluated workflow"
  for every measured result above; none is real-world evidence.
- Say "detected all tested mutations", never "tamper-proof".
- Say "on one machine with SQLite" for every timing.
- Do not claim novelty, superiority or production scalability.
