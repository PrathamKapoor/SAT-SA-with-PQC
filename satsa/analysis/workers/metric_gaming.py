"""Potential metric gaming: the closure-rate-on-critical/high metrics
look too good, given the absence of corresponding investigation
depth. SIH-REQ-7 / execution-gap signal 5.6.

Specifically: when the closure rate on critical/high alerts is
unusually high AND the average investigation depth per closed case
is unusually low, the metrics may be driven by closure, not by
investigation. This is a *coarse* heuristic — a finding is not proof
of gaming — and is deliberately conservative so it only fires when
both anomalies are simultaneously present.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)


@dataclass(frozen=True)
class MetricGamingThresholds:
    severities: tuple = ("critical", "high")
    min_closure_rate: float = 0.90         # very high closure
    max_avg_steps: float = 1.5             # very little investigation
    min_alerts_for_signal: int = 5         # not enough data to call a pattern


DEFAULT_METRIC_GAMING_POLICY = MetricGamingThresholds()


class MetricGamingWorker(AnalyticalWorker):
    name = "potential-metric-gaming"
    version = "0.1.0"

    def __init__(self, thresholds: MetricGamingThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_METRIC_GAMING_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        alerts_of_interest = [a for a in dataset.alerts
                              if a.mapped_severity in self.thresholds.severities]
        if len(alerts_of_interest) < self.thresholds.min_alerts_for_signal:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "alerts_of_interest": len(alerts_of_interest)},
                state="insufficient_data",
                processing_metrics={"reason": "not enough severity-eligible alerts to assess"},
            )
        closed = [a for a in alerts_of_interest if a.closed_at is not None]
        closure_rate = len(closed) / len(alerts_of_interest)
        steps_by_case: dict[str, int] = {}
        for s in dataset.steps:
            steps_by_case[s.case_id] = steps_by_case.get(s.case_id, 0) + 1
        case_depths: list[int] = []
        for a in closed:
            for c in (a.case_refs or []):
                case_depths.append(steps_by_case.get(c, 0))
        avg_steps = statistics.mean(case_depths) if case_depths else 0.0

        from satsa.domain.evidence import ConfidenceVector, Finding
        findings: list[Finding] = []
        is_suspicious = (closure_rate >= self.thresholds.min_closure_rate
                         and avg_steps <= self.thresholds.max_avg_steps)
        if is_suspicious:
            effect = min(1.0, 0.5 * (closure_rate + (1.0 - min(1.0, avg_steps / max(1, self.thresholds.max_avg_steps)))))
            confidence = ConfidenceVector(
                analytical_support=0.4 + 0.4 * effect,
                evidence_completeness=min(1.0, len(alerts_of_interest) / 20.0),
            )
            findings.append(Finding(
                observation_id="",
                rule_or_category="execution_gap.potential_metric_gaming",
                state="signal",
                rationale=(
                    f"{len(closed)}/{len(alerts_of_interest)} critical/high alerts "
                    f"({closure_rate:.0%}) were closed, with an average of "
                    f"{avg_steps:.1f} investigation step(s) per linked case. "
                    "Closure rate is very high while investigation depth is very "
                    "low — confirm that the numbers reflect real work, not just "
                    "fast closure."
                ),
                scoped_subjects=[a.id for a in closed],
                statistic=avg_steps,
                effect=effect,
                threshold=float(self.thresholds.max_avg_steps),
                confidence=confidence,
                evidence_refs=[a.source_record_ref for a in closed if a.source_record_ref],
                limitations=(
                    "A coarse two-signal heuristic; some legitimate operational "
                    "shapes (very high automation, very high capability) will "
                    "look identical. The human review workflow is the right next "
                    "step, not a conclusion."
                ),
            ))
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "alerts_of_interest": len(alerts_of_interest),
                "closed": len(closed),
                "closure_rate": closure_rate,
                "avg_steps": avg_steps,
            },
            state="signal" if findings else "no_signal",
            findings=findings,
            processing_metrics={"thresholds": {
                "min_closure_rate": self.thresholds.min_closure_rate,
                "max_avg_steps": self.thresholds.max_avg_steps,
                "min_alerts_for_signal": self.thresholds.min_alerts_for_signal,
            }},
        )
