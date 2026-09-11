"""SourceRecord, Observation, Finding, ReviewDecision, ProvenanceRecord —
the explainability chain Part C7/SIH-EX-01..05 requires:
Finding -> Observation -> SourceRecord -> original submission bytes.

Deliberately distinct from ``qsmlops.agents.base.Observation``/``Finding``:
those are the MLOps platform's own (simpler, single-confidence-float)
shapes and stay exactly as they are (Phase 1's target-architecture.md: reuse
the *pattern*, not the implementation). SAT-SA's Finding needs a richer,
multi-dimensional confidence vector and an explicit abstention state
(``insufficient_data``/``not_applicable``) that the MLOps Finding has no
reason to carry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from satsa.domain.base import CURRENT_SCHEMA_VERSION, new_id, require

FINDING_STATES = ("signal", "no_signal", "insufficient_data", "not_applicable", "error")
REVIEW_ACTIONS = ("confirm", "dismiss", "escalate", "request_review", "annotate")


@dataclass
class SourceRecord:
    """A pointer to one immutable original record inside a submission's
    stored bytes — never the bytes themselves. ``original_record_digest``
    lets a reader verify the referenced record has not changed without
    re-reading the whole submission file."""

    submission_id: str
    file_digest: str
    format: str
    locator: str  # row index, JSON pointer, or similar — format-specific
    original_record_digest: str
    id: str = field(default_factory=lambda: new_id("srcrec"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.submission_id), "submission_id is required", errors)
        require(bool(self.file_digest), "file_digest is required", errors)
        require(bool(self.original_record_digest), "original_record_digest is required", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "submission_id": self.submission_id, "file_digest": self.file_digest,
            "format": self.format, "locator": self.locator,
            "original_record_digest": self.original_record_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SourceRecord":
        return cls(
            submission_id=d["submission_id"], file_digest=d["file_digest"], format=d["format"],
            locator=d["locator"], original_record_digest=d["original_record_digest"],
            id=d.get("id") or new_id("srcrec"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class ConfidenceVector:
    """Multi-dimensional confidence per analytics-architecture.md: "Do not
    call a p-value a probability of correctness." ``overall`` is computed as
    the minimum of the required components by convention (a high-impact
    uncertain signal is only as trustworthy as its weakest leg), not stored
    independently — callers should not construct it directly with a
    different overall unless they have a documented reason to."""

    analytical_support: float
    evidence_completeness: float
    peer_confidence: Optional[float] = None  # None = not_applicable, not zero

    @property
    def overall(self) -> float:
        components = [self.analytical_support, self.evidence_completeness]
        if self.peer_confidence is not None:
            components.append(self.peer_confidence)
        return min(components)

    def to_dict(self) -> dict:
        return {
            "analytical_support": self.analytical_support,
            "evidence_completeness": self.evidence_completeness,
            "peer_confidence": self.peer_confidence, "overall": self.overall,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConfidenceVector":
        return cls(
            analytical_support=d["analytical_support"],
            evidence_completeness=d["evidence_completeness"],
            peer_confidence=d.get("peer_confidence"),
        )


@dataclass
class Observation:
    """One detector's run envelope against one scope (Part H's
    "Observation") — the container a run's Findings belong to. Mirrors the
    worker contract's ObservationBatch (satsa.contracts.worker) but as a
    plain domain record rather than an in-memory execution result."""

    run_id: str
    worker_name: str
    detector_version: str
    entity_id: str
    assessment_id: str
    scope: dict = field(default_factory=dict)  # e.g. {"asset_id": ..., "period": ...}
    created_at: float = 0.0
    id: str = field(default_factory=lambda: new_id("observation"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.run_id), "run_id is required", errors)
        require(bool(self.worker_name), "worker_name is required", errors)
        require(bool(self.entity_id), "entity_id is required", errors)
        require(bool(self.assessment_id), "assessment_id is required", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "run_id": self.run_id, "worker_name": self.worker_name,
            "detector_version": self.detector_version, "entity_id": self.entity_id,
            "assessment_id": self.assessment_id, "scope": dict(self.scope),
            "created_at": self.created_at, "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Observation":
        return cls(
            run_id=d["run_id"], worker_name=d["worker_name"],
            detector_version=d.get("detector_version", ""), entity_id=d["entity_id"],
            assessment_id=d["assessment_id"], scope=dict(d.get("scope", {})),
            created_at=d.get("created_at", 0.0), id=d.get("id") or new_id("observation"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class Finding:
    """One supervisory-analytical signal (Part H's "Finding" / SIH-EX-01).

    ``state`` is mandatory and distinct from a boolean pass/fail: an
    abstaining detector (``insufficient_data``/``not_applicable``) is not
    the same as one that checked and found nothing (``no_signal``) — this
    distinction is exactly what analytics-architecture.md's "a failed
    detector cannot become 'healthy'" rule protects.
    """

    observation_id: str
    rule_or_category: str
    state: str
    rationale: str = ""
    scoped_subjects: list = field(default_factory=list)  # entity/asset/case/alert IDs
    statistic: Optional[float] = None
    effect: Optional[float] = None
    threshold: Optional[float] = None
    confidence: Optional[ConfidenceVector] = None
    evidence_refs: list = field(default_factory=list)  # SourceRecord IDs
    limitations: str = ""
    id: str = field(default_factory=lambda: new_id("finding"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.observation_id), "observation_id is required", errors)
        require(bool(self.rule_or_category), "rule_or_category is required", errors)
        require(
            self.state in FINDING_STATES, f"state {self.state!r} must be one of {FINDING_STATES}",
            errors,
        )
        if self.state == "signal":
            require(
                bool(self.evidence_refs),
                "a 'signal' finding must cite at least one evidence_ref "
                "(SIH-EX-02: 'a score without explanation is insufficient')",
                errors,
            )
            require(
                self.confidence is not None,
                "a 'signal' finding must carry a confidence vector", errors,
            )
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "observation_id": self.observation_id,
            "rule_or_category": self.rule_or_category, "state": self.state,
            "rationale": self.rationale, "scoped_subjects": list(self.scoped_subjects),
            "statistic": self.statistic, "effect": self.effect, "threshold": self.threshold,
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "evidence_refs": list(self.evidence_refs), "limitations": self.limitations,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(
            observation_id=d["observation_id"], rule_or_category=d["rule_or_category"],
            state=d["state"], rationale=d.get("rationale", ""),
            scoped_subjects=list(d.get("scoped_subjects", [])), statistic=d.get("statistic"),
            effect=d.get("effect"), threshold=d.get("threshold"),
            confidence=ConfidenceVector.from_dict(d["confidence"]) if d.get("confidence") else None,
            evidence_refs=list(d.get("evidence_refs", [])), limitations=d.get("limitations", ""),
            id=d.get("id") or new_id("finding"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class ReviewDecision:
    """An authenticated examiner's action on a Finding (Part H's
    "SupervisoryDecision"; named ReviewDecision to match
    data-architecture.md's record name and SAT-HUM-01's "human decisions
    must remain authoritative"). Append-only by convention: a correction
    creates a new ReviewDecision referencing ``previous_revision_id``, it
    never edits history — enforced by the persistence layer that will store
    these, not by this dataclass itself.
    """

    finding_id: str
    principal_identity_id: str
    action: str
    reason: str = ""
    occurred_at: float = 0.0
    previous_revision_id: Optional[str] = None
    id: str = field(default_factory=lambda: new_id("reviewdec"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.finding_id), "finding_id is required", errors)
        require(bool(self.principal_identity_id), "principal_identity_id is required", errors)
        require(
            self.action in REVIEW_ACTIONS, f"action {self.action!r} must be one of {REVIEW_ACTIONS}",
            errors,
        )
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "finding_id": self.finding_id,
            "principal_identity_id": self.principal_identity_id, "action": self.action,
            "reason": self.reason, "occurred_at": self.occurred_at,
            "previous_revision_id": self.previous_revision_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReviewDecision":
        return cls(
            finding_id=d["finding_id"], principal_identity_id=d["principal_identity_id"],
            action=d["action"], reason=d.get("reason", ""), occurred_at=d.get("occurred_at", 0.0),
            previous_revision_id=d.get("previous_revision_id"),
            id=d.get("id") or new_id("reviewdec"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class ProvenanceRecord:
    """A typed subject->predicate->object link in the SAT-SA domain,
    conceptually the same shape as qsmlops' provenance_edges (Phase 2 Part
    E) but for satsa's own object types (finding/observation/submission/
    source_record/review_decision, not qsmlops' observation/finding).
    Kept as a plain domain record here (Part H scope); persisting it is a
    later-phase concern, same distinction Part E drew for qsmlops' tables.
    """

    subject_type: str
    subject_id: str
    predicate: str
    object_type: str
    object_id: str
    metadata: dict = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.subject_type), "subject_type is required", errors)
        require(bool(self.subject_id), "subject_id is required", errors)
        require(bool(self.predicate), "predicate is required", errors)
        require(bool(self.object_type), "object_type is required", errors)
        require(bool(self.object_id), "object_id is required", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "subject_type": self.subject_type, "subject_id": self.subject_id,
            "predicate": self.predicate, "object_type": self.object_type,
            "object_id": self.object_id, "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProvenanceRecord":
        return cls(
            subject_type=d["subject_type"], subject_id=d["subject_id"], predicate=d["predicate"],
            object_type=d["object_type"], object_id=d["object_id"],
            metadata=dict(d.get("metadata", {})),
        )
