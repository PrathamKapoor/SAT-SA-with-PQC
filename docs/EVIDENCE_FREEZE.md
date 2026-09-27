# Research Evidence Freeze v1

**Freeze:** `satsa-evidence-freeze-v1`, directory `research/evidence/freeze-v1/`,
created 2026-09-27T03:28:30Z with tool commit `36fc576`, committed in `a3b8137`.
**This is the canonical evidence set for the paper.** Later runs must use new
experiment IDs and a new freeze version; freeze v1 is never edited.

Verify: `python scripts/verify_evidence_freeze.py research/evidence/freeze-v1`
(14 items, intact at creation and in a fresh clone; also enforced by
`tests/test_phase10_evidence_freeze.py`). Regenerate tables and figure data:
`python scripts/export_paper_tables.py --freeze research/evidence/freeze-v1 --out <dir>`
(uses canonical bundles only; rejects any bundle whose manifest or artifacts
differ from the freeze).

## Canonical and non-canonical bundles

Hash columns show the first 16 hex digits; full values are in `freeze.json`.

| Bundle | Role | Experiment | Dataset (id, version, origin) | Seed | Code commit | Source dirty | Manifest SHA-256 | Raw results SHA-256 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| controlled-final-seed-17 (EXP-C01) | canonical | satsa-controlled-supervisory-benchmark | catalog benchmark 1.0.0, synthetic | 17 | 82085d2 | no | 0ad518882d319dd9 | bea7b1527d0f9513 |
| EXP-R01b-evidence-robustness | canonical | satsa-evidence-perturbation-v1 | controlled-evidence-perturbation 1.0, synthetic | 0 | 400f2d6 | no | 8a43c01d982b91a5 | fc6b39beb6fc6568 |
| EXP-O01-orchestration-overhead | canonical | satsa-orchestration-overhead-v1 | controlled-orchestration-mixed 1.0, synthetic | 0 | 698b507 | no | d758a2801f158cc2 | 4d6f556cac639da6 |
| EXP-O02-orchestration-recovery | canonical | satsa-orchestration-recovery-v1 | controlled-orchestration-mixed 1.0, synthetic | 0 | 698b507 | no | ddd3bef48fb22f11 | 02fe625343d48ece |
| EXP-T01-trust-mutation-matrix | canonical | trust-sat-controlled-mutation-v1 | controlled-trust-synthetic-submission 1.0, synthetic | — | 9325fdd | no | f20a5c59cb460491 | 6f7bb986edd064b2 |
| EXP-P01-peer-sweep | canonical | peer-cohort-sweep-v1 | controlled-peer-cohort-sweep 1.0, synthetic | — | 9325fdd | no | 7aa85508062b2b28 | 82f29af3808f33a3 |
| EXP-A01-component-ablation | canonical | satsa-component-ablation-v1 | catalog + generated populations 1.0, synthetic | 300 | 9325fdd | no | 03632678da62b279 | d89c148120a4ec5f |
| EXP-PR01-prioritization-replicated | canonical | satsa-prioritization-replicated-v1 | generated workload populations 1.0, synthetic | 100 | 9325fdd | no | 2d83cefce4326afc | 360ee0062d218bf1 |
| EXP-X02-external-itsm | canonical | satsa-external-itsm-v1 | UCI-498 (2018 release), external benchmark | 0 | 8f63aeb | no | 576e50ea1c67eaf1 | 9707e96afa8b7bf8 |
| EXP-R01-evidence-robustness | superseded | satsa-evidence-perturbation-v1 | as R01b | 0 | e7aedd8 | no | 8f1fdd9e4815e921 | 34a6bbdede3fcc72 |
| evidence-robustness-pilot | superseded | satsa-evidence-perturbation-v1 | as R01b | 0 | ee87026 | no | aec1083548ff5d50 | 29786ff8899e91b9 |
| trust-integrity-final | superseded | trust-sat-controlled-mutation-v1 | as T01 | — | 82085d2 | no | 2a480e8c31648e11 | 77ebfa6df97b0572 |
| peer-sensitivity-final | historical | peer-cohort-sensitivity-v1 | controlled-peer-cohorts 1.0 | — | 82085d2 | no | 55b78749ba919c46 | bc27d4324a3f491b |

Supporting file: `supporting/EXP-D01-local-process-smoke.json` (SHA-256
`29bddd52a5c649b9de6002abd4372c1e9d2b518d3e61e0ecd6119b1257c4debb`) — HTTP
smoke across local API and worker processes (SQLite, local storage), commit
`aa79109`, 18/18 PASS.

External dataset: UCI-498, DOI 10.24432/C57S4H, CC BY 4.0, downloaded
2026-09-27T03:04:04Z, CSV SHA-256
`fd184bbfd62329cfe093e99da2ea7071905f2ead91900b448eb2635870821bef`, adapter
`uci498-adapter/1`. The source file is not stored in the repository (43 MB);
the experiment refuses any file with a different checksum.

## Environment

Windows 11 (10.0.26200), Python 3.13.14, LangGraph 1.2.12, NumPy 2.5.2,
SciPy 1.17.1, SAT-SA 0.16.0, SQLite (all measured runs). Dependency-definition
hashes are recorded in every manifest. Timing runs are single-machine.

## Statistical methods

`evaluation/research/statistics.py`: medians; p95 only for n ≥ 20; seeded
percentile bootstrap intervals (10,000 resamples; 2,000 for Spearman) only for
n ≥ 10; paired comparisons by trial or seed; Spearman ρ with average ranks.
No p-values, no significance claims, no multiplicity correction because no
tests are performed. Randomization baselines are finite seeded permutation
distributions, not confidence intervals.

## Status of every planned evaluation

| Evaluation | Status |
| --- | --- |
| Controlled detection, baselines, robustness, ablation, prioritization, peer, integrity, orchestration, recovery | IMPLEMENTED · EXECUTED · MEASURED · REPRODUCIBLE (freeze v1) |
| External dataset (UCI-498 IT incident log) | IMPLEMENTED · EXECUTED · MEASURED · REPRODUCIBLE (partial external evidence; not SOC) |
| External datasets GUIDE, CIC-IDS2017, BOTS | NOT EXECUTED — unsuitable for workflow detectors and BLOCKED for download ([EXTERNAL_DATASETS.md](EXTERNAL_DATASETS.md)) |
| HTTP end-to-end, local processes (SQLite) | EXECUTED · MEASURED (EXP-D01) |
| Live PostgreSQL | IMPLEMENTED · NOT EXECUTED · BLOCKED: `SATSA_TEST_POSTGRES_DSN` unavailable |
| Containers / compose topology / SeaweedFS / HTTP through containers | IMPLEMENTED (CI job) · NOT EXECUTED · BLOCKED: Docker not installed; CI not run (no push authorized) |
| PostgreSQL vs SQLite and container vs local performance | NOT EXECUTED · BLOCKED by the two items above |
| Hosted API/worker deployment | NOT EXECUTED |
| Expert labels | PROTOCOL/INGESTION READY · NOT EXECUTED (no labels exist) |
| Human review study | PROTOCOL READY · NOT EXECUTED |

## Known limitations

See [RESEARCH_LIMITATIONS.md](RESEARCH_LIMITATIONS.md). Headline negative
results preserved in this freeze: stale and contradictory records accepted
silently (R01b); closure-speed heuristic comparable to SAT-SA on synthetic
populations (PR01) and baselines tied on the closure corpus (C01); detector
saturation and no association with SLA-miss rate on real external data (X02);
peer behaviour strongly dependent on cohort composition (P01).
