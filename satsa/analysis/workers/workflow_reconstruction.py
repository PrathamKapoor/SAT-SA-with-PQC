"""Workflow reconstruction: build the actual ordered event sequence
per case from raw timestamped records, and flag temporal-sequence
violations no other worker checks for.

Every record already carries a timestamp (case.opened_at/closed_at,
each investigation step's performed_at + declared sequence, each
escalation's occurred_at, each disposition's occurred_at) but nothing
in the pipeline reconstructs them into one ordered timeline and
cross-checks it. This worker does exactly that — three real,
independent checks:

1. **Escalation after closure** — a case escalated *after* it was
   already closed. Either the closure was premature (reopened via
   escalation) or the escalation is stale/misfiled; either way a
   supervisor should look.
2. **Disposition before investigation** — a disposition recorded
   before any investigation step exists for the case. Disposing of
   something before investigating it is a textbook execution gap at
   finer temporal granularity than the existing fast-closure check.
3. **Declared sequence vs. actual chronology mismatch** — investigation
   steps whose ``sequence`` field disagrees with the chronological
   order of their own ``performed_at`` timestamps. This is a strong
   data-quality signal: it usually means the steps were backfilled or
   reconstructed after the fact rather than recorded as they happened.

Each check is independently gated on the data it needs being present
(never fabricates a violation from missing data) and cites the exact
record ids involved.
"""
from __future__ import annotations

from dataclasses import dataclass

from satsa.contracts.worker import (
    AnalyticalWorker,
    ObservationBatch,
    RunContext,
)


@dataclass(frozen=True)
class WorkflowReconstructionThresholds:
    # No numeric threshold needed for these three checks — they are
    # each a strict temporal-ordering violation, not a statistical
    # judgment call. Kept as a policy object for consistency with the
    # rest of the worker fleet and to leave room for a future
    # tolerance window (e.g. "within 60s is clock-skew noise").
    escalation_after_closure_tolerance_seconds: float = 0.0


DEFAULT_WORKFLOW_RECONSTRUCTION_POLICY = WorkflowReconstructionThresholds()


class WorkflowReconstructionWorker(AnalyticalWorker):
    name = "workflow-reconstruction"
    version = "0.1.0"

    def __init__(self, thresholds: WorkflowReconstructionThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_WORKFLOW_RECONSTRUCTION_POLICY

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        from satsa.domain.evidence import ConfidenceVector, Finding

        findings: list[Finding] = []

        cases_by_id = {c.id: c for c in dataset.cases}
        steps_by_case: dict[str, list] = {}
        for s in dataset.steps:
            steps_by_case.setdefault(s.case_id, []).append(s)

        # -- 1. Escalation after closure --------------------------------
        escalations_after_closure = []
        for e in dataset.escalations:
            case = cases_by_id.get(e.case_id) if e.case_id else None
            if case is None or case.closed_at is None:
                continue
            if e.occurred_at > (case.closed_at
                                 + self.thresholds.escalation_after_closure_tolerance_seconds):
                escalations_after_closure.append((e, case))
        if escalations_after_closure:
            findings.append(Finding(
                observation_id="",
                rule_or_category="workflow_reconstruction.escalation_after_closure",
                state="signal",
                rationale=(
                    f"{len(escalations_after_closure)} escalation(s) occurred "
                    "after their linked case was already closed. Either the "
                    "closure was premature and the case had to be reopened, "
                    "or the escalation record is misfiled."
                ),
                scoped_subjects=[e.id for e, _ in escalations_after_closure],
                statistic=float(len(escalations_after_closure)),
                effect=min(1.0, len(escalations_after_closure) / max(1, len(dataset.escalations) or 1)),
                threshold=0.0,
                confidence=ConfidenceVector(analytical_support=0.85, evidence_completeness=1.0),
                evidence_refs=[c.source_record_ref for _, c in escalations_after_closure
                              if c.source_record_ref],
                limitations=(
                    "A short gap may reflect legitimate post-closure review "
                    "escalation (e.g. a QA re-check), not a genuine process "
                    "failure — confirm via human review before treating as "
                    "a conduct finding."
                ),
            ))

        # -- 2. Disposition before any investigation step ----------------
        dispositions_before_investigation = []
        for d in dataset.dispositions:
            if not d.case_id:
                continue
            steps = steps_by_case.get(d.case_id, [])
            if not steps:
                continue  # covered separately by negative_space.missing_investigation
            earliest_step = min(s.performed_at for s in steps)
            if d.occurred_at < earliest_step:
                dispositions_before_investigation.append(d)
        if dispositions_before_investigation:
            findings.append(Finding(
                observation_id="",
                rule_or_category="workflow_reconstruction.disposition_before_investigation",
                state="signal",
                rationale=(
                    f"{len(dispositions_before_investigation)} disposition(s) "
                    "were recorded before the earliest investigation step for "
                    "their case — the case was dispositioned before it was "
                    "investigated."
                ),
                scoped_subjects=[d.id for d in dispositions_before_investigation],
                statistic=float(len(dispositions_before_investigation)),
                effect=min(1.0, len(dispositions_before_investigation)
                          / max(1, len(dataset.dispositions) or 1)),
                threshold=0.0,
                confidence=ConfidenceVector(analytical_support=0.8, evidence_completeness=1.0),
                evidence_refs=[d.id for d in dispositions_before_investigation],
                limitations=(
                    "Some legitimate dispositions (e.g. an immediate "
                    "known-benign classification) precede formal "
                    "investigation steps by design — confirm via human "
                    "review."
                ),
            ))

        # -- 3. Declared sequence vs. actual chronology mismatch ---------
        cases_with_sequence_mismatch = []
        for case_id, steps in steps_by_case.items():
            if len(steps) < 2:
                continue
            by_declared_sequence = sorted(steps, key=lambda s: s.sequence)
            by_actual_time = sorted(steps, key=lambda s: s.performed_at)
            if [s.id for s in by_declared_sequence] != [s.id for s in by_actual_time]:
                cases_with_sequence_mismatch.append(case_id)
        if cases_with_sequence_mismatch:
            findings.append(Finding(
                observation_id="",
                rule_or_category="workflow_reconstruction.sequence_chronology_mismatch",
                state="signal",
                rationale=(
                    f"{len(cases_with_sequence_mismatch)} case(s) have "
                    "investigation steps whose declared sequence number "
                    "disagrees with the chronological order of their own "
                    "timestamps — a common signature of steps backfilled "
                    "or reconstructed after the fact rather than recorded "
                    "as they happened."
                ),
                scoped_subjects=list(cases_with_sequence_mismatch),
                statistic=float(len(cases_with_sequence_mismatch)),
                effect=min(1.0, len(cases_with_sequence_mismatch) / max(1, len(dataset.cases))),
                threshold=0.0,
                confidence=ConfidenceVector(analytical_support=0.6, evidence_completeness=1.0),
                evidence_refs=[],
                limitations=(
                    "Clock skew across analyst workstations, or a "
                    "case-management system that allows manual sequence "
                    "reassignment, can also produce this pattern without "
                    "any process failure."
                ),
            ))

        return ObservationBatch(
            worker_name=self.name, detector_version=self.version,
            scope={
                "entity_id": run_context.entity_id,
                "assessment_id": run_context.assessment_id,
                "cases_total": len(dataset.cases),
                "escalations_total": len(dataset.escalations),
                "dispositions_total": len(dataset.dispositions),
            },
            state="signal" if findings else "no_signal",
            findings=findings,
        )
