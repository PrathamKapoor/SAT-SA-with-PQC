"""Critical-without-escalation: a critical alert was closed but no
escalation was raised. SIH-REQ-4 / execution-gap signal 5.3.

A critical alert that closes without a documented escalation is
exactly the situation supervisors want to know about — escalation is
a second-pair-of-eyes check, not paperwork.
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)


@dataclass(frozen=True)
class CriticalWithoutEscalationThresholds:
    severities: tuple = ("critical",)   # only the top tier by default


DEFAULT_CRITICAL_WITHOUT_ESCALATION_POLICY = CriticalWithoutEscalationThresholds()


class CriticalWithoutEscalationWorker(AnalyticalWorker):
    name = "critical-without-escalation"
    version = "0.1.0"

    def __init__(self, thresholds: CriticalWithoutEscalationThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_CRITICAL_WITHOUT_ESCALATION_POLICY

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
        escalated_alert_ids = {e.alert_id for e in dataset.escalations if e.alert_id}
        escalated_case_ids = {e.case_id for e in dataset.escalations if e.case_id}
        qualifying: list = []
        for a in dataset.alerts:
            if a.mapped_severity not in self.thresholds.severities:
                continue
            if a.closed_at is None:
                continue
            if a.id in escalated_alert_ids:
                continue
            # also count it as 'escalated' if any of its linked cases were
            # escalated — the escalation may have happened at the case level
            if any(c in escalated_case_ids for c in (a.case_refs or [])):
                continue
            qualifying.append(a)

        from satsa.domain.evidence import ConfidenceVector, Finding
        findings: list[Finding] = []
        if qualifying:
            confidence = ConfidenceVector(
                analytical_support=0.8,   # the rule is essentially binary
                evidence_completeness=min(1.0, len(qualifying) / max(1, len(dataset.alerts))),
            )
            findings.append(Finding(
                observation_id="",
                rule_or_category="execution_gap.critical_without_escalation",
                state="signal",
                rationale=(
                    f"{len(qualifying)} closed critical alert(s) had no escalation "
                    "record (neither directly nor via any linked case). The standard "
                    "second-pair-of-eyes check did not happen."
                ),
                scoped_subjects=[a.id for a in qualifying],
                statistic=float(len(qualifying)),
                effect=min(1.0, len(qualifying) / max(1, len(dataset.alerts))),
                threshold=1.0,
                confidence=confidence,
                evidence_refs=[a.source_record_ref for a in qualifying if a.source_record_ref],
                limitations=(
                    "Only considers escalations the CSE submitted. A legitimate "
                    "verbal escalation (e.g. a phone call) is not visible to the "
                    "supervisor and will be flagged here — confirm via the human "
                    "review workflow before treating as a finding."
                ),
            ))
        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "alerts_total": len(dataset.alerts),
                "qualifying": len(qualifying),
                "escalations_in_scope": len(dataset.escalations),
            },
            state="signal" if findings else "no_signal",
            findings=findings,
        )
