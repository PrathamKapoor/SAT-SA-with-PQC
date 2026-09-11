"""Repeated alerts without remediation: a case has re-opened or
absorbed multiple alerts but the case has no remediation_refs, and
the case is closed. The same incident keeps showing up; nothing
changed. SIH-REQ-6 / execution-gap signal 5.5.

We deliberately do not require the same `native_id` to recur: the
CSE may file each recurring event as a new alert. We count *all*
alerts that resolved into a case, so a case touched by ≥
``recurrence_threshold`` distinct alerts is a recurring case, and
one that closed without listing any remediation action is a likely
gap.
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)


@dataclass(frozen=True)
class RecurringWithoutRemediationThresholds:
    recurrence_threshold: int = 3          # alerts linked to one case
    must_be_closed: bool = True
    require_status: tuple = ("closed",)    # the case statuses we consider resolved


DEFAULT_RECURRING_WITHOUT_REMEDIATION_POLICY = RecurringWithoutRemediationThresholds()


class RecurringWithoutRemediationWorker(AnalyticalWorker):
    name = "recurring-without-remediation"
    version = "0.1.0"

    def __init__(self, thresholds: RecurringWithoutRemediationThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_RECURRING_WITHOUT_REMEDIATION_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        if not dataset.cases:
            return ObservationBatch(
                worker_name=self.name, detector_version=self.version,
                scope={"entity_id": run_context.entity_id,
                       "assessment_id": run_context.assessment_id,
                       "cases_total": 0},
                state="insufficient_data",
                processing_metrics={"reason": "no cases in scope"},
            )
        # alert → case (many-to-many via alert.case_refs)
        case_to_alerts: dict[str, list] = {c.id: [] for c in dataset.cases}
        for a in dataset.alerts:
            for c in (a.case_refs or []):
                if c in case_to_alerts:
                    case_to_alerts[c].append(a)
        qualifying: list = []
        for c in dataset.cases:
            linked = case_to_alerts.get(c.id, [])
            if len(linked) < self.thresholds.recurrence_threshold:
                continue
            if self.thresholds.must_be_closed and c.status not in self.thresholds.require_status:
                continue
            if c.remediation_refs:
                continue
            qualifying.append((c, linked))

        from satsa.domain.evidence import ConfidenceVector, Finding
        findings: list[Finding] = []
        if qualifying:
            confidence = ConfidenceVector(
                analytical_support=0.7,
                evidence_completeness=min(1.0, len(qualifying) / max(1, len(dataset.cases))),
            )
            scoped = [c.id for c, _ in qualifying]
            max_recurrence = max(len(linked) for _, linked in qualifying)
            findings.append(Finding(
                observation_id="",
                rule_or_category="execution_gap.recurring_without_remediation",
                state="signal",
                rationale=(
                    f"{len(qualifying)} closed case(s) absorbed ≥ "
                    f"{self.thresholds.recurrence_threshold} alerts (max "
                    f"{max_recurrence}) but list no remediation action. The same "
                    "incident(s) keep appearing without an effective fix."
                ),
                scoped_subjects=scoped,
                statistic=float(max_recurrence),
                effect=min(1.0, max_recurrence / max(1, self.thresholds.recurrence_threshold * 2)),
                threshold=float(self.thresholds.recurrence_threshold),
                confidence=confidence,
                evidence_refs=[c.source_record_ref for c, _ in qualifying if c.source_record_ref],
                limitations=(
                    "A 'remediation' is whatever the CSE records in remediation_refs. "
                    "A real remediation done outside the workflow tool is invisible "
                    "here and will be over-flagged — confirm with the analyst."
                ),
            ))
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "cases_total": len(dataset.cases),
                "qualifying": len(qualifying),
            },
            state="signal" if findings else "no_signal",
            findings=findings,
            processing_metrics={"thresholds": {
                "recurrence_threshold": self.thresholds.recurrence_threshold,
                "must_be_closed": self.thresholds.must_be_closed,
            }},
        )
