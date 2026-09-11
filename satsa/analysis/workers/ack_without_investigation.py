"""Acknowledged-but-not-investigated: an alert that was acknowledged
(met the SLA for first response) but has no meaningful investigation
behind its closure — possibly closed as a checkbox rather than on
substance. SIH-REQ-2 / execution-gap signal 5.1.

Heuristic: for every closed alert whose case(s) collectively recorded
fewer than ``min_steps_per_case`` investigation steps, the alert is
flagged. Acknowledgement is required for the signal to fire (an alert
that was never even acknowledged is the *negative-space* engine's
concern, not this one — that distinction is the whole point of
separating the two phases per docs/phase1/analytics-architecture.md).
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)


@dataclass(frozen=True)
class AckWithoutInvestigationThresholds:
    min_steps_per_case: int = 2     # below this = no real investigation
    # only consider alerts at-or-above these severities
    severities: tuple = ("critical", "high", "medium")


DEFAULT_ACK_WITHOUT_INVESTIGATION_POLICY = AckWithoutInvestigationThresholds()


class AckWithoutInvestigationWorker(AnalyticalWorker):
    name = "ack-without-investigation"
    version = "0.1.0"

    def __init__(self, thresholds: AckWithoutInvestigationThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_ACK_WITHOUT_INVESTIGATION_POLICY

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
        steps_by_case: dict[str, list] = {}
        for s in dataset.steps:
            steps_by_case.setdefault(s.case_id, []).append(s)
        qualifying: list = []
        ineligible_unacked = 0
        for a in dataset.alerts:
            if a.mapped_severity not in self.thresholds.severities:
                continue
            if a.acknowledged_at is None:
                ineligible_unacked += 1
                continue
            if a.closed_at is None:
                continue  # not closed → not a "closure-without-investigation" finding
            case_refs = a.case_refs or []
            total_steps = sum(len(steps_by_case.get(c, [])) for c in case_refs)
            if total_steps < self.thresholds.min_steps_per_case:
                qualifying.append((a, total_steps, case_refs))

        from satsa.domain.evidence import ConfidenceVector, Finding
        findings: list[Finding] = []
        if qualifying:
            effect = min(1.0, len(qualifying) / max(1, len(dataset.alerts)))
            confidence = ConfidenceVector(
                analytical_support=0.5 + 0.4 * effect,
                evidence_completeness=min(1.0, len(qualifying) / max(1, len(dataset.alerts))),
            )
            scoped = [a.id for a, _, _ in qualifying]
            findings.append(Finding(
                observation_id="",
                rule_or_category="execution_gap.ack_without_investigation",
                state="signal",
                rationale=(
                    f"{len(qualifying)} acknowledged-and-closed alert(s) had fewer than "
                    f"{self.thresholds.min_steps_per_case} investigation step(s) recorded "
                    "across their linked case(s). Closure followed acknowledgement, but "
                    "with no traceable investigation behind it."
                ),
                scoped_subjects=scoped,
                statistic=float(len(qualifying)),
                effect=effect,
                threshold=float(self.thresholds.min_steps_per_case),
                confidence=confidence,
                evidence_refs=[a.source_record_ref for a, _, _ in qualifying if a.source_record_ref],
                limitations=(
                    "Heuristic on raw step count. 'Meaningful' investigation is not "
                    "a count, and shallow-but-substantive cases may be mis-flagged. "
                    "See the rule rationale and individual case drill-down for context."
                ),
            ))
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "alerts_total": len(dataset.alerts),
                "qualifying": len(qualifying),
                "ineligible_unacknowledged": ineligible_unacked,
            },
            state="signal" if findings else "no_signal",
            findings=findings,
            processing_metrics={"thresholds": {
                "min_steps_per_case": self.thresholds.min_steps_per_case,
                "severities": list(self.thresholds.severities),
            }},
        )
