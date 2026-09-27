# Paper Evidence Index (freeze v2)

Canonical evidence: `research/evidence/freeze-v2/` (verify with
`python scripts/verify_evidence_freeze.py research/evidence/freeze-v2`);
freeze v1 is kept unchanged as history. Machine-readable catalog:
`research/evidence/catalog.json`. Tables and statistical audit:
`freeze-v2/exports/*.{csv,md,tex}`; figure data:
`freeze-v2/exports/figures/` with `figures-index.json`. Report:
[EVIDENCE_FREEZE.md](EVIDENCE_FREEZE.md). Limitations:
[RESEARCH_LIMITATIONS.md](RESEARCH_LIMITATIONS.md).

Manuscript values: `paper/data/paper-data.json` maps each `\V{claim-id}` used in
`paper/manuscript.tex` to its experiment, bundle, manifest hash, metric, sample size
and dataset; `python scripts/audit_paper.py` verifies paper number = paper data =
canonical bundle = frozen result.

Evidence categories are never merged: **S** controlled synthetic, **X**
external dataset (partial), **O** real SOC operational data (none exists).

## Claim matrix

| RQ | Claim (exact wording) | Exp. | Dataset | Baseline | Metric | Canonical result | Artifact | Cat. | Limits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RQ1 | In five controlled catalog scenarios SAT-SA emitted every declared finding family, with additional undeclared families | C01 | S: catalog v1.0 | declared labels | micro P/R/F1, action alignment | TP 5, FP 7, FN 0; P 0.417, R 1.0, F1 0.588; action 4/5 | `controlled-final-seed-17` | B | authored labels |
| RQ2 | On 12 construction-labelled closures, SAT-SA's fast-closure detector matched fixed-threshold and MAD baselines (F1 1.0); z-score and IQR flagged none | C01 | S | z/MAD/IQR/fixed/random | F1 | SAT-SA 1.0 = fixed 1.0 = MAD 1.0; random 0.33 | `baseline_closure_time.*` | B | 12 records |
| RQ2 | Across 20 generated populations SAT-SA ranked pathological entities above random order and alert-volume ranking in 18–20/20 populations per metric, and matched or exceeded a closure-speed heuristic in most but not all | PR01 | S: generator, seeds 100–119 | random, alert volume, fastest closure | P/R/NDCG@10/20/30% | recall@20% median 0.8 vs 0.6 (closure), 0.2 (volume), 0.20 (random); vs closure 8 higher / 11 equal / 1 lower | `EXP-PR01…`, `prioritization*.*`, FIG-2 | B | generator aligned with detectors |
| RQ2 | Removing fast-closure or negative-space lowered catalog recall from 1.0 to 0.6; four workers lowered population ranking quality when present | A01 | S | full worker set | micro R; recall@20% | see EXPERIMENTS.md | `EXP-A01…`, `ablation_*`, FIG-3 | B | n=5 seeds exploratory |
| RQ3 | Findings in the evaluated workflow cite resolvable source records through an authorized decision and a verifying receipt | T01, D01 | S | checklist | coverage | receipt verified; 18/18 HTTP checks | `EXP-T01…`, `supporting/EXP-D01…json` | C | one workflow |
| RQ4 | Hosted validation matched its declared contract in 245/245 perturbed conditions; stale and contradictory records were accepted silently | R01b | S: 5 scenarios × 248 conditions | paired control | contract match, family change | 245/245; omission rejected 3/11/14 of 25; staleness 15/15 accepted, no change | `EXP-R01b…`, `robustness_*`, FIG-5 | B | authored fixtures |
| RQ4 | Robustness evaluation exposed and fixed a withheld sequence-chronology finding | R01 → R01b | S | — | family emitted for re-sequenced duplicate steps | absent in 5/5 scenarios before `da80046` (R01); present in 5/5 after, 0 findings withheld (R01b) | `EXP-R01…` (superseded), `EXP-R01b…` | B | worker log messages from R01 were not recorded in its bundle |
| RQ5 | TRUST-SAT detected all 13 tested single-field mutations of canonical state; an unsigned operational field did not affect verification | T01 | S: one workflow | valid control, negative control | detected / expected | 13/13 detected; control verified | `EXP-T01…`, `integrity_mutations.*` | D | not a detection rate |
| RQ6 | A peer finding needs ≥3 peers and depends on cohort spread and size | P01 | S: 96 engineered cells | fixed policy | finding emitted, MAD deviation | tight: 7/8 subjects flagged from n=3; wide: extremes only, fast subjects from n≥5 | `EXP-P01…`, FIG-4 | B | closure metric only |
| RQ7 | On one machine with SQLite, LangGraph orchestration added a median +0.096 s (95% interval −0.020 to +0.211) and 38 DB calls per workflow with identical outputs; supervisory finalization took a median 0.288 s | O01 | S: mixed scenario | direct execution; unreviewed config | paired median difference | as stated | `EXP-O01…`, `orchestration_*`, FIG-6a | C/E | one machine, SQLite |
| RQ7 | 36/36 injected interruptions recovered with outputs identical to uninterrupted runs and no completed stage repeated | O02 | S | uninterrupted reference | recovery, duplication | 36/36 | `EXP-O02…`, `recovery.*`, FIG-6b | C/E | in-process injection |
| EXT-1 | The unchanged pipeline ingested and analysed a real IT incident-workflow log (50 groups, 22,604 incidents) without rejections | X02b | X: UCI-498 | — | ingestion counts; run status | 134,888 rows received, 134,888 accepted, 0 rejected; 50/50 analyses completed | `EXP-X02b…` | B | ITSM, not SOC |
| EXT-2 | On this real distribution four existence-rule or distribution detectors fired for every group although their input prevalence varied widely | X03 | X | — | flagging rate; input prevalence | 4 families 50/50; cases without steps 1.7%–78.4% | `external_failure_saturation.*` | B (negative) | design regime of existence rules |
| EXT-3 | SAT-SA's entity risk was not associated with the groups' SLA-miss rate; a resolution-time rule was | X02b | X | random, volume, slowest resolution, reassignment rate | Spearman ρ; top-quartile P/R/NDCG | SAT-SA ρ −0.11 (−0.42, 0.21); slowest resolution ρ 0.94; SAT-SA P@10% 0.40 vs random 0.25 | `external_association.*`, `external_ranking.*`, FIG-7 | B (negative) | SLA ≠ supervisory quality |
| EXT-4 | On the external data, fast-closure prevalence was negatively associated with SLA misses, so SAT-SA's execution-gap dimension ran opposite to the outcome; the failure is attributed mainly to construct mismatch | X03 | X | — | Spearman ρ with bootstrap | fast-closure ρ −0.70 (−0.82, −0.52); execution-gap dimension ρ −0.41 (−0.66, −0.11); 3 dimensions unavailable | `external_failure_*`, FIG-8, `docs/EXTERNAL_FAILURE_ANALYSIS.md` | B (negative, diagnostic) | diagnostic; one dataset |
| — | Real SOC operational effectiveness | — | O | — | — | **NOT DEMONSTRATED** | none | — | no data |
| — | Expert agreement with SAT-SA findings | — | — | — | — | **NOT EXECUTED** (pipeline ready, no expert-labelled data) | none | — | no labels |
| — | Human reviewers work faster or better with SAT-SA | H01 | — | evidence-only | — | **NOT EXECUTED** (protocol ready) | none | — | no study |
| — | Production-topology performance (PostgreSQL, S3, containers) | — | — | — | — | **BLOCKED** | none | — | Docker/DSN unavailable |

## Contribution classification

| Contribution | Category | Basis |
| --- | --- | --- |
| Supervisor-side, record-level SOC assessment with evidence-cited findings | A — candidate research contribution (application framing), low confidence | [LITERATURE_POSITIONING.md](LITERATURE_POSITIONING.md) |
| Absence-based (negative-space) supervisory checks | A candidate, low confidence; technique known (conformance checking) | same |
| Controlled findings: robustness, ablation, prioritization, peer sensitivity, external association and failure analysis | B — empirical findings (including negative results) | freeze v2 |
| Tenant-aware PostgreSQL/SQLite persistence, versioned submissions, queue and workers | C — engineering contribution | code; PostgreSQL unverified live |
| LangGraph orchestration with review interrupt and recovery | C — engineering/orchestration capability | EXP-O01/O02 |
| TRUST-SAT ML-DSA-65 signed supervisory receipts and hash-chained ledger | D — security/integrity capability | EXP-T01 |
| API/worker deployment topology, smoke test, CI topology job | E — deployment capability | EXP-D01; containers unverified |
| Research bundles, freeze, statistics, table/figure export, expert-label workflow | F — supporting infrastructure | code |

## Wording rules

- Qualify every result with its evidence category ("in controlled synthetic
  scenarios", "on one external IT incident log").
- "detected all tested mutations" — never "tamper-proof".
- "on one machine with SQLite" for every timing.
- No "first", "novel", "outperforms", "state of the art", "scalable".

## Deployment status model

| Capability | CONFIGURED | BUILD VERIFIED | LOCAL DEPLOYMENT VERIFIED | INTEGRATION VERIFIED | HOSTED DEPLOYMENT VERIFIED |
| --- | --- | --- | --- | --- | --- |
| API + worker processes (SQLite, local storage) | yes | n/a | **yes** (EXP-D01, 18/18) | no | no |
| Container images | yes (Dockerfile, CI job) | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Compose topology (PostgreSQL, SeaweedFS, migrate, key-init, API, worker) | yes | NOT EXECUTED | NOT EXECUTED (BLOCKED: no Docker) | NOT EXECUTED | NOT EXECUTED |
| Live PostgreSQL | yes | n/a | NOT EXECUTED (BLOCKED: no DSN) | NOT EXECUTED | NOT EXECUTED |
| Live S3 / SeaweedFS | yes | n/a | NOT EXECUTED | NOT EXECUTED | NOT EXECUTED |
| Hosted API/worker | no | NOT EXECUTED | n/a | n/a | NOT EXECUTED |
