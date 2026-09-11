# Phase 7 — Anomaly Engine

## Goal

Detect *previously unknown* suspicious operational patterns using
**explainable statistics** (median / MAD / IQR / percentiles) over
the entity's own assessment data — no black-box ML.

## Why explainable statistics

A supervisor must be able to verify a finding's math without
reading a model. The AnomalyWorker therefore:

* uses a single, transparent algorithm (the median + k·MAD cutoff),
* records the median, MAD, p10, p90 and the cutoff in
  `processing_metrics`,
* reports the observed value, the baseline (the cutoff the engine
  compared against, written into `threshold`), and a deviation
  `effect` for every emitted `signal` finding.

The MAD=0 case (a degenerate distribution where every record is
equal except one) is handled explicitly: the score collapses to
the raw deviation so it is always finite and sortable.

## The eight metrics

| Metric | Unit | Why it matters |
|---|---|---|
| closure_time | per closed alert (seconds) | an unusually slow closure may be a resource gap |
| investigation_duration | per case (seconds) | a case open much longer than its peers is worth a look |
| alerts_per_asset | per asset (count) | a "hot" asset; a sensor-noise vs. real-incident triage point |
| critical_alerts_per_critical_asset | per critical asset (count) | focused targeting |
| escalation_rate | entity-level (share) | below 30% on critical alerts is itself an outlier |
| recurrence | per case (count) | a single case absorbing many alerts |
| monitoring_coverage | entity-level (share) | < 50% of critical assets alerted |
| investigation_depth | per case (count) | outlier depth (high *or* low) is worth a look |

The current values for *all eight* are reported in
`processing_metrics["metric_sample_sizes"]` so a reviewer can see
whether a "no anomaly" outcome is meaningful or simply had no
data.

## Limitations (Phase 7 → 8)

The baseline is *in-scope* (this assessment's own records).
Cohort benchmarks (Phase 8) replace this with a peer-cohort
baseline. Every emitted `signal` finding carries a
`limitations` string that says so — no finding is presented as
peer-benchmarked when it is not.

## Tests

`tests/test_phase7_satsa_anomaly.py` — 21 tests:

* Pure-function tests for the statistics helpers (`_median`,
  `_mad`, `_percentile`, `_anomalous_outliers`) including the
  MAD=0 / `inf`-score guard.
* True-positive + true-negative + too-few-samples scenarios for
  `closure_time`.
* True-positive scenarios for `investigation_duration`,
  `alerts_per_asset`, `critical_alerts_per_critical_asset`,
  `recurrence`, `monitoring_coverage`, `investigation_depth`.
* True-positive + true-negative for `escalation_rate` (and the
  "don't claim low escalation when escalations wasn't submitted"
  guard).
* Output-shape tests: every emitted `signal` finding carries the
  observed value, baseline, effect, confidence, evidence_refs,
  and a `limitations` string.
* Per-metric sample-size reporting.
* Custom-threshold test (`min_samples=3` flags a 4-alert scope
  with a clear outlier).

The Phase 4/5 worker-set determinism tests were updated to
include the new `anomaly` worker; the existing assertions on
`len(observation_ids)` / `len(jobs)` were bumped to 8.
