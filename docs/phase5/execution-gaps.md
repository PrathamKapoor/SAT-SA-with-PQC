# Phase 5 — Execution Gap Engine

## Goal

Build the first major SIH intelligence capability: detect *execution
gaps* — situations where a CSE's workflow is going through the
motions but not actually doing the work the workflow is supposed to
guarantee.

## The six SIH execution-gap signals

| # | Rule | Worker |
|---|---|---|
| 5.1 | Acknowledged alert without meaningful investigation | `AckWithoutInvestigationWorker` |
| 5.2 | Critical/high/medium alert closed unusually quickly | `FastClosureWorker` (Phase 4) |
| 5.3 | Critical alert closed without escalation | `CriticalWithoutEscalationWorker` |
| 5.4 | Repeated investigation patterns (shallow playbook) | `RepeatedInvestigationWorker` |
| 5.5 | Repeated alerts without remediation evidence | `RecurringWithoutRemediationWorker` |
| 5.6 | Potential metric gaming (high closure, low depth) | `MetricGamingWorker` |

Each worker is a separate module under `satsa/analysis/workers/`,
owning its own configurable thresholds. The default set is
registered (in a fixed order — important for test fixtures) in
`satsa/analysis/run._default_workers`.

## How each signal answers the spec's required questions

Every emitted `Finding` carries:

* **WHAT happened** — the worker-specific `rationale` string
  (e.g. "3/10 investigation steps used the same action_type with
  near-identical notes").
* **WHY it is unusual** — the configurable `threshold`, the observed
  `statistic`, and the `effect = 1 - statistic/threshold` (clamped to
  (0, 1]).
* **WHAT evidence supports it** — every `signal` finding cites
  at least one SourceRecord / step / case id (`evidence_refs`,
  per SIH-EX-02).
* **WHAT should the examiner inspect** — the `limitations` string
  names exactly what the heuristic cannot see (e.g. "a legitimate
  verbal escalation is not visible to the supervisor and will be
  flagged here — confirm via human review before treating as a
  finding").
* **How confident are we** — a `ConfidenceVector` with
  `analytical_support` (how strongly the rule was tripped),
  `evidence_completeness` (share of the eligible data the rule
  saw), and an unset `peer_confidence` (Phase 8 fills this in).

## Signal design choices (per spec)

* *Heuristics, not black-box scores.* Every rule is a single,
  transparent, configurable threshold or two-signal conjunction. The
  threshold is a domain-meaningful number (seconds, count, share),
  not a model weight. The full input and threshold are recorded in
  the `processing_metrics` block of every `ObservationBatch`.
* *The detector's abstention is honest.* `insufficient_data` is a
  distinct state from `no_signal` (a failed-to-run detector vs. one
  that ran and found nothing) per `analytics-architecture.md`.
* *Negative-space is separated.* A never-acknowledged alert is the
  *negative-space engine's* concern (Phase 6), not 5.1. The
  AckWithoutInvestigation worker explicitly excludes
  unacknowledged alerts from its qualifying set.
* *Per-severity thresholds.* The fast-closure and the
  critical-without-escalation rules are per-severity, not global —
  a "fast" close on a `low` alert is normal; on `critical` it is not.

## Tests

`tests/test_phase5_satsa_execution_gaps.py` — 24 tests:

* For each of 5.1 / 5.3 / 5.4 / 5.5 / 5.6: a true-positive, a
  true-negative, a borderline, a missing-data, and a
  conflicting-thresholds scenario (5.2 already has its full suite
  in Phase 4).
* A single end-to-end ground-truth test that ingests a small
  synthetic submission exercising *every* signal, runs the full
  default worker set, and confirms the right combination of
  `rule_or_category` values is persisted (5.6 deliberately
  does not fire on the 4-alert scope — its `min_alerts_for_signal`
  threshold protects small samples).
* A determinism test that pins the default worker registration
  order (any change to that order would be observable to the UI /
  the report and must be intentional).

The Phase 4 tests were updated to reflect the new six-worker
default set (one fast-closure finding + one critical-without-
escalation finding in the minimal two-alert fixture).
