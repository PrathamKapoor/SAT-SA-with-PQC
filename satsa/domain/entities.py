"""Entity, Assessment, Submission, Asset — the scoping records every other
SAT-SA record is anchored to. Field lists follow
docs/phase1/data-architecture.md's canonical model table; nothing here adds
a field that document did not already justify (Part H: "do not invent
fields that have no purpose").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from satsa.domain.base import CURRENT_SCHEMA_VERSION, new_id, require

ASSESSMENT_STATUSES = ("draft", "open", "closed", "superseded")
SIGNATURE_STATUSES = ("unsigned", "signed", "verified", "verification_failed")


@dataclass
class Entity:
    """A CSE (Client Security Environment / the assessed organization).

    Missing-data semantics: unknown cohort dimensions (sector/environment/
    scale) prohibit the relevant peer comparison — they do not default to
    "average" or get silently excluded from comparability checks elsewhere.
    """

    display_name: str
    sector: str = ""
    environment_class: str = ""
    cohort_attributes: dict = field(default_factory=dict)
    access_scope: str = ""
    id: str = field(default_factory=lambda: new_id("entity"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.display_name), "display_name is required", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "display_name": self.display_name, "sector": self.sector,
            "environment_class": self.environment_class,
            "cohort_attributes": dict(self.cohort_attributes),
            "access_scope": self.access_scope, "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Entity":
        return cls(
            display_name=d["display_name"], sector=d.get("sector", ""),
            environment_class=d.get("environment_class", ""),
            cohort_attributes=dict(d.get("cohort_attributes", {})),
            access_scope=d.get("access_scope", ""), id=d.get("id") or new_id("entity"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class Assessment:
    """One periodic supervisory assessment cycle for one entity.

    Period is half-open [period_start, period_end) per
    data-architecture.md. ``supersedes_id`` links a corrected assessment to
    the one it replaces — a correction creates a new version, it never
    mutates an already-closed assessment in place.
    """

    entity_id: str
    period_start: float
    period_end: float
    timezone: str = "UTC"
    submission_cutoff: Optional[float] = None
    policy_version: str = ""
    status: str = "draft"
    supersedes_id: Optional[str] = None
    id: str = field(default_factory=lambda: new_id("assessment"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.entity_id), "entity_id is required", errors)
        require(self.period_end > self.period_start, "period_end must be after period_start", errors)
        require(
            self.status in ASSESSMENT_STATUSES,
            f"status {self.status!r} must be one of {ASSESSMENT_STATUSES}", errors,
        )
        return errors

    def contains(self, timestamp: float) -> bool:
        """Half-open interval membership: [period_start, period_end)."""
        return self.period_start <= timestamp < self.period_end

    def to_dict(self) -> dict:
        return {
            "id": self.id, "entity_id": self.entity_id, "period_start": self.period_start,
            "period_end": self.period_end, "timezone": self.timezone,
            "submission_cutoff": self.submission_cutoff, "policy_version": self.policy_version,
            "status": self.status, "supersedes_id": self.supersedes_id,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Assessment":
        return cls(
            entity_id=d["entity_id"], period_start=d["period_start"], period_end=d["period_end"],
            timezone=d.get("timezone", "UTC"), submission_cutoff=d.get("submission_cutoff"),
            policy_version=d.get("policy_version", ""), status=d.get("status", "draft"),
            supersedes_id=d.get("supersedes_id"), id=d.get("id") or new_id("assessment"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class Submission:
    """One CSE evidence submission for one assessment.

    ``file_digests``/``declared_counts`` are the submitter's own claim about
    what the submission contains — reconciling that claim against what was
    actually parsed is ingestion-phase work (data-architecture.md's
    5-step transaction), not this record's job; this record only carries the
    claim plus signature status honestly (Part H: "source provenance").
    """

    assessment_id: str
    source_system: str
    declared_period_start: float
    declared_period_end: float
    file_digests: dict = field(default_factory=dict)   # filename -> sha3 hex
    declared_counts: dict = field(default_factory=dict)  # table -> row count
    schema_name: str = ""
    received_at: Optional[float] = None
    signature_status: str = "unsigned"
    id: str = field(default_factory=lambda: new_id("submission"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.assessment_id), "assessment_id is required", errors)
        require(bool(self.source_system), "source_system is required", errors)
        require(
            self.declared_period_end > self.declared_period_start,
            "declared_period_end must be after declared_period_start", errors,
        )
        require(
            self.signature_status in SIGNATURE_STATUSES,
            f"signature_status {self.signature_status!r} must be one of {SIGNATURE_STATUSES}",
            errors,
        )
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "assessment_id": self.assessment_id, "source_system": self.source_system,
            "declared_period_start": self.declared_period_start,
            "declared_period_end": self.declared_period_end,
            "file_digests": dict(self.file_digests), "declared_counts": dict(self.declared_counts),
            "schema_name": self.schema_name, "received_at": self.received_at,
            "signature_status": self.signature_status, "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Submission":
        return cls(
            assessment_id=d["assessment_id"], source_system=d["source_system"],
            declared_period_start=d["declared_period_start"],
            declared_period_end=d["declared_period_end"],
            file_digests=dict(d.get("file_digests", {})),
            declared_counts=dict(d.get("declared_counts", {})),
            schema_name=d.get("schema_name", ""), received_at=d.get("received_at"),
            signature_status=d.get("signature_status", "unsigned"),
            id=d.get("id") or new_id("submission"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )


@dataclass
class Asset:
    """An asset/system in the entity's inventory (optional per submission —
    absence means coverage analysis is usually `insufficient_data`, not a
    finding of zero coverage; see data-architecture.md)."""

    entity_id: str
    native_id: str
    criticality: str = "unknown"
    environment: str = ""
    active_intervals: list = field(default_factory=list)  # [(start, end), ...]
    control_applicability: list = field(default_factory=list)  # control IDs
    id: str = field(default_factory=lambda: new_id("asset"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.entity_id), "entity_id is required", errors)
        require(bool(self.native_id), "native_id is required", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "entity_id": self.entity_id, "native_id": self.native_id,
            "criticality": self.criticality, "environment": self.environment,
            "active_intervals": list(self.active_intervals),
            "control_applicability": list(self.control_applicability),
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Asset":
        return cls(
            entity_id=d["entity_id"], native_id=d["native_id"],
            criticality=d.get("criticality", "unknown"), environment=d.get("environment", ""),
            active_intervals=list(d.get("active_intervals", [])),
            control_applicability=list(d.get("control_applicability", [])),
            id=d.get("id") or new_id("asset"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )
