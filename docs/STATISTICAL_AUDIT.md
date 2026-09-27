# Statistical Audit (freeze v2)

Generated rows: `research/evidence/freeze-v2/exports/statistical_audit.{csv,md,tex}`
and `statistical-audit.json` (built by `evaluation/research/audit.py` from the
canonical bundles; no typed numbers). This page summarises them.

**Policy.** Medians; p95 only for n ≥ 20; seeded percentile bootstrap intervals
(10,000 resamples; 2,000 for Spearman ρ) only for n ≥ 10; comparisons paired
by trial or seed where the design pairs them; no p-values and no
significance claims; no multiplicity correction because no tests are
performed — intervals are therefore descriptive and uncorrected.

## Trial count is not independent sample count

| Experiment | Reported n | What n counts | Actual independent units | Consequence |
| --- | --- | --- | --- | --- |
| C01 detection | 5 | authored scenarios (12 scenario-family pairs) | 5 authored scenarios | descriptive only |
| C01 closure baselines | 12 | construction-labelled records (3 positive) | 12 records from one construction | descriptive; ties at F1 1.0 |
| C01 workload | 1 population | 25 random permutations are a comparator distribution | 1 population | superseded in scope by PR01 |
| R01b robustness | 245 conditions | perturbations of 5 fixtures | 5 fixtures | conformance count, not a rate |
| R01b omission | 25 per rate | 5 scenarios × 5 omission seeds (seeds change which records are removed) | 5 fixtures | descriptive counts |
| O01 overhead | 30 pairs | repeated runs on one machine, rotated order | 1 machine / 1 fixture | intervals describe run-to-run variability only |
| O02 recovery | 36 runs | 6 points × 2 modes × 3 deterministic repeats | 12 cells | mechanism check, not a failure rate |
| T01 integrity | 14 mutations | mutation classes on one workflow | 1 workflow | not a detection rate |
| P01 peer | 96 cells | engineered deterministic grid (49 emit a finding) | none (designed grid) | mechanism map |
| A01 scenario | 5 | scenarios × 16 ablated worker sets | 5 scenarios | descriptive |
| A01 population | 5 seeds | paired full vs ablated per seed | 5 populations | exploratory; no intervals (n < 10) |
| PR01 prioritization | 20 seeds | generated populations; random = mean of 200 permutations per seed | 20 populations (same generator) | intervals reported; 27 comparisons uncorrected |
| X02b external | 50 groups | assignment groups of one organisation | 1 organisation | group-level association only |
| X03 diagnostic | 50 groups | as X02b; 12 correlations | 1 organisation | diagnostic, not a claim of effect |

## Key estimates with intervals

| Comparison | n | Estimate | 95% interval | Reading |
| --- | --- | --- | --- | --- |
| Graph − direct processing time (O01) | 30 paired runs | +0.096 s | −0.020 to +0.211 | includes zero on this machine |
| Graph − direct time outside domain stages (O01) | 30 | +0.059 s | +0.057 to +0.061 | consistent orchestration cost on this machine |
| Graph − direct database calls (O01) | 30 | +38 | 38 to 38 | deterministic |
| Reviewed/finalized − unreviewed processing (O01) | 30 | +0.318 s | +0.176 to +0.569 | review + TRUST-SAT finalization cost |
| SAT-SA − random, recall@20% (PR01) | 20 seeds | +0.59 | +0.41 to +0.60 | higher in all 20 populations |
| SAT-SA − alert volume, recall@20% (PR01) | 20 | +0.40 | +0.30 to +0.60 | higher in all 20 |
| SAT-SA − fastest closure, recall@20% (PR01) | 20 | 0.00 | 0.00 to +0.20 | 8 higher, 11 equal, 1 lower |
| SAT-SA risk vs SLA miss, Spearman ρ (X02b) | 50 groups | −0.11 | −0.42 to +0.21 | no association |
| Slowest median resolution vs SLA miss (X02b) | 50 | 0.94 | 0.86 to 0.97 | strong (timeliness construct) |
| Fast-closure prevalence vs SLA miss (X03) | 50 | −0.70 | −0.82 to −0.52 | construct inversion |

## Adequacy

Only PR01 (20 independent populations from one generator) and the O01 timing
series (30 paired runs, one machine) have n ≥ 20; neither supports
generalisation beyond its generator or machine. No experiment supports a
confirmatory inferential claim. Adding p-values would not change that and is
not done.
