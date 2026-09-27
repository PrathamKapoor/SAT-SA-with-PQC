# Research Evidence Freeze

## Freeze v2 — canonical for the paper

**Freeze:** `satsa-evidence-freeze-v2`, directory `research/evidence/freeze-v2/`,
created 2026-09-27T05:54:24Z with tool commit `837d1ef`,
committed in `85b7763`. `freeze.json` SHA-256
`2ac93ef3f2967f908c35b05c1fed97dc60282aa503d1a97594275deae3a1ff0a`.
Catalog: `research/evidence/catalog.json` (generated from this freeze and
`catalog-spec.json`; SHA-256 `16c60059668c36890dd656eda52eb75c2e2293ba352f39ffcfca5ecf64c27070`).
Freeze v1 is unchanged and still verifies; v2 differs by making **EXP-X02b**
canonical (X02 superseded, bookkeeping only), adding **EXP-X03** and the
dataset suitability matrix, and exporting the statistical audit.

| Bundle | Role | Code commit | Manifest SHA-256 |
| --- | --- | --- | --- |
| controlled-final-seed-17 | canonical | 82085d2 | `0ad518882d319dd9136b57462f216024f780d89af686c8248864ed58b2449637` |
| EXP-R01b-evidence-robustness | canonical | 400f2d6 | `8a43c01d982b91a5e05ac5044e50c2164395aa8ca5360ed88c19543afb946709` |
| EXP-O01-orchestration-overhead | canonical | 698b507 | `d758a2801f158cc26cc0c9342062bf6656dc05359b9944b5a9ed278a601f2b84` |
| EXP-O02-orchestration-recovery | canonical | 698b507 | `ddd3bef48fb22f110d4c5f85534dd5bc2eea0cb975444f1ba9dee2aa309b064c` |
| EXP-T01-trust-mutation-matrix | canonical | 9325fdd | `f20a5c59cb4604919174e28d46ad52e060b67820953e7baccf4d86c1f722e0fc` |
| EXP-P01-peer-sweep | canonical | 9325fdd | `7aa85508062b2b28519f157a64dcf2692b43dcf50b9264bf308888bcbefe5e54` |
| EXP-A01-component-ablation | canonical | 9325fdd | `03632678da62b27940702b8ec11cfbee726d62f199762f7093e0b5d93a445ff4` |
| EXP-PR01-prioritization-replicated | canonical | 9325fdd | `2d83cefce4326afc7549b9386567fd803ebf6dcde97d03b189ae13d7d9222c75` |
| EXP-X02b-external-itsm | canonical | c1206dd | `036652ed89089874a31689354c0ddac26e4140e0f4e7b774f4341408a4d9b9d0` |
| EXP-X03-external-failure-analysis | canonical | c1206dd | `10229533540e0ec189daba065ef3dae96a404a9842076caacbb61e12de8c8182` |
| EXP-X02-external-itsm | superseded | 8f63aeb | `576e50ea1c67eaf16149737df20df6e4676968a72d96746468f84ce188cb4b05` |
| EXP-R01-evidence-robustness | superseded | e7aedd8 | `8f1fdd9e4815e92167c051c06531b31ef6ee88cac2e846af92124a59acc063e9` |
| evidence-robustness-pilot | superseded | ee87026 | `aec1083548ff5d50d5d3baa567a88dc7d58e54eb4ce4d5fbd1aebceb05edcbe1` |
| trust-integrity-final | superseded | 82085d2 | `2a480e8c31648e11dfc2180d5d7e533510cc016c11670dfbe4f0cb2ef8ebfff4` |
| peer-sensitivity-final | historical | 82085d2 | `55b78749ba919c46fa430c3ed7b7117f477c03693696ba8daa2e328f52bb720c` |

| Supporting file | SHA-256 |
| --- | --- |
| supporting/EXP-D01-local-process-smoke.json | `29bddd52a5c649b9de6002abd4372c1e9d2b518d3e61e0ecd6119b1257c4debb` |
| supporting/dataset-suitability.json | `c250e488eb1834b2f96dbe99909fd235b71edebea0f2a3a877ea115f1e8e5c2d` |

### Verification drill (2026-09-27, fresh clone of `85b7763`)

| Step | Result |
| --- | --- |
| `verify_evidence_freeze.py research/evidence/freeze-v2` | intact, 17 items checked |
| regenerate exports and compare with committed `freeze-v2/exports` | 81 files each, 0 differing (byte-identical) |
| edit `manifest.json` of EXP-X02b | verify exit 1: "manifest.json differs from the frozen manifest hash"; export skipped the bundle |
| edit `raw/results.json` | verify exit 1: "raw/results.json hash mismatch"; export skipped |
| edit `processed/metrics.json` | verify exit 1: "processed/metrics.json hash mismatch"; export skipped |
| edit `config.json` | verify exit 1: "config.json hash mismatch", "config.json does not match configuration_sha256"; export skipped |
| restore file | intact again |

Also enforced by `tests/test_phase10_evidence_freeze.py` and
`tests/test_phase11_publication.py`.

---

## Freeze v1 (history)

**Freeze:** `satsa-evidence-freeze-v1`, directory `research/evidence/freeze-v1/`,
created 2026-09-27T03:28:30Z with tool commit `36fc576`, committed in `a3b8137`.
**It was canonical until freeze v2 (above) superseded it; it is kept unchanged as history.** Later runs must use new
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
