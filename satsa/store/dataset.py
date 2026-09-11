"""CanonicalDataset: the frozen, in-memory read view of one entity's data
for one assessment that analytical workers operate on (Phase 4+).

Built from the persisted canonical store in one scoped read — workers
receive this object (already loaded), never a live database handle
(agent-architecture.md: workers hold no mutation authority).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from satsa.domain.entities import Asset
from satsa.domain.workflow import (
    Alert,
    Case,
    Disposition,
    Escalation,
    InvestigationStep,
)
from satsa.store.repositories import (
    AlertStore,
    AssetStore,
    CaseStore,
    DispositionStore,
    EscalationStore,
    InvestigationStepStore,
    SubmissionStore,
)


def _jloads(text: str):
    try:
        return json.loads(text) if text else []
    except json.JSONDecodeError:
        return []


def _alert_from(r: dict) -> Alert:
    return Alert(
        id=r["id"], entity_id=r["entity_id"], assessment_id=r["assessment_id"],
        native_id=r["native_id"], created_at=r["created_at"],
        native_severity=r["native_severity"], mapped_severity=r["mapped_severity"],
        native_category=r["native_category"], mapped_category=r["mapped_category"],
        asset_refs=_jloads(r["asset_refs_json"]), case_refs=_jloads(r["case_refs_json"]),
        detector_refs=_jloads(r["detector_refs_json"]),
        acknowledged_at=r["acknowledged_at"], closed_at=r["closed_at"],
        disposition_id=r["disposition_id"], source_record_ref=r["source_record_ref"],
        schema_version=r["schema_version"],
    )


def _case_from(r: dict) -> Case:
    return Case(
        id=r["id"], entity_id=r["entity_id"], assessment_id=r["assessment_id"],
        native_id=r["native_id"], opened_at=r["opened_at"],
        alert_refs=_jloads(r["alert_refs_json"]), owner_pseudonym=r["owner_pseudonym"],
        status=r["status"], closed_at=r["closed_at"], closure_reason=r["closure_reason"],
        investigation_refs=_jloads(r["investigation_refs_json"]),
        remediation_refs=_jloads(r["remediation_refs_json"]),
        source_record_ref=r["source_record_ref"], schema_version=r["schema_version"],
    )


def _step_from(r: dict) -> InvestigationStep:
    return InvestigationStep(
        id=r["id"], case_id=r["case_id"], action_type=r["action_type"],
        performed_at=r["performed_at"], sequence=r["sequence"],
        analyst_pseudonym=r["analyst_pseudonym"],
        evidence_refs=_jloads(r["evidence_refs_json"]),
        result_refs=_jloads(r["result_refs_json"]), note_text=r["note_text"],
    )


def _escalation_from(r: dict) -> Escalation:
    return Escalation(
        id=r["id"], entity_id=r["entity_id"], assessment_id=r["assessment_id"],
        occurred_at=r["occurred_at"], alert_id=r["alert_id"], case_id=r["case_id"],
        destination_role=r["destination_role"], trigger=r["trigger"],
        outcome=r["outcome"], policy_exception_ref=r["policy_exception_ref"],
    )


def _disposition_from(r: dict) -> Disposition:
    return Disposition(
        id=r["id"], entity_id=r["entity_id"], assessment_id=r["assessment_id"],
        occurred_at=r["occurred_at"], alert_id=r["alert_id"], case_id=r["case_id"],
        mapped_category=r["mapped_category"], reason=r["reason"],
        approver_role=r["approver_role"], exception_ref=r["exception_ref"],
        supporting_refs=_jloads(r["supporting_refs_json"]),
    )


def _asset_from(r: dict) -> Asset:
    return Asset(
        id=r["id"], entity_id=r["entity_id"], native_id=r["native_id"],
        criticality=r["criticality"], environment=r["environment"],
        active_intervals=_jloads(r["active_intervals_json"]),
        control_applicability=_jloads(r["control_applicability_json"]),
    )


@dataclass
class CanonicalDataset:
    """Frozen per-(entity, assessment) snapshot of canonical records."""

    entity_id: str
    assessment_id: str
    snapshot_digest: str = ""
    period_start: float = 0.0
    period_end: float = 0.0
    alerts: list = field(default_factory=list)          # list[Alert]
    cases: list = field(default_factory=list)           # list[Case]
    steps: list = field(default_factory=list)           # list[InvestigationStep]
    escalations: list = field(default_factory=list)     # list[Escalation]
    dispositions: list = field(default_factory=list)    # list[Disposition]
    assets: list = field(default_factory=list)          # list[Asset]
    # Which of the six SIH categories a submission actually contained data
    # for — an empty list means "submitted, nothing in it"; a category absent
    # from this set entirely means "file never submitted" (negative-space
    # analysis distinguishes the two; see Phase 6).
    submitted_categories: frozenset = frozenset()

    # ---- convenience views used by detectors ----
    @property
    def cases_by_id(self) -> dict:
        return {c.id: c for c in self.cases}

    @property
    def alerts_by_id(self) -> dict:
        return {a.id: a for a in self.alerts}

    def steps_for_case(self, case_id: str) -> list:
        return sorted((s for s in self.steps if s.case_id == case_id),
                      key=lambda s: s.sequence)

    def escalations_for_alert(self, alert_id: str) -> list:
        return [e for e in self.escalations if e.alert_id == alert_id]

    def escalations_for_case(self, case_id: str) -> list:
        return [e for e in self.escalations if e.case_id == case_id]

    def dispositions_for_alert(self, alert_id: str) -> list:
        return [d for d in self.dispositions if d.alert_id == alert_id]


def load_dataset(engine, entity_id: str, assessment_id: str) -> CanonicalDataset:
    """Load the frozen scope = union of this assessment's accepted submissions."""
    alerts = AlertStore(engine).list_for_scope(entity_id, assessment_id)
    cases = CaseStore(engine).list_for_scope(entity_id, assessment_id)
    escalations = EscalationStore(engine).list_for_scope(entity_id, assessment_id)
    dispositions = DispositionStore(engine).list_for_scope(entity_id, assessment_id)
    assets = AssetStore(engine).list_for_scope(entity_id, assessment_id)
    submissions = SubmissionStore(engine).list_for_assessment(assessment_id)

    steps: list = []
    categories: set = set()
    digest_parts: list = []
    for sub in submissions:
        for step_row in InvestigationStepStore(engine).list_for_submission(sub["id"]):
            steps.append(_step_from(step_row))
        if sub.get("snapshot_digest"):
            digest_parts.append(sub["snapshot_digest"])
        report = sub.get("ingest_report_json") or "{}"
        try:
            report_d = json.loads(report)
        except json.JSONDecodeError:
            report_d = {}
        for cat, info in (report_d.get("categories") or {}).items():
            if info.get("present"):
                categories.add(cat)

    digest = ""
    if digest_parts:
        from qsmlops.crypto.hashing import digest_document
        digest = digest_document(sorted(digest_parts))

    return CanonicalDataset(
        entity_id=entity_id, assessment_id=assessment_id,
        snapshot_digest=digest,
        alerts=[_alert_from(r) for r in alerts],
        cases=[_case_from(r) for r in cases],
        steps=steps, escalations=[_escalation_from(r) for r in escalations],
        dispositions=[_disposition_from(r) for r in dispositions],
        assets=[_asset_from(r) for r in assets],
        submitted_categories=frozenset(categories),
    )
