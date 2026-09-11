"""Fast-closure detection: critical/high alerts closed in an unusually
short time. The first execution-gap worker (Part H "Closure time",
SIH-REQ-3 "unusually fast closure of critical alerts").

This is intentionally a *single, transparent, configurable rule* — not
a black-box score. Every emitted finding carries:

* what was observed (the alert + the seconds-to-close),
* the threshold it was compared against,
* the configured deviation that produced the signal,
* a multi-dimensional confidence vector (analytical support +
  evidence completeness), and
* a SourceRecord pointer back to the original submission row.

The threshold policy is a plain dataclass; the orchestrator passes it
through via the worker constructor. A future phase (peer benchmarking)
can swap the constant thresholds for ones derived from a cohort
baseline — the rest of the worker is unchanged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from satsa.analysis.repository import SourceRecordRefStore
from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)
from satsa.domain.evidence import (
    ConfidenceVector,
    Finding,
    SourceRecord,
)
from satsa.domain.workflow import Alert


@dataclass(frozen=True)
class FastClosureThresholds:
    """Maximum allowed close-time (seconds) before an alert's closure
    becomes 'unusually fast' for its severity. Defaults are deliberately
    conservative — they are operational SLAs, not measurements of what
    is possible. Override at construction time, never mutate, never
    bake into the worker."""

    critical_max_seconds: float = 600.0     # 10 minutes
    high_max_seconds: float = 1800.0       # 30 minutes
    medium_max_seconds: float = 3600.0      # 1 hour
    # Below this we will not emit (a 5-second close *might* be valid for
    # an obvious benign auto-closure; not the worker's place to flag it).
    absolute_floor_seconds: float = 30.0
    # Minimum count of qualifying alerts at a given severity before we
    # report a single (entity-level) finding — protects against firing
    # on a single quirky data point.
    min_count_per_severity: int = 1


DEFAULT_FAST_CLOSURE_POLICY = FastClosureThresholds()


def _threshold_for(severity: str, t: FastClosureThresholds) -> float:
    return {
        "critical": t.critical_max_seconds,
        "high": t.high_max_seconds,
        "medium": t.medium_max_seconds,
    }.get(severity, math.inf)


class FastClosureWorker(AnalyticalWorker):
    """Detect critical/high/medium alerts closed faster than the configured
    SLA. Each severity produces at most one finding per run (aggregated over
    the entity's full assessment scope), or a `no_signal` finding."""

    name = "fast-closure"
    version = "0.1.0"

    def __init__(self, thresholds: FastClosureThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_FAST_CLOSURE_POLICY

    # ------------------------------------------------------------------

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        if not dataset.alerts:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "alerts_total": 0},
                state="insufficient_data",
                processing_metrics={"reason": "no alerts in scope"},
            )

        # Index alerts by id for source-record lookup; collect per-severity
        # qualifying alerts. Severity "unknown" is intentionally excluded:
        # we do not raise findings on data the system could not classify.
        by_id = {a.id: a for a in dataset.alerts}
        per_sev_qualifying: dict[str, list[Alert]] = {}
        per_sev_total: dict[str, int] = {}
        per_sev_close_times: dict[str, list[float]] = {}
        ineligible = 0

        for a in dataset.alerts:
            if a.mapped_severity not in ("critical", "high", "medium"):
                ineligible += 1
                continue
            if a.closed_at is None or a.time_to_close is None:
                continue
            per_sev_total[a.mapped_severity] = per_sev_total.get(a.mapped_severity, 0) + 1
            per_sev_close_times.setdefault(a.mapped_severity, []).append(a.time_to_close)
            threshold = _threshold_for(a.mapped_severity, self.thresholds)
            if a.time_to_close < self.thresholds.absolute_floor_seconds:
                continue
            if a.time_to_close < threshold:
                per_sev_qualifying.setdefault(a.mapped_severity, []).append(a)

        findings: list[Finding] = []
        any_signal = False
        for severity in ("critical", "high", "medium"):
            qualifying = per_sev_qualifying.get(severity, [])
            if not qualifying:
                continue
            if len(qualifying) < self.thresholds.min_count_per_severity:
                continue
            any_signal = True
            threshold = _threshold_for(severity, self.thresholds)
            close_times = sorted(a.time_to_close for a in qualifying if a.time_to_close is not None)
            median = close_times[len(close_times) // 2] if close_times else 0.0
            min_close = min(close_times) if close_times else 0.0
            # effect = how far below the threshold the median sits; +1 = at
            # the threshold, 0 = at zero seconds. Bounded in (0, 1].
            effect = max(0.0, min(1.0, 1.0 - median / threshold)) if threshold else 0.0
            analytical_support = min(1.0, 0.4 + 0.6 * effect)
            # evidence_completeness = qualifying / total-alerts-at-severity
            total = per_sev_total.get(severity, 0) or 1
            evidence_completeness = min(1.0, len(qualifying) / total)
            confidence = ConfidenceVector(
                analytical_support=analytical_support,
                evidence_completeness=evidence_completeness,
                peer_confidence=None,  # cohort benchmarking is a later phase
            )
            evidence_refs = [a.source_record_ref for a in qualifying if a.source_record_ref]
            rationale = (
                f"{len(qualifying)} {severity} alert(s) closed in under "
                f"{int(threshold)}s (median {int(median)}s, min {int(min_close)}s). "
                "Possible execution gap — verify that closure followed a real "
                "investigation, not a perfunctory one."
            )
            limitations = (
                "Heuristic closure-time threshold; a finding is not proof of "
                "misconduct, only that closure looked fast. Peer-benchmarked "
                "thresholds land in a later phase. Alerts with mapped_severity "
                f"= 'unknown' ({ineligible} observed) are excluded by design."
            )
            finding = Finding(
                observation_id="",  # back-filled by RunService
                rule_or_category="execution_gap.fast_closure",
                state="signal",
                rationale=rationale,
                scoped_subjects=[a.id for a in qualifying],
                statistic=median,
                effect=effect,
                threshold=float(threshold),
                confidence=confidence,
                evidence_refs=evidence_refs,
                limitations=limitations,
            )
            findings.append(finding)

        state = "signal" if any_signal else "no_signal"
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={"entity_id": run_context.entity_id,
                   "assessment_id": run_context.assessment_id,
                   "alerts_total": len(dataset.alerts),
                   "qualifying_by_severity": {
                       s: len(per_sev_qualifying.get(s, []))
                       for s in ("critical", "high", "medium")}},
            state=state,
            findings=findings,
            processing_metrics={
                "thresholds": {
                    "critical_max_seconds": self.thresholds.critical_max_seconds,
                    "high_max_seconds": self.thresholds.high_max_seconds,
                    "medium_max_seconds": self.thresholds.medium_max_seconds,
                    "absolute_floor_seconds": self.thresholds.absolute_floor_seconds,
                    "min_count_per_severity": self.thresholds.min_count_per_severity,
                },
                "per_severity_close_times": {
                    s: sorted(per_sev_close_times.get(s, [])) for s in
                    ("critical", "high", "medium")},
            },
        )
