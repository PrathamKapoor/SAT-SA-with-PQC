# Phase 9 — Entity Risk Engine

## Goal

Aggregate a run's findings into an **explainable, decomposable**
per-entity risk profile: a single number the supervisor can use to
prioritize, with a tree showing exactly which dimensions
contributed which scores and which findings drove each dimension.

## The decomposition contract

A risk profile is never a single number — it is a tree:

```text
Total: 82 (high confidence)
├── execution_gap       24/25
│   ├── finding_a…
│   ├── finding_b…
│   └── finding_c…
├── peer_deviation      20/20
│   └── finding_d…
├── detection_gap       14/15
│   └── finding_e…
├── negative_space      12/15
│   └── finding_f…
├── anomaly               8/15
│   └── finding_g…
├── investigation_quality 4/5
└── escalation_discipline 0/5
```

Every leaf links to a `Finding` by id; every node carries its
weight and a rationale describing its top contributors.

## Dimension weights

| Dimension              | Weight | Rationale |
|------------------------|--------|-----------|
| `execution_gap`        | 25     | The SIH core signal class (5.1–5.6); directly tested in the spec. |
| `peer_deviation`       | 20     | Externally anchored; hardest for a CSE to dismiss. |
| `detection_gap`        | 15     | Missing monitoring/alerting is a system-level risk. |
| `negative_space`       | 15     | Absence of expected evidence is the spec's 6th category. |
| `anomaly`              | 15     | In-scope outliers, complementary to peer deviation. |
| `investigation_quality`|  5     | Shallow-playbook signals; important but tactical. |
| `escalation_discipline`|  5     | Single-rule dimension; supplements `execution_gap`. |
| **total**              | **100**| |

The weights are documented in `satsa.analysis.risk.DIMENSION_WEIGHTS`
and are included in every persisted profile so a reviewer can
see what the score was computed with. Changing a weight is a
one-line edit.

## Scoring math

For each dimension, the raw confidence of the contributing
`signal` findings is summed (a single very-high-confidence finding
contributes ~1.0, a 5-finding dimension at 0.7 confidence each
contributes ~3.5). The dimension score is then

```
score = weight * (1 - 1 / (1 + raw))
```

which saturates at the weight (a single dimension can never
exceed its weight, no matter how many findings), and gives a
*diminishing* return for additional findings (so a 1-finding
dimension and a 5-finding dimension are different but not
arbitrarily different).

The total is the sum of dimension scores, capped at 100 (=
sum of weights).

## Confidence bucket

The profile carries a `confidence_bucket` in
`{very_low, low, medium, high}` derived from the average
`confidence.overall` of the contributing signal findings, so the
UI can show "82 (high confidence)" not just "82".

## Tests

`tests/test_phase9_satsa_entity_risk.py` — 16 tests:

* Pure-function tests for `_dimension_for` (every rule prefix
  bucket), `_confidence_overall` (handles missing/malformed JSON),
  `_confidence_bucket` (boundary values).
* Integration through a real `RunService.run` + a real
  `SatsaService.compute_risk` for:
  - an entity with no runs (zero score, no run_id),
  - a scope with only execution-gap findings (only that
    dimension is non-zero),
  - a scope with peer-deviation findings (peer_deviation
    dimension non-zero),
  - a heavily-loaded scope (total capped at 100),
  - the tree-shaped `decomposition()` output,
  - per-dimension `finding_ids` linking back to real
    `satsa_findings` rows,
  - a specific `run_id` honored (not always "the latest"),
  - the persisted `weights` field equals `DIMENSION_WEIGHTS`,
  - every dimension carries a rationale, including the
    "no findings in this dimension" case,
  - the confidence bucket is one of the four defined values.
