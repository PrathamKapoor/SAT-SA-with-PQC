"""Alert, Case, InvestigationStep, Escalation, Disposition — the SOC
workflow records execution-gap/negative-space analytics will eventually
read (Phase 3+, not this phase). Field lists follow
docs/phase1/data-architecture.md's canonical model table.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from satsa.domain.base import CURRENT_SCHEMA_VERSION, new_id, require


@dataclass
class Alert:
    """A single security alert as submitted by the CSE.

    ``acknowledged_at``/``closed_at`` are ``None`` (not a duration of zero)
    when not yet acknowledged/closed — data-architecture.md is explicit
    that "optional acknowledgment/closure is null, not zero duration."
    """

    entity_id: str
    assessment_id: str
    native_id: str
    created_at: float
    native_severity: str = ""
    mapped_severity: str = "unknown"
    native_category: str = ""
    mapped_category: str = "unknown"
    asset_refs: list = field(default_factory=list)
    case_refs: list = field(default_factory=list)
    detector_refs: list = field(default_factory=list)
    acknowledged_at: Optional[float] = None
    closed_at: Optional[float] = None
    disposition_id: Optional[str] = None
    source_record_ref: str = ""
    id: str = field(default_factory=lambda: new_id("alert"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.entity_id), "entity_id is required", errors)
        require(bool(self.assessment_id), "assessment_id is required", errors)
        require(bool(self.native_id), "native_id is required", errors)
        if self.acknowledged_at is not None:
            require(
                self.acknowledged_at >= self.created_at,
                "acknowledged_at cannot precede created_at", errors,
            )
        if self.closed_at is not None and self.acknowledged_at is not None:
            require(
                self.closed_at >= self.acknowledged_at,
                "closed_at cannot precede acknowledged_at", errors,
            )
        return errors

    @property
    def time_to_acknowledge(self) -> Optional[float]:
        if self.acknowledged_at is None:
            return None
        return self.acknowledged_at - self.created_at

    @property
    def time_to_close(self) -> Optional[float]:
        if self.closed_at is None:
            return None
        return self.closed_at - self.created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id, "entity_id": self.entity_id, "assessment_id": self.assessment_id,
            "native_id": self.native_id, "created_at": self.created_at,
            "native_severity": self.native_severity, "mapped_severity": self.mapped_severity,
            "native_category": self.native_category, "mapped_category": self.mapped_category,
            "asset_refs": list(self.asset_refs), "case_refs": list(self.case_refs),
            "detector_refs": list(self.detector_refs),
            "acknowledged_at": self.acknowledged_at, "closed_at": self.closed_at,
            "disposition_id": self.disposition_id, "source_record_ref": self.source_record_ref,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Alert":
        return cls(
            entity_id=d["entity_id"], assessment_id=d["assessment_id"], native_id=d["native_id"],
            created_at=d["created_at"], native_severity=d.get("native_severity", ""),
            mapped_severity=d.get("mapped_severity", "unknown"),
            native_category=d.get("native_category", ""),
            mapped_category=d.get("mapped_category", "unknown"),
            asset_refs=list(d.get("asset_refs", [])), case_refs=list(d.get("case_refs", [])),
            detector_refs=list(d.get("detector_refs", [])),
            acknowledged_at=d.get("acknowledged_at"), closed_at=d.get("closed_at"),
            disposition_id=d.get("disposition_id"),
            source_record_ref=d.get("source_record_ref", ""),
            id=d.get("id") or new_id("alert"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class Case:
    """An investigation case, potentially linking multiple alerts.

    ``alert_refs`` being empty is a distinct, meaningful state ("no alert
    link submitted") from a case that legitimately has none — ingestion
    quality checks (a later phase) are responsible for flagging the
    difference; this record just carries what was submitted.
    """

    entity_id: str
    assessment_id: str
    native_id: str
    opened_at: float
    alert_refs: list = field(default_factory=list)
    owner_pseudonym: str = ""
    status: str = "open"
    closed_at: Optional[float] = None
    closure_reason: str = ""
    investigation_refs: list = field(default_factory=list)
    remediation_refs: list = field(default_factory=list)
    source_record_ref: str = ""
    id: str = field(default_factory=lambda: new_id("case"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.entity_id), "entity_id is required", errors)
        require(bool(self.assessment_id), "assessment_id is required", errors)
        require(bool(self.native_id), "native_id is required", errors)
        if self.closed_at is not None:
            require(self.closed_at >= self.opened_at, "closed_at cannot precede opened_at", errors)
            require(self.status == "closed", "closed_at set but status is not 'closed'", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "entity_id": self.entity_id, "assessment_id": self.assessment_id,
            "native_id": self.native_id, "opened_at": self.opened_at,
            "alert_refs": list(self.alert_refs), "owner_pseudonym": self.owner_pseudonym,
            "status": self.status, "closed_at": self.closed_at,
            "closure_reason": self.closure_reason,
            "investigation_refs": list(self.investigation_refs),
            "remediation_refs": list(self.remediation_refs),
            "source_record_ref": self.source_record_ref, "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Case":
        return cls(
            entity_id=d["entity_id"], assessment_id=d["assessment_id"], native_id=d["native_id"],
            opened_at=d["opened_at"], alert_refs=list(d.get("alert_refs", [])),
            owner_pseudonym=d.get("owner_pseudonym", ""), status=d.get("status", "open"),
            closed_at=d.get("closed_at"), closure_reason=d.get("closure_reason", ""),
            investigation_refs=list(d.get("investigation_refs", [])),
            remediation_refs=list(d.get("remediation_refs", [])),
            source_record_ref=d.get("source_record_ref", ""),
            id=d.get("id") or new_id("case"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class InvestigationStep:
    """One recorded action within a case's investigation workflow.

    A note's presence/length is not, by itself, evidence of a meaningful
    investigation (data-architecture.md: "A note length or checkbox alone
    does not prove investigation") — that judgment belongs to a later-phase
    detector reading many steps together, not to this record.
    """

    case_id: str
    action_type: str
    performed_at: float
    sequence: int
    analyst_pseudonym: str = ""
    evidence_refs: list = field(default_factory=list)
    result_refs: list = field(default_factory=list)
    note_text: str = ""
    id: str = field(default_factory=lambda: new_id("invstep"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.case_id), "case_id is required", errors)
        require(bool(self.action_type), "action_type is required", errors)
        require(self.sequence >= 0, "sequence must be non-negative", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "case_id": self.case_id, "action_type": self.action_type,
            "performed_at": self.performed_at, "sequence": self.sequence,
            "analyst_pseudonym": self.analyst_pseudonym,
            "evidence_refs": list(self.evidence_refs), "result_refs": list(self.result_refs),
            "note_text": self.note_text, "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InvestigationStep":
        return cls(
            case_id=d["case_id"], action_type=d["action_type"], performed_at=d["performed_at"],
            sequence=d["sequence"], analyst_pseudonym=d.get("analyst_pseudonym", ""),
            evidence_refs=list(d.get("evidence_refs", [])),
            result_refs=list(d.get("result_refs", [])), note_text=d.get("note_text", ""),
            id=d.get("id") or new_id("invstep"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class Escalation:
    """An escalation event for an alert and/or case.

    Absence of an expected Escalation record is only interpretable relative
    to a declared policy/expectation (a later-phase concept) — this record
    does not itself decide whether its own absence is a finding.
    """

    entity_id: str
    assessment_id: str
    occurred_at: float
    alert_id: Optional[str] = None
    case_id: Optional[str] = None
    destination_role: str = ""
    trigger: str = ""
    outcome: str = ""
    policy_exception_ref: Optional[str] = None
    id: str = field(default_factory=lambda: new_id("escalation"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.entity_id), "entity_id is required", errors)
        require(bool(self.assessment_id), "assessment_id is required", errors)
        require(
            self.alert_id or self.case_id,
            "an escalation must reference at least one of alert_id/case_id", errors,
        )
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "entity_id": self.entity_id, "assessment_id": self.assessment_id,
            "occurred_at": self.occurred_at, "alert_id": self.alert_id, "case_id": self.case_id,
            "destination_role": self.destination_role, "trigger": self.trigger,
            "outcome": self.outcome, "policy_exception_ref": self.policy_exception_ref,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Escalation":
        return cls(
            entity_id=d["entity_id"], assessment_id=d["assessment_id"],
            occurred_at=d["occurred_at"], alert_id=d.get("alert_id"), case_id=d.get("case_id"),
            destination_role=d.get("destination_role", ""), trigger=d.get("trigger", ""),
            outcome=d.get("outcome", ""), policy_exception_ref=d.get("policy_exception_ref"),
            id=d.get("id") or new_id("escalation"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class Disposition:
    """The closure/disposition of an alert or case — preserved as its own
    record (rather than a field on Alert/Case) so benign/duplicate/test/
    suppressed classifications and their uncertainty survive independently
    of the alert/case lifecycle, per data-architecture.md."""

    entity_id: str
    assessment_id: str
    occurred_at: float
    alert_id: Optional[str] = None
    case_id: Optional[str] = None
    mapped_category: str = "unknown"
    reason: str = ""
    approver_role: str = ""
    exception_ref: Optional[str] = None
    supporting_refs: list = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("disposition"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.entity_id), "entity_id is required", errors)
        require(bool(self.assessment_id), "assessment_id is required", errors)
        require(
            self.alert_id or self.case_id,
            "a disposition must reference at least one of alert_id/case_id", errors,
        )
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "entity_id": self.entity_id, "assessment_id": self.assessment_id,
            "occurred_at": self.occurred_at, "alert_id": self.alert_id, "case_id": self.case_id,
            "mapped_category": self.mapped_category, "reason": self.reason,
            "approver_role": self.approver_role, "exception_ref": self.exception_ref,
            "supporting_refs": list(self.supporting_refs), "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Disposition":
        return cls(
            entity_id=d["entity_id"], assessment_id=d["assessment_id"],
            occurred_at=d["occurred_at"], alert_id=d.get("alert_id"), case_id=d.get("case_id"),
            mapped_category=d.get("mapped_category", "unknown"), reason=d.get("reason", ""),
            approver_role=d.get("approver_role", ""), exception_ref=d.get("exception_ref"),
            supporting_refs=list(d.get("supporting_refs", [])),
            id=d.get("id") or new_id("disposition"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )
