# P33 Measured Report — Controlled Benchmark + Air-Gap Rehearsal

> **Limitations first (this document reports only the run below).**
> Everything here was measured on **synthetic, controlled scenarios**
> — deterministic single-entity fixtures, a seeded generator
> population, and construction-labeled closure times. This is **NOT**
> real SOC/CSE/NCIIPC validation, **NOT** CIC-IDS2017/BOTS processing,
> and **NOT** a target-machine deployment. Five of ten catalog
> scenarios are honestly `not_executed` in single-entity fixtures.
> Full boundary: `docs/CONTROLLED_BENCHMARK.md`, `docs/CLAIMS.md`.

## Environment (actual run)

| Item | Value |
|---|---|
| Benchmark | satsa-controlled-supervisory-benchmark v1.0.0 |
| Python | 3.13.14 |
| Platform | Windows-11-10.0.26200-SP0 (development host) |
| SAT-SA | 0.16.0-phase52-ui (package `qsmlops` 0.1.0) |
| Workload seed | 42 (population 10, 4 pathological; 200 random trials) |
| Pipeline runs executed | 5 scenario + 10 population + 18 ablation = 33 real full-pipeline runs |
| Total runner duration | ~22 s |

Machine-readable results: `controlled-benchmark-results.json`
(command in `docs/CONTROLLED_BENCHMARK.md`). Determinism is enforced
by fixed seeds and proven by
`tests/test_phase88_controlled_benchmark.py::test_runner_is_deterministic_for_fixed_seed`
(two full runs produce identical `metrics`).

## A. Scenario corpus (declared catalog labels, real pipeline)

Coverage: **5 executed / 5 not_executed** (anomaly-rate, peer-deviation,
borderline, noisy, conflicting-evidence — documented single-fixture
reasons; not scored as zero).

Corpus micro (family level): tp=5, fp=7, fn=0 →
**precision 0.4167, recall 1.0, F1 0.5882**.

| Scenario | Expected family(ies) | Detected | Extra emitted | Action |
|---|---|---|---|---|
| healthy | (none) | none emitted | none | SURFACE ✓ |
| eg-fast-closure | execution_gap.fast_closure | ✓ | execution_gap.recurring_without_remediation | INSPECT ✓ |
| ns-missing-investigation | negative_space.missing_investigation | ✓ | none | INSPECT ✓ |
| mixed | execution_gap.fast_closure, negative_space.missing_monitoring | both ✓ | coverage_gap, recurring, 3× peer_benchmark | **SURFACE ✗ (expected REQUEST_EVIDENCE — measured miss)** |
| missing-evidence | evidence_completeness.missing_categories | ✓ | negative_space.missing_disposition | REQUEST_EVIDENCE ✓ |

Action alignment: **4/5 (0.8)**. All expected families were detected
(recall 1.0); the 7 extra family emissions are cross-detector side
effects on fixtures whose catalog does not declare family exclusivity
(each listed in the results file); the mixed-scenario action mismatch
is reported as a miss, not explained away.

## B. Closure-time baselines (labels by construction; 12 records, 3 positive)

| Detector | tp | fp | fn | tn | precision | recall |
|---|---|---|---|---|---|---|
| **SAT-SA FastClosureWorker** | **3** | **0** | **0** | **9** | **1.0** | **1.0** |
| MAD | 3 | 0 | 0 | 9 | 1.0 | 1.0 |
| fixed_threshold (600s) | 3 | 0 | 0 | 9 | 1.0 | 1.0 |
| random (seeded) | 1 | 2 | 2 | 7 | 0.33 | 0.33 |
| z-score | 0 | 0 | 3 | 9 | — | 0.0 |
| IQR | 0 | 0 | 3 | 9 | — | 0.0 |

Read honestly: on this deliberately small corpus the SAT-SA worker and
two baselines tie at perfect separation; z-score/IQR miss the narrow
low-tail fast closures (their distributional assumptions absorb 3
outliers of 12). "—" marks undefined ratios, never zero. This corpus
is too small for any superiority claim — the section demonstrates
mechanics and honest comparison, not dominance.

## C. Prioritization (simulated workload experiment — real pipeline, synthetic labels)

| K (top %) | SAT-SA recall@K | Random mean (200 trials) | Lift |
|---|---|---|---|
| 10 | 0.25 | 0.0975 | 2.56x |
| 20 | 0.50 | 0.1988 | 2.52x |
| 50 | 0.75 | 0.52 | 1.44x |

Review volume to find all 4 pathological entities: SAT-SA order 6 vs
random mean 8.65. Explicitly labeled `simulated_workload_reduction` —
not a claim about real analyst time saved.

## D. Ablation (real RunService, one worker removed at a time, 'mixed' scope)

7 finding families emitted with all 16 workers. Workers with unique,
non-overlapping family contributions on this scope:
`fast-closure`, `recurring-without-remediation`, `negative-space`,
`peer-benchmark` (3 peer families), `coverage-gap`. The remaining 11
default workers lost no family here — reported as measured fact (a
worker with no unique loss on one scope is not thereby useless, per
`evaluation/ablation/runner.py`).

## E. Air-gap rehearsal (same-host, offline by construction)

Tool: `scripts/airgap_rehearsal.py`. Bundle: 41 wheels built on this
host (`pip download`, a build-time step). Every install command used
`--no-index --find-links <bundle>` — network unreachable by flags.

| Check | Result |
|---|---|
| wheelhouse_present (41 wheels, all runtime requirements matched) | pass |
| venv_created | pass |
| install_requirements (--no-index) | pass |
| install_project (--no-index, --no-deps, non-editable) | pass |
| imports_from_site_packages (neutral cwd; satsa/qsmlops resolved from venv, not source) | pass |
| cli_version (`sat-sa --version` → 0.16.0-phase52-ui) | pass |
| doctor (fresh temp DB/keys; real ML-DSA roundtrip, DB migrate, write probes, offline posture) | pass (16/1/0 — expected HSM WARN) |
| demo (committed synthetic data) | pass |
| validate (synthetic ground-truth validation) | pass |
| offline_install_posture | pass |

**Overall: pass — same-host rehearsal scope.** This proves the offline
install/run path works with PyPI unreachable. It is **not** a
deployment on an independent air-gapped target machine and must not be
cited as NCIIPC deployment proof (no target rehearsal has been run as
of this report).

## Reproduce

```bash
python scripts/run_controlled_benchmark.py --out <dir>      # benchmark
python scripts/airgap_rehearsal.py --wheelhouse <dir> --out <dir> --keep
```
