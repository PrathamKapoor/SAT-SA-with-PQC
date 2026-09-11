# Phase 10 — Review Prioritization

## Goal

Answer the supervisor's first question: **"What should I look at
first?"** — at both the entity and the finding level.

## Two rankings

* `prioritize_entities` — every entity with a most-recent run,
  ranked highest-first.
* `prioritize_findings` — every `signal` finding of a single run,
  ranked highest-first.

## Entity priority score

A simple sum of documented weights, never a hidden model:

```
priority_score = risk_score
              + 10 * confidence_value
              +  5 * recency
              +  2 * high_signal_count
```

* `risk_score` is the Phase 9 per-entity risk (0–100).
* `confidence_value` maps the `confidence_bucket` to
  `{very_low:0, low:0.25, medium:0.6, high:1.0}` so the
  same risk score from a low-confidence run does not jump
  ahead of a high-confidence run.
* `recency` decays linearly over a 30-day window from the run's
  `created_at` timestamp.
* `high_signal_count` is the number of `peer_benchmark.*` and
  `potential_metric_gaming` signal findings on the run.

All weights are documented in
`satsa.analysis.prioritize._priority_score`. Changing them is a
one-line edit, and the *rationale* string every entity carries
quotes the real numbers it was computed from — no fabricated
reasons.

## Per-entity rationale

Every entry in the ranked list carries a `rationale` string of
the form:

```
risk 72/100; confidence medium; top dimensions: execution_gap=24.5, peer_deviation=20.0; 2 high-severity signal(s)
```

The reviewer can read this without opening the UI, and the UI
can render it as a one-line summary with drill-down into the
underlying findings.

## Finding priority

Within a run, every `signal` finding gets a `severity` bucket
(high for `peer_benchmark.*` and `potential_metric_gaming`,
medium for `execution_gap.*` and `anomaly.*`, low for
`negative_space.*`) and a priority score of
`severity_value * (0.5 + confidence.overall)`. The rationale
quotes the dimension + the finding's own `rationale` text — every
priority is evidence-backed.

## Tests

`tests/test_phase10_satsa_prioritize.py` — 13 tests:

* `_severity_of` bucket tests for every rule family.
* `prioritize_entities`:
  - empty when no runs,
  - ranked highest-first,
  - evidence-backed rationale string,
  - `high_signal_count` bumped by peer-deviation findings.
* `prioritize_findings`:
  - empty for unknown run,
  - only `signal` findings returned,
  - evidence-backed rationale,
  - high-severity (peer-deviation) sorts above low-severity
    (negative-space) within the same run,
  - `to_dict()` round-trip.
