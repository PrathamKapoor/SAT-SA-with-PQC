# Phase 8 — Peer Benchmarking

## Goal

Compare comparable CSEs (no blind cross-entity comparison) and
surface deviations in closure, investigation, escalation, alert
volume, coverage, recurrence and other supported metrics.

## Peer groups

A peer group is defined by exact match on the two cohort
attributes the `Entity` already carries:

* `sector` (e.g. `defence`, `finance`, `healthcare`)
* `environment_class` (e.g. `on-prem`, `cloud`, `hybrid`)

The extensible `cohort_attributes` dict is reserved for
deployment-specific group refinement; the default
`_cohort_key` ignores it so a CSE is never silently dropped from
its sector cohort by missing metadata.

A peer baseline requires at least `min_peers` (default 3) entities
in the same cohort. Below that, the worker returns
`insufficient_data` rather than fabricating a comparison from one
or two peers.

## The seven peer-benchmarked metrics

| Metric | Computed from | What a deviation usually means |
|---|---|---|
| `critical_closure_median_seconds` | closed critical alerts | "fast closure" vs peer median |
| `critical_closure_rate` | closed / total critical alerts | very high rate (potential gaming) or very low (workflow gap) |
| `escalation_rate` | critical alerts with an escalation / total | unusually low (the `critical-without-escalation` worker's peer-anchored version) |
| `investigation_depth_median` | investigation steps per case | unusually shallow or unusually deep work |
| `recurrence_median` | alerts linked to each case | a single case absorbing many alerts vs peers |
| `monitoring_coverage` | critical assets with any alert / total | the negative-space signal, peer-anchored |
| `alerts_per_critical_asset` | alerts per critical asset | an unusually hot or quiet critical asset |

Each metric is computed the same way for the subject and for every
peer (see `satsa.analysis.workers.peer_benchmark._assessment_metrics`),
then aggregated across the peer cohort into `{median, mad, p25,
p75, count}` per metric.

## Deviation rule

For every metric, the entity's value is compared against the peer
median in MAD units. A deviation ≥ `mad_k` (default 2.0) produces
a `signal` finding. Smaller deviations are not signalled — a
peer cohort has noise, and a 2-MAD cutoff is the same conservative
heuristic most published anomaly-detection literature uses.

The MAD=0 case (every peer has the same value) is handled by
falling back to the raw deviation so the comparison is still
finite and well-defined.

## Output shape

Every `peer_benchmark.<metric>.deviation` finding carries:

* `statistic` — the subject's observed value (e.g. `30.0` for 30-second median closure)
* `threshold` — the peer median (e.g. `300.0`)
* `effect` — the deviation in MAD units (positive = subject higher, negative = subject lower)
* `confidence.peer_confidence` — `min(1.0, peer_count / 10)`. The Phase 7
  workers leave this `None`; the peer-benchmark worker is the one
  that fills it in. The spec's "94%" example is *notional* — the
  engine reports a real number from a real peer count.
* `evidence_refs` — the subject's own source record pointers (per
  SIH-EX-02: a `signal` finding must cite at least one source
  record; the peer-benchmark is a population-level signal but the
  comparison was made on the subject's records, so those records
  are the evidence anchors).
* `limitations` — names the peer count, the cohort key, and
  reminds the reviewer that the confidence figure is a
  cohort-size-scaled number, not a measured probability.

The `ObservationBatch.scope["peer_metrics_summary"]` carries a
per-metric `{median, count}` view so the UI can render the
"observed / peer / deviation" comparison chart without a second
database round-trip.

## Where the baseline comes from

The `RunService.run` method automatically calls
`compute_peer_baseline(engine, entity_id, min_peers=...)` once per
run, for any `PeerBenchmarkWorker` in the worker set, and attaches
it to the worker via `attach_baseline` (the worker contract does
not currently carry a baseline *data* channel — the function-name
suggests a future widening). The baseline is computed against the
most-recent assessment of every other entity in the cohort.

## Tests

`tests/test_phase8_satsa_peer_benchmark.py` — 12 tests:

* `_cohort_key` + `_aggregate_peer_metric` (pure-function tests).
* `compute_peer_baseline` against a real engine:
  - empty cohort (no peers),
  - mismatched-cohort exclusion (different sector),
  - matching-cohort inclusion (same sector + env),
  - aggregation of the seven metrics across real peer entities.
* `PeerBenchmarkWorker` with a hand-built baseline:
  - `signal` when the subject deviates ≥ 2 MADs,
  - `no_signal` when within tolerance,
  - `insufficient_data` when `peer_count < min_peers`,
  - the spec-style output (4.2-min observed vs 38.7-min peer)
    produced end-to-end with real numbers + a non-`None`
    `confidence.peer_confidence`.
* End-to-end: 4 peers + 1 subject, default worker set, run
  produces a real `peer_benchmark.<metric>.deviation` finding
  whose `statistic` and `threshold` are the actual numbers.

The existing Phase 4/5 fixtures were updated to reflect the
9-worker default set.
