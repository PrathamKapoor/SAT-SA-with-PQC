# Phase 4 — Analysis Run Engine + First Worker

## Goal

Run **multiple analytical workers consistently** over one frozen
`CanonicalDataset` and persist the result so the rest of the
supervisory product (UI, peer comparison, risk, human review, reports)
can build on it.

## What was added

- **Migration 7** — `satsa_analysis_tables`: `satsa_runs`,
  `satsa_observations`, `satsa_findings`, `satsa_jobs` (with indexes
  on the common scope lookups).
- **Contract widening** — `AnalyticalWorker.evaluate()` and
  `Orchestrator.run()` now take the resolved `CanonicalDataset`
  alongside the `SnapshotRef` (Phase 2 deliberately deferred
  resolution; Phase 4 resolves it). `EchoWorker` / `CrashingWorker`
  signatures updated to match.
- **ObservationBatch validation tightening** — `ObservationBatch.validate()`
  no longer recursively calls `Finding.validate()`. Findings arrive
  with `observation_id=""` by design (the persistence layer back-fills
  it once the `Observation` row exists); recursive validation would
  reject every `signal` finding. The persistence layer runs
  `Finding.validate()` again after the back-fill (see
  `RunService.run`).
- **Analysis package** —
  - `satsa.analysis.repository` — `RunStore`, `ObservationStore`,
    `FindingStore`, `JobStore`, `SourceRecordRefStore` (typed row
    access + content digest on every insert, matching Phase 2's
    convention).
  - `satsa.analysis.run.RunService` — the glue: load the dataset,
    create the `AnalysisRun`, run every registered worker through
    the existing `Orchestrator`, persist run/observations/findings/
    jobs in a single transaction. The run's status is derived from
    job outcomes (`completed` / `partial` / `failed`).
  - `satsa.analysis.workers.fast_closure.FastClosureWorker` — the
    first execution-gap detector (Part H "Closure time" /
    SIH-REQ-3). Per-severity, configurable thresholds, multi-dim
    confidence vector, per-finding `SourceRecord` references, no
    black-box score.
- **SatsaService** — gained `run_analysis()` as a thin facade over
  `RunService.run`.

## Entry point

```python
from satsa.service import SatsaService
from satsa.analysis.workers.fast_closure import (
    FastClosureWorker, FastClosureThresholds,
)

service = SatsaService(database)
result = service.run_analysis(
    entity_id, assessment_id,
    thresholds=FastClosureThresholds(
        critical_max_seconds=600,
        high_max_seconds=1800,
        medium_max_seconds=3600,
        absolute_floor_seconds=30,
        min_count_per_severity=1,
    ),
)
# result.run_id, result.status, result.observation_ids,
# result.finding_ids, result.jobs, result.error
```

Or, to plug in custom workers:

```python
from satsa.contracts.worker import EchoWorker
result = service.run_analysis(
    entity_id, assessment_id,
    workers=[FastClosureWorker(), MyCustomWorker(), EchoWorker()],
)
```

## Worker contract

```python
class AnalyticalWorker(ABC):
    name: str
    version: str

    @abstractmethod
    def evaluate(
        self,
        snapshot: SnapshotRef,
        dataset: CanonicalDataset,
        baselines: list[BaselineRef],
        policy: Optional[PolicyRef],
        run_context: RunContext,
    ) -> ObservationBatch: ...
```

Findings are domain records (state ∈ `signal` / `no_signal` /
`insufficient_data` / `not_applicable` / `error`). A worker that
finds nothing is `no_signal`; a worker that was not actually run
(missing data) is `insufficient_data`. A `signal` finding must
cite at least one `SourceRecord` (SIH-EX-02) and carry a
`ConfidenceVector` (analytical_support / evidence_completeness /
optional peer_confidence).

## First worker — FastClosureWorker

For each severity tier (critical / high / medium) with at least one
alert closed in under the configured SLA (and above the absolute
floor):

- emits one `signal` finding per severity,
- with the median close time as the statistic, the threshold as the
  threshold, and `effect = 1 - median/threshold` (clamped to (0, 1]),
- a `ConfidenceVector` with `analytical_support = 0.4 + 0.6·effect`
  and `evidence_completeness = qualifying / total_at_severity`,
- per-finding `evidence_refs` (SourceRecord IDs from the originating
  alerts),
- a `limitations` string that documents the heuristic nature and
  calls out the cohort-benchmarking gap that a later phase closes.

Alerts with `mapped_severity == "unknown"` are excluded by design
(the system did not classify them, the worker should not raise
findings on data it does not understand). Closure times below the
`absolute_floor_seconds` are also excluded (a 5-second close is
likely an auto-closure, not a supervisory gap).

## Tests

`tests/test_phase4_satsa_analysis_run.py` — 15 tests covering:

- FastClosureWorker unit cases: normal (no signal), suspicious
  (signal), threshold boundary (below signals, at threshold does
  not), absolute floor exclusion, missing data, multiple severities
  → multiple findings, unknown severity excluded, determinism,
  baseline/policy not used in Phase 4 (left for Phase 8).
- RunService integration: persists `AnalysisRun` / `Observation` /
  `Finding` / `Job`; re-runs create new runs; failing workers don't
  crash the run; observation_id back-fill into findings; custom
  thresholds honoured.
- The existing `tests/test_phase2_satsa_orchestration.py` tests
  were updated to the widened `evaluate()` / `run()` signatures.

## Result

- Phase 4 test file: 15/15 passed.
- Full regression: 569 passed (was 554), 17 skipped, 0 failed.
- Repository remains runnable; no debug code, no temporary files,
  no secrets introduced.
