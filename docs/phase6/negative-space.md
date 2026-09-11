# Phase 6 — Negative-Space Engine

## Goal

Detect the **absence of evidence that should be there**, while
carefully distinguishing *absence in reality* from *absence from
submission*.

## Why this distinction matters

A CSE that submitted an empty `alerts.csv` and a CSE that did not
submit one at all look the same on the surface — both have zero
alerts in scope. But the supervisory action is completely different:
the first is a finding about the CSE's posture; the second is a
finding about the assessment itself (re-ingest with the missing
file). Conflating them wastes reviewer time and is exactly the
silent misinterpretation the spec warns against.

## Six negative-space rules

| Rule | What it asks | Requires the data to be submitted? |
|---|---|---|
| `negative_space.missing_file.<category>` | Was the category file submitted at all? | (always; this is the rule that reports the absence) |
| `negative_space.missing_investigation` | Are there cases with zero recorded steps? | yes (cases + investigation_steps) |
| `negative_space.missing_escalation` | Are there critical alerts with no escalation? | yes (alerts + escalations) |
| `negative_space.missing_disposition` | Are there closed alerts with no disposition? | yes (alerts + dispositions) |
| `negative_space.missing_monitoring` | Are there critical assets with zero alerts? | yes (assets + alerts) |
| `negative_space.unexpectedly_low_activity` | Critical-asset-heavy inventory with very few alerts | yes (assets + alerts) |

Every rule is honest about the data it needed. Every finding's
`confidence.evidence_completeness` is 0.0 if its data category
was never submitted (the `missing_file.<category>` finding
catches that explicitly).

## The data-completeness map

Every `ObservationBatch.scope["data_completeness"]` is a
`{category: bool}` map of the six SIH input categories so the UI
/ report can show at a glance *what the supervisor can and cannot
judge*. The Phase 5 `ack-without-investigation` worker uses
`dataset.submitted_categories` for the same reason.

## Spec compliance

- **Zero activity alone is not a finding** — verified by
  `test_zero_activity_alone_is_not_a_finding`. A scope with one
  alert and no other categories produces only
  `insufficient_data` findings (the data-completeness layer),
  not `signal` findings.
- **Per-finding `evidence_completeness`** — every
  `signal` finding carries a `ConfidenceVector` whose
  `evidence_completeness` component reflects how much of the
  eligible data the rule actually saw (down to 0.0 if the
  relevant category was never submitted).
- **Configurable thresholds** — `NegativeSpaceThresholds`
  exposes `min_investigation_steps`, `min_alerts_per_critical_asset`,
  `min_critical_assets`, `min_alert_volume_for_low_activity` for
  the per-deployment policy knobs.

## Tests

`tests/test_phase6_satsa_negative_space.py` — 21 tests:

- 1 true-positive + 1 true-negative + 1 data-completeness
  fallback for each of the five conduct rules (missing_*
  categories),
- 1 positive + 1 negative + 1 below-minimum-inventory for the
  "low activity" rule,
- the `zero_activity_alone_is_not_a_finding` spec rule,
- the data-completeness map plumbing,
- a custom-threshold test (lower volume threshold produces a
  finding on smaller samples).

The existing Phase 4 / Phase 5 fixtures were updated to reflect
the seven-worker default set; the test that asserted exactly two
findings now asserts the right subset of rules (including the
new `negative_space.missing_file.cases` rule that correctly
replaces `negative_space.missing_investigation` for a fixtures
that never submitted a `cases` file).
