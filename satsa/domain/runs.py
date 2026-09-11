"""AnalysisRun — the execution-boundary record Part J asks for: what was
analyzed, when, with which code/analytics/model versions, producing which
observations, from which evidence. Reruns create a new AnalysisRun; a
finding is never silently overwritten by a later run (analytics-architecture.md:
"Rerun creates new ID; never overwrite prior findings")."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from satsa.domain.base import CURRENT_SCHEMA_VERSION, new_id, require

RUN_STATUSES = ("pending", "running", "completed", "failed", "partial", "cancelled")


@dataclass
class AnalysisRun:
    entity_id: str
    assessment_id: str
    snapshot_digest: str
    baseline_digests: dict = field(default_factory=dict)  # baseline name -> digest
    code_version: str = ""
    analytics_version: str = ""
    model_version: Optional[str] = None
    status: str = "pending"
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    observation_ids: list = field(default_factory=list)
    error: str = ""
    id: str = field(default_factory=lambda: new_id("run"))
    schema_version: int = CURRENT_SCHEMA_VERSION

    def validate(self) -> list[str]:
        errors: list[str] = []
        require(bool(self.entity_id), "entity_id is required", errors)
        require(bool(self.assessment_id), "assessment_id is required", errors)
        require(bool(self.snapshot_digest), "snapshot_digest is required", errors)
        require(
            self.status in RUN_STATUSES, f"status {self.status!r} must be one of {RUN_STATUSES}",
            errors,
        )
        if self.status in ("completed", "failed", "partial", "cancelled"):
            require(self.finished_at is not None, f"status={self.status} requires finished_at", errors)
        if self.status == "failed":
            require(bool(self.error), "status='failed' requires a non-empty error", errors)
        return errors

    def to_dict(self) -> dict:
        return {
            "id": self.id, "entity_id": self.entity_id, "assessment_id": self.assessment_id,
            "snapshot_digest": self.snapshot_digest, "baseline_digests": dict(self.baseline_digests),
            "code_version": self.code_version, "analytics_version": self.analytics_version,
            "model_version": self.model_version, "status": self.status,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "observation_ids": list(self.observation_ids), "error": self.error,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisRun":
        return cls(
            entity_id=d["entity_id"], assessment_id=d["assessment_id"],
            snapshot_digest=d["snapshot_digest"],
            baseline_digests=dict(d.get("baseline_digests", {})),
            code_version=d.get("code_version", ""), analytics_version=d.get("analytics_version", ""),
            model_version=d.get("model_version"), status=d.get("status", "pending"),
            started_at=d.get("started_at"), finished_at=d.get("finished_at"),
            observation_ids=list(d.get("observation_ids", [])), error=d.get("error", ""),
            id=d.get("id") or new_id("run"),
            schema_version=d.get("schema_version", CURRENT_SCHEMA_VERSION),
        )
