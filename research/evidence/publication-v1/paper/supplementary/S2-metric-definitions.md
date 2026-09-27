# S2. Metric and statistic definitions

## Detection against construction labels (C01, A01)

- **Unit:** a (scenario, finding family) pair. A declared family emitted by
  SAT-SA is a true positive (TP); a declared family not emitted is a false
  negative (FN); an emitted family not declared for that scenario is a false
  positive (FP).
- **Micro precision** = ΣTP / (ΣTP + ΣFP); **micro recall** = ΣTP / (ΣTP + ΣFN);
  **F1** = harmonic mean. Undefined ratios (0/0) are reported as undefined,
  never as 0.
- **Action alignment:** the recommended supervisory action equals the
  scenario's declared action.
- Labels are *construction labels*: they record what a scenario was built to
  contain. Agreement shows the mechanism responds to designed inputs.

## Closure-time detectors (C01)

Unit: one construction-labelled critical closure record (positive = fast).
Baselines (`evaluation/baselines/statistical.py`, called from
`evaluation/baselines/compare.py`):

- fixed threshold: closure time < 600 s;
- MAD: modified z-score |0.6745·(x − median)/MAD| > 3.5 (either direction);
- z-score: |x − mean| / population SD > 2 (either direction);
- IQR: outside Tukey fences [Q1 − 1.5·IQR, Q3 + 1.5·IQR];
- random: a seeded random sample of round(n·p) records, p = positive rate.

Each flags nothing when its dispersion is zero or the sample is too small.

## Prioritization (PR01, X02b)

- For a ranking of N entities and budget k% the top n = max(1, round(k·N/100))
  entities are reviewed (PR01: 2, 4, 6 of 20 at 10/20/30%).
- **precision@k** = relevant in top n / n; **recall@k** = relevant in top n /
  all relevant.
- **NDCG@k** (Järvelin and Kekäläinen 2002) with binary relevance, log2
  discount, normalised by the ideal ordering.
- **Review volume** = rank position of the last relevant entity (entities that
  must be reviewed to find all relevant ones).
- Ties in heuristic baselines are broken by a seeded shuffle; random order is
  summarised by its mean over 200 seeded permutations per population.
- External relevance (X02b): top-quartile SLA-miss rate (12 of 50 groups).

## Robustness (R01b)

- **Validation-contract conformance:** observed validation status equals the
  expectation declared before execution; conditions without a declared
  expectation (staleness) or not applicable to a fixture are excluded.
- **Family set changed:** the set of emitted finding families differs from the
  paired unperturbed control of the same scenario.

## Orchestration (O01, O02)

- **Processing time:** wall-clock seconds of the workflow excluding the human
  decision wait.
- **Outside domain:** processing time not spent in analysis, recommendation or
  finalization stages (queueing, orchestration, persistence).
- **Paired difference:** per-trial difference between modes run on the same
  trial index; summarised by the median, a percentile bootstrap interval and
  counts of pairs where one mode was greater.
- **Recovered:** the interrupted run completed with outputs identical to the
  uninterrupted reference, one decision, one finalization and a verifying
  receipt.

## Integrity (T01)

- **Detected:** verification status `tampered` after a single mutation to
  signed state; the negative control must still verify. Reported as counts of
  tested mutations, not as a detection rate.

## Association (X02b, X03)

- **Spearman ρ** between a group-level score and the group's SLA-miss rate
  (fraction of incidents whose final `made_sla` flag is false), n = 50 groups.

## Statistics policy

Medians; 95th percentiles only for n ≥ 20; seeded percentile bootstrap
(10,000 resamples; 2,000 for Spearman ρ) only for n ≥ 10 independent units;
paired comparisons with higher/equal/lower counts; no p-values; intervals are
descriptive and uncorrected for multiple comparisons. S6 lists n, independent
unit and adequacy for every estimate.
