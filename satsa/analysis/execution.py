"""Durable tenant-scoped analysis execution for validated submissions.

The execution layer schedules the existing deterministic SAT-SA workers. It
does not change their algorithms, and it deliberately keeps transactions to
short state transitions and per-worker result commits.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from qsmlops.core.errors import DuplicateEntryError, PermissionDeniedError
from qsmlops.core.logging import configure_logging, get_logger
from qsmlops.crypto.hashing import digest_document
from qsmlops.security.permissions.model import (
    ANALYSIS_RUN,
    EVIDENCE_VIEW,
    FINDING_VIEW,
    REVIEW_CREATE,
)
from satsa.analysis import ANALYTICS_VERSION
from satsa.analysis.repository import _d, _j
from satsa.analysis.run import _default_workers
from satsa.analysis.workers import DEFAULT_FAST_CLOSURE_POLICY
from satsa.contracts.orchestration import Job, Orchestrator
from satsa.contracts.worker import RunContext, SnapshotRef
from satsa.domain.entities import Asset
from satsa.domain.evidence import Finding, Observation
from satsa.domain.workflow import (
    Alert,
    Case,
    Disposition,
    Escalation,
    InvestigationStep,
)
from satsa.errors import DomainValidationError
from satsa.store.dataset import CanonicalDataset
from satsa.tenancy import TenantRepository, _id

log = get_logger(__name__)

RUN_TERMINAL = {"completed", "partial", "failed", "cancelled"}
RUN_TRANSITIONS = {
    "queued": {"running", "cancel_requested", "failed"},
    "running": {
        "completed",
        "partial",
        "failed",
        "awaiting_review",
        "cancel_requested",
        "cancelled",
        "queued",
    },
    "cancel_requested": {"cancelled", "failed"},
    "awaiting_review": {"queued", "cancel_requested"},
    "failed": {"queued"},
}
_CATEGORY_TYPES: dict[str, type[Any]] = {
    "alerts": Alert,
    "cases": Case,
    "assets": Asset,
    "investigation_steps": InvestigationStep,
    "escalations": Escalation,
    "dispositions": Disposition,
}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha3_256("\0".join(parts).encode()).hexdigest()[:32]
    return f"{prefix}_{digest}"


def _lock_run(db, organization_id: str, run_id: str) -> dict | None:
    """Row-lock a run inside a transaction and return its committed status.

    A no-op UPDATE is the portable SELECT ... FOR UPDATE: PostgreSQL waits for
    a concurrent writer and re-reads the row; SQLite serializes transactions.
    """
    return db.query_one(
        "UPDATE satsa_runs SET status=status WHERE organization_id=? AND id=?"
        " RETURNING status",
        (organization_id, run_id),
    )


def _membership_role(engine, org: str, user: str) -> str | None:
    row = engine.query_one(
        "SELECT m.role FROM satsa_memberships m JOIN satsa_organizations o"
        " ON o.id=m.organization_id JOIN satsa_users u ON u.id=m.user_id"
        " JOIN identities i ON i.identity_id=u.identity_id"
        " WHERE m.organization_id=? AND m.user_id=? AND m.status='active'"
        " AND o.status='active' AND u.status='active' AND i.status='active'",
        (org, user),
    )
    return row["role"] if row else None


class AnalysisExecutionService:
    """Caller-facing run operations. Tenant context is mandatory."""

    def __init__(
        self,
        engine,
        organization_id: str,
        user_id: str,
        *,
        audit=None,
        max_attempts: int = 3,
    ) -> None:
        if not organization_id or not user_id or max_attempts < 1:
            raise ValueError(
                "organization, user and positive max_attempts are required"
            )
        self.db = engine
        self.org = organization_id
        self.user = user_id
        self.tenant = TenantRepository(engine, organization_id, user_id)
        self.audit = audit
        if audit is None:
            raise ValueError("AuditService is required for analysis run state changes")
        self.max_attempts = max_attempts

    @staticmethod
    def _validate_key(key: str) -> None:
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= 128
            or any(ord(char) < 33 for char in key)
        ):
            raise DomainValidationError(
                "idempotency key must be 1-128 printable non-space characters"
            )

    def create_run(
        self,
        submission_version_id: str,
        *,
        idempotency_key: str,
        graph_enabled: bool = False,
        review_required: bool = False,
    ) -> dict:
        review_required = review_required or graph_enabled
        self.tenant._require(ANALYSIS_RUN)
        self._validate_key(idempotency_key)
        version = self.db.query_one(
            "SELECT v.id AS version_id,v.status,v.snapshot_digest,v.submission_id,"
            "s.entity_id,s.assessment_id FROM satsa_submission_versions v"
            " JOIN satsa_submissions s ON s.id=v.submission_id"
            " WHERE v.organization_id=? AND s.organization_id=? AND v.id=?",
            (self.org, self.org, submission_version_id),
        )
        if version is None:
            raise PermissionDeniedError(
                "submission version does not belong to organization"
            )
        if version["status"] != "valid":
            raise DomainValidationError(
                "analysis requires a validated submission version"
            )
        now = time.time()
        run_id = _id("run")
        correlation_id = str(uuid4())
        try:
            with self.db.transaction():
                existing = self.db.query_one(
                    "SELECT r.id FROM satsa_run_context c JOIN satsa_runs r ON r.id=c.run_id"
                    " WHERE c.organization_id=? AND c.submission_version_id=? AND c.idempotency_key=?",
                    (self.org, submission_version_id, idempotency_key),
                )
                if existing:
                    previous = self.get_run(existing["id"])
                    if (
                        bool(previous["graph_enabled"]) != graph_enabled
                        or bool(previous["review_required"]) != review_required
                    ):
                        raise DomainValidationError(
                            "idempotency key belongs to a different execution mode"
                        )
                    return previous
                self.db.execute(
                    "INSERT INTO satsa_runs (id,organization_id,entity_id,assessment_id,"
                    "snapshot_digest,code_version,analytics_version,status,started_at,"
                    "requested_at,requested_by_user_id,correlation_id,progress_total,"
                    "progress_completed,retry_count,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        self.org,
                        version["entity_id"],
                        version["assessment_id"],
                        version["snapshot_digest"] or "",
                        "",
                        ANALYTICS_VERSION,
                        "queued",
                        None,
                        now,
                        self.user,
                        correlation_id,
                        16,
                        0,
                        0,
                        now,
                    ),
                )
                self.db.execute(
                    "INSERT INTO satsa_run_context (run_id,organization_id,submission_id,"
                    "submission_version_id,idempotency_key,requested_by_user_id,requested_at,correlation_id,graph_enabled,review_required)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        self.org,
                        version["submission_id"],
                        submission_version_id,
                        idempotency_key,
                        self.user,
                        now,
                        correlation_id,
                        int(graph_enabled),
                        int(review_required),
                    ),
                )
                for worker in _default_workers(DEFAULT_FAST_CLOSURE_POLICY):
                    self.db.execute(
                        "INSERT INTO satsa_jobs (id,run_id,worker_name,status,created_at,"
                        "result_json,content_digest,attempt,retryable)"
                        " VALUES (?,?,?,'pending',?,'{}','',0,0)",
                        (
                            _stable_id("stage", run_id, worker.name),
                            run_id,
                            worker.name,
                            now,
                        ),
                    )
                self.db.execute(
                    "INSERT INTO satsa_execution_jobs (id,organization_id,run_id,status,"
                    "attempt_count,max_attempts,available_at,created_at,updated_at)"
                    " VALUES (?,?,?,'queued',0,?,?,?,?)",
                    (
                        _id("execution"),
                        self.org,
                        run_id,
                        self.max_attempts,
                        now,
                        now,
                        now,
                    ),
                )
            self._audit("analysis.run_queued", run_id, version_id=submission_version_id)
        except DuplicateEntryError:
            existing = self.db.query_one(
                "SELECT run_id FROM satsa_run_context WHERE organization_id=?"
                " AND submission_version_id=? AND idempotency_key=?",
                (self.org, submission_version_id, idempotency_key),
            )
            if not existing:
                raise
            run_id = existing["run_id"]
        result = self.get_run(run_id)
        if (
            bool(result["graph_enabled"]) != graph_enabled
            or bool(result["review_required"]) != review_required
        ):
            raise DomainValidationError(
                "idempotency key belongs to a different execution mode"
            )
        return result

    def get_run(self, run_id: str) -> dict:
        self.tenant._require(FINDING_VIEW)
        row = self.db.query_one(
            "SELECT r.*,c.submission_id,c.submission_version_id,c.graph_enabled,c.review_required,"
            "c.correlation_id AS execution_id"
            " FROM satsa_runs r JOIN satsa_run_context c ON c.run_id=r.id"
            " WHERE r.organization_id=? AND c.organization_id=? AND r.id=?",
            (self.org, self.org, run_id),
        )
        if row is None:
            raise PermissionDeniedError("analysis run does not belong to organization")
        row.pop("internal_error", None)
        row["run_id"] = row["id"]
        row["steps"] = [
            dict(step)
            for step in self.db.query_all(
                "SELECT j.worker_name,j.status,j.attempt,j.started_at,j.finished_at,"
                "CASE WHEN j.status='failed' THEN 'Analytical stage failed.' ELSE '' END AS error"
                " FROM satsa_jobs j"
                " JOIN satsa_runs r ON r.id=j.run_id WHERE r.organization_id=? AND r.id=?"
                " ORDER BY j.created_at,j.worker_name",
                (self.org, run_id),
            )
        ]
        return row

    def cancel(self, run_id: str) -> dict:
        self.tenant._require(REVIEW_CREATE)
        role = _membership_role(self.db, self.org, self.user)
        if role not in {"satsa_supervisor", "satsa_admin"}:
            raise PermissionDeniedError("only a supervisor may cancel an analysis run")
        with self.db.transaction():
            row = _lock_run(self.db, self.org, run_id)
            if row is None:
                raise PermissionDeniedError(
                    "analysis run does not belong to organization"
                )
            status = row["status"]
            if status in RUN_TERMINAL:
                return self.get_run(run_id)
            _transition(status, "cancel_requested")
            now = time.time()
            self.db.execute(
                "UPDATE satsa_runs SET status='cancel_requested' WHERE organization_id=? AND id=?",
                (self.org, run_id),
            )
            self.db.execute(
                "UPDATE satsa_execution_jobs SET status='cancel_requested',cancel_requested_at=?,updated_at=?"
                " WHERE organization_id=? AND run_id=? AND status IN ('queued','running','retry_wait','completed')",
                (now, now, self.org, run_id),
            )
        self._audit("analysis.cancel_requested", run_id)
        return self.get_run(run_id)

    def get_risk(self, run_id: str) -> dict | None:
        self.tenant._require(FINDING_VIEW)
        row = self.db.query_one(
            "SELECT k.profile_json,k.content_digest,k.algorithm_version,k.created_at"
            " FROM satsa_run_risk k JOIN satsa_run_context c ON c.run_id=k.run_id"
            " WHERE c.organization_id=? AND c.run_id=?",
            (self.org, run_id),
        )
        if row is None:
            if (
                self.db.query_one(
                    "SELECT run_id FROM satsa_run_context WHERE organization_id=? AND run_id=?",
                    (self.org, run_id),
                )
                is None
            ):
                raise PermissionDeniedError(
                    "analysis run does not belong to organization"
                )
            return None
        return {**row, "profile": json.loads(row["profile_json"])}

    def list_entity_priorities(self) -> list[dict]:
        """Rank this organization's entities for review attention.

        Uses each entity's most recent run that has a persisted risk
        profile (awaiting review, completed or partial) and the same
        priority function as the offline ranking. Nothing is recomputed
        from source data; only persisted, tenant-scoped results are read."""
        from types import SimpleNamespace

        from satsa.analysis.prioritize import _severity_of, entity_priority

        self.tenant._require(FINDING_VIEW)
        rows = self.db.query_all(
            "SELECT r.id AS run_id,r.entity_id,r.created_at,r.status,k.profile_json"
            " FROM satsa_runs r JOIN satsa_run_risk k ON k.run_id=r.id"
            " WHERE r.organization_id=? AND k.organization_id=?"
            " AND r.status IN ('awaiting_review','completed','partial')"
            " ORDER BY r.entity_id,r.created_at DESC,r.id DESC",
            (self.org, self.org),
        )
        latest: dict[str, dict] = {}
        for row in rows:
            latest.setdefault(row["entity_id"], row)
        items = []
        for row in latest.values():
            profile = json.loads(row["profile_json"])
            signals = self.db.query_all(
                "SELECT f.rule_or_category FROM satsa_findings f"
                " JOIN satsa_observations o ON o.id=f.observation_id"
                " JOIN satsa_runs r ON r.id=o.run_id"
                " WHERE r.organization_id=? AND r.id=? AND f.state='signal'",
                (self.org, row["run_id"]),
            )
            priority = entity_priority(
                SimpleNamespace(
                    entity_id=row["entity_id"],
                    run_id=row["run_id"],
                    total_score=float(profile.get("total_score", 0.0)),
                    confidence_bucket=profile.get("confidence_bucket", "very_low"),
                    dimensions=[
                        SimpleNamespace(name=d["name"], score=float(d["score"]))
                        for d in profile.get("dimensions", [])
                    ],
                    run_created_at=row["created_at"],
                    signal_findings=[
                        {"severity": _severity_of(s["rule_or_category"] or "")}
                        for s in signals
                    ],
                )
            )
            items.append({**priority.to_dict(), "run_status": row["status"]})
        items.sort(key=lambda p: (-p["priority_score"], p["entity_id"]))
        return items

    def list_recommendations(self, run_id: str) -> list[dict]:
        self.tenant._require(FINDING_VIEW)
        self.get_run(run_id)
        return self.db.query_all(
            "SELECT id,finding_id,action,recommendation_json,content_digest,created_at"
            " FROM satsa_run_recommendations WHERE organization_id=? AND run_id=?"
            " ORDER BY finding_id",
            (self.org, run_id),
        )

    def get_review_decision(self, run_id: str) -> dict | None:
        self.tenant._require(FINDING_VIEW)
        self.get_run(run_id)
        return self.db.query_one(
            "SELECT id,run_id,finding_id,user_id,principal_identity_id,action,reason,"
            "finding_content_digest,content_digest,created_at"
            " FROM satsa_run_review_decisions WHERE organization_id=? AND run_id=?",
            (self.org, run_id),
        )

    def get_trust_receipt(self, run_id: str) -> dict:
        self.tenant._require(EVIDENCE_VIEW)
        self.get_run(run_id)
        from satsa.analysis.trust import TrustService

        return TrustService(self.db, None, organization_id=self.org).get_final_receipt(
            run_id
        )

    def verify_trust(self, run_id: str) -> tuple[bool, str]:
        self.tenant._require(EVIDENCE_VIEW)
        self.get_run(run_id)
        from satsa.analysis.trust import TrustService

        return TrustService(
            self.db, None, organization_id=self.org
        ).verify_finalization(run_id, self.audit)

    def get_graph_progress(self, run_id: str) -> dict:
        """Return small authorized checkpoint references, never raw graph state."""
        run = self.get_run(run_id)
        if not run["graph_enabled"]:
            raise DomainValidationError("run is not graph supervised")
        from satsa.analysis.graph import durable_checkpointer

        with durable_checkpointer(self.db) as saver:
            checkpoint = saver.get_tuple(
                {"configurable": {"thread_id": f"satsa:{run_id}"}}
            )
        if checkpoint is None:
            return {"run_id": run_id, "checkpointed": False, "current_stage": "queued"}
        state = checkpoint.checkpoint.get("channel_values", {})
        if (
            state.get("run_id") != run_id
            or state.get("organization_id") != self.org
            or state.get("submission_version_id") != run["submission_version_id"]
        ):
            raise PermissionDeniedError("checkpoint scope does not match owned run")
        return {
            "run_id": run_id,
            "checkpointed": True,
            "current_stage": state.get("current_stage", ""),
            "awaiting_review": run["status"] == "awaiting_review",
        }

    def decide(self, run_id: str, *, action: str, reason: str = "") -> dict:
        """Record one attributable run-level supervisory decision and requeue.

        This extends the finding-scoped review model to the whole run, including
        runs with no findings. It uses the existing review action vocabulary.
        """
        self.tenant._require(REVIEW_CREATE)
        if _membership_role(self.db, self.org, self.user) not in {
            "satsa_supervisor",
            "satsa_admin",
        }:
            raise PermissionDeniedError("only a supervisor may decide an analysis run")
        # The existing finding review model also offers annotate and
        # request_review. Neither is a terminal run-level determination.
        if action not in {"confirm", "dismiss", "escalate"} or len(reason) > 4000:
            raise DomainValidationError("invalid supervisory action or reason")
        run = self.get_run(run_id)
        if not (run["graph_enabled"] or run["review_required"]):
            raise DomainValidationError("run is not supervised")
        existing = self.get_review_decision(run_id)
        if existing:
            if existing["action"] == action and existing["reason"] == reason:
                return existing
            raise DomainValidationError("supervisory decision already recorded")
        if run["status"] != "awaiting_review":
            raise DomainValidationError("run has not reached human review")
        finding = self.db.query_one(
            "SELECT f.* FROM satsa_findings f"
            " JOIN satsa_observations o ON o.id=f.observation_id"
            " JOIN satsa_runs r ON r.id=o.run_id"
            " WHERE r.organization_id=? AND r.id=? ORDER BY f.id LIMIT 1",
            (self.org, run_id),
        )
        identity = self.db.query_one(
            "SELECT identity_id FROM satsa_users WHERE id=?", (self.user,)
        )
        now = time.time()
        decision_id = _stable_id("runreview", run_id)
        from satsa.analysis.canonical import live_finding_digest

        document = {
            "run_id": run_id,
            "organization_id": self.org,
            "finding_id": finding["id"] if finding else None,
            "finding_content_digest": live_finding_digest(finding) if finding else "",
            "principal_identity_id": identity["identity_id"],
            "action": action,
            "reason": reason,
            "created_at": now,
        }
        with self.db.transaction():
            # Lock the run row first: competing decisions and a concurrent
            # cancel serialize here, and the checks below see their commits.
            current = _lock_run(self.db, self.org, run_id)
            prior = self.db.query_one(
                "SELECT id,action,reason FROM satsa_run_review_decisions"
                " WHERE organization_id=? AND run_id=?",
                (self.org, run_id),
            )
            if prior is not None:
                if prior["action"] == action and prior["reason"] == reason:
                    decision = self.get_review_decision(run_id)
                    assert decision is not None
                    return decision
                raise DomainValidationError("supervisory decision already recorded")
            if current is None or current["status"] != "awaiting_review":
                raise DomainValidationError("run is no longer awaiting review")
            self.db.execute(
                "INSERT INTO satsa_run_review_decisions"
                " (id,organization_id,run_id,finding_id,user_id,principal_identity_id,"
                "action,reason,finding_content_digest,content_digest,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    decision_id,
                    self.org,
                    run_id,
                    document["finding_id"],
                    self.user,
                    identity["identity_id"],
                    action,
                    reason,
                    document["finding_content_digest"],
                    digest_document(document),
                    now,
                ),
            )
            # Freeze the complete reviewed context atomically with the decision;
            # finalization must not sign changed results after human review.
            from satsa.analysis.canonical import supervisory_document

            reviewed = supervisory_document(self.db, self.org, run_id)
            reviewed.pop("review_context_digest")
            self.db.execute(
                "UPDATE satsa_run_review_decisions SET review_context_digest=? WHERE organization_id=? AND id=?",
                (digest_document(reviewed), self.org, decision_id),
            )
            self.db.execute(
                "UPDATE satsa_runs SET status='queued' WHERE organization_id=? AND id=?",
                (self.org, run_id),
            )
            self.db.execute(
                "UPDATE satsa_execution_jobs SET status='queued',attempt_count=0,available_at=?,"
                "updated_at=?,completed_at=NULL WHERE organization_id=? AND run_id=?"
                " AND status='completed'",
                (now, now, self.org, run_id),
            )
        self._audit("analysis.review_decided", run_id, decision_id=decision_id)
        decision = self.get_review_decision(run_id)
        assert decision is not None
        return decision

    def list_findings(
        self, run_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        self.tenant._require(FINDING_VIEW)
        if not 1 <= limit <= 500 or offset < 0:
            raise DomainValidationError("invalid pagination")
        if (
            self.db.query_one(
                "SELECT run_id FROM satsa_run_context WHERE organization_id=? AND run_id=?",
                (self.org, run_id),
            )
            is None
        ):
            raise PermissionDeniedError("analysis run does not belong to organization")
        return self.db.query_all(
            "SELECT f.* FROM satsa_findings f JOIN satsa_observations o ON o.id=f.observation_id"
            " JOIN satsa_runs r ON r.id=o.run_id WHERE r.organization_id=? AND r.id=?"
            " ORDER BY f.created_at,f.id LIMIT ? OFFSET ?",
            (self.org, run_id, limit, offset),
        )

    def get_finding(self, finding_id: str) -> dict:
        self.tenant._require(FINDING_VIEW)
        row = self.db.query_one(
            "SELECT f.*,o.run_id,r.organization_id FROM satsa_findings f"
            " JOIN satsa_observations o ON o.id=f.observation_id"
            " JOIN satsa_runs r ON r.id=o.run_id WHERE r.organization_id=? AND f.id=?",
            (self.org, finding_id),
        )
        if row is None:
            raise PermissionDeniedError("finding does not belong to organization")
        return row

    def list_evidence(self, run_id: str, *, limit: int = 100) -> list[dict]:
        """Return source records cited by this tenant-owned run's findings."""
        self.tenant._require(EVIDENCE_VIEW)
        if not 1 <= limit <= 500:
            raise DomainValidationError("invalid pagination")
        findings = self.list_findings(run_id, limit=500, offset=0)
        refs: list[str] = []
        for finding in findings:
            raw = finding.get("evidence_refs_json") or "[]"
            try:
                values = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, ValueError):
                values = []
            refs.extend(
                value
                for value in values
                if isinstance(value, str) and value.startswith("srcrec_")
            )
        refs = list(dict.fromkeys(refs))[:limit]
        if not refs:
            return []
        marks = ",".join("?" for _ in refs)
        return self.db.query_all(
            "SELECT sr.id AS source_record_id,sr.locator,sr.format,sr.file_digest,"
            "sr.original_record_digest,a.id AS artifact_id,a.category,a.sha3_256_digest,"
            "a.original_filename,r.content_digest AS canonical_record_digest,r.record_id"
            " FROM satsa_source_records sr JOIN satsa_artifacts a ON a.id=sr.artifact_id"
            " JOIN satsa_run_context c ON c.submission_id=sr.submission_id"
            " JOIN satsa_version_records r ON r.version_id=c.submission_version_id"
            " AND r.organization_id=c.organization_id AND r.source_record_id=sr.id"
            f" WHERE c.organization_id=? AND c.run_id=? AND a.organization_id=? AND sr.id IN ({marks})"
            " ORDER BY sr.id",
            (self.org, run_id, self.org, *refs),
        )

    def _audit(self, action: str, run_id: str, **metadata) -> None:
        if self.audit is None:
            return
        from qsmlops.security.audit.events import AuditEvent

        identity = self.db.query_one(
            "SELECT identity_id FROM satsa_users WHERE id=?", (self.user,)
        )
        self.audit.record(
            AuditEvent.create(
                actor=identity["identity_id"],
                action=action,
                resource=f"analysis_run:{run_id}",
                metadata={"organization_id": self.org, **metadata},
            )
        )


def _transition(current: str, target: str) -> None:
    if target not in RUN_TRANSITIONS.get(current, set()):
        raise DomainValidationError(
            f"invalid analysis run transition: {current} -> {target}"
        )


@dataclass(frozen=True)
class Lease:
    run_id: str
    organization_id: str
    worker_id: str
    generation: int
    attempt: int


class ExecutionQueue:
    """PostgreSQL atomic claim with SKIP LOCKED; SQLite BEGIN IMMEDIATE."""

    def __init__(self, engine, *, lease_seconds: float = 60.0) -> None:
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.db = engine
        self.lease_seconds = lease_seconds

    def claim(self, worker_id: str) -> dict | None:
        if not worker_id or len(worker_id) > 128:
            raise ValueError("worker_id is required and must be <=128 characters")
        now = time.time()
        with self.db.transaction():
            exhausted = self.db.query_all(
                "SELECT organization_id,run_id FROM satsa_execution_jobs"
                " WHERE status='running' AND lease_expires_at<=? AND attempt_count>=max_attempts",
                (now,),
            )
            for expired in exhausted:
                self.db.execute(
                    "UPDATE satsa_execution_jobs SET status='failed',error_code='lease_exhausted',"
                    "internal_error='worker lease expired after maximum attempts',updated_at=?,"
                    "completed_at=?,lease_owner='',lease_expires_at=NULL"
                    " WHERE organization_id=? AND run_id=? AND status='running'"
                    " AND lease_expires_at<=? AND attempt_count>=max_attempts",
                    (now, now, expired["organization_id"], expired["run_id"], now),
                )
                self.db.execute(
                    "UPDATE satsa_runs SET status='failed',error_code='lease_exhausted',"
                    "internal_error='worker lease expired after maximum attempts',"
                    "error='Analysis worker stopped before completion',finished_at=?"
                    " WHERE organization_id=? AND id=? AND status='running'",
                    (now, expired["organization_id"], expired["run_id"]),
                )
                from satsa.analysis.canonical import canonical_run_dict_from_row

                run = self.db.query_one(
                    "SELECT * FROM satsa_runs WHERE organization_id=? AND id=?",
                    (expired["organization_id"], expired["run_id"]),
                )
                if run is not None:
                    self.db.execute(
                        "UPDATE satsa_runs SET content_digest=? WHERE organization_id=? AND id=?",
                        (
                            digest_document(canonical_run_dict_from_row(run)),
                            expired["organization_id"],
                            expired["run_id"],
                        ),
                    )
            if self.db.dialect == "postgresql":
                candidate = self.db.query_one(
                    "SELECT id FROM satsa_execution_jobs WHERE"
                    " (status IN ('queued','retry_wait') AND available_at<=? AND attempt_count<max_attempts) OR"
                    " (status='cancel_requested' AND (lease_owner='' OR lease_expires_at<=?)) OR"
                    " (status='running' AND lease_expires_at<=? AND attempt_count<max_attempts)"
                    " ORDER BY available_at,created_at LIMIT 1 FOR UPDATE SKIP LOCKED",
                    (now, now, now),
                )
            else:
                candidate = self.db.query_one(
                    "SELECT id FROM satsa_execution_jobs WHERE"
                    " (status IN ('queued','retry_wait') AND available_at<=? AND attempt_count<max_attempts) OR"
                    " (status='cancel_requested' AND (lease_owner='' OR lease_expires_at<=?)) OR"
                    " (status='running' AND lease_expires_at<=? AND attempt_count<max_attempts)"
                    " ORDER BY available_at,created_at LIMIT 1",
                    (now, now, now),
                )
            if candidate is None:
                return None
            row = self.db.query_one(
                "SELECT * FROM satsa_execution_jobs WHERE id=?", (candidate["id"],)
            )
            generation = int(row["lease_generation"]) + 1
            attempt = int(row["attempt_count"]) + 1
            new_status = (
                "cancel_requested" if row["status"] == "cancel_requested" else "running"
            )
            self.db.execute(
                "UPDATE satsa_execution_jobs SET status=?,attempt_count=?,"
                "lease_owner=?,lease_generation=?,lease_expires_at=?,heartbeat_at=?,updated_at=?"
                " WHERE id=?",
                (
                    new_status,
                    attempt,
                    worker_id,
                    generation,
                    now + self.lease_seconds,
                    now,
                    now,
                    row["id"],
                ),
            )
            self.db.execute(
                "UPDATE satsa_runs SET status='running',started_at=COALESCE(started_at,?)"
                " WHERE organization_id=? AND id=? AND status IN ('queued','running','failed')",
                (now, row["organization_id"], row["run_id"]),
            )
            return {
                **row,
                "status": new_status,
                "lease_owner": worker_id,
                "lease_generation": generation,
                "attempt_count": attempt,
                "lease_expires_at": now + self.lease_seconds,
            }

    def heartbeat(self, run_id: str, worker_id: str, generation: int) -> bool:
        now = time.time()
        with self.db.transaction():
            self.db.execute(
                "UPDATE satsa_execution_jobs SET heartbeat_at=?,lease_expires_at=?,updated_at=?"
                " WHERE run_id=? AND status IN ('running','cancel_requested') AND lease_owner=? AND lease_generation=?"
                " AND lease_expires_at>?",
                (
                    now,
                    now + self.lease_seconds,
                    now,
                    run_id,
                    worker_id,
                    generation,
                    now,
                ),
            )
            return (
                self.db.query_one(
                    "SELECT run_id FROM satsa_execution_jobs WHERE run_id=?"
                    " AND status IN ('running','cancel_requested')"
                    " AND lease_owner=? AND lease_generation=? AND lease_expires_at>?",
                    (run_id, worker_id, generation, now),
                )
                is not None
            )

    def complete(self, lease: Lease, run_status: str) -> bool:
        if run_status not in {"completed", "partial", "cancelled"}:
            raise ValueError("invalid successful terminal status")
        now = time.time()
        with self.db.transaction():
            row = self._lease_row(lease, now)
            if row is None:
                return False
            if run_status in {"completed", "partial"}:
                context = self.db.query_one(
                    "SELECT graph_enabled,review_required FROM satsa_run_context WHERE organization_id=? AND run_id=?",
                    (lease.organization_id, lease.run_id),
                )
                if context and (context["graph_enabled"] or context["review_required"]):
                    finalized = self.db.query_one(
                        "SELECT f.id FROM satsa_trust_finalizations f"
                        " JOIN satsa_run_review_decisions d ON d.id=f.decision_id AND d.run_id=f.run_id"
                        " AND d.organization_id=f.organization_id WHERE f.organization_id=? AND f.run_id=?"
                        " AND f.state='verified' AND f.ledger_entry_hash IS NOT NULL",
                        (lease.organization_id, lease.run_id),
                    )
                    if finalized is None:
                        raise DomainValidationError(
                            "supervised completion requires verified finalization"
                        )
            run = self.db.query_one(
                "SELECT status FROM satsa_runs WHERE organization_id=? AND id=?",
                (lease.organization_id, lease.run_id),
            )
            if (
                run is not None
                and run["status"] == "cancel_requested"
                and run_status != "cancelled"
            ):
                # Cancellation after trust verification remains cancellation,
                # not an analytical failure with a misleading failure audit.
                raise CancelAtBoundary()
            if run is not None and run["status"] != run_status:
                _transition(run["status"], run_status)
            self.db.execute(
                "UPDATE satsa_execution_jobs SET status=?,completed_at=?,updated_at=?,"
                "lease_owner='',lease_expires_at=NULL WHERE run_id=?",
                (
                    "cancelled" if run_status == "cancelled" else "completed",
                    now,
                    now,
                    lease.run_id,
                ),
            )
            self.db.execute(
                "UPDATE satsa_runs SET status=?,finished_at=? WHERE organization_id=? AND id=?",
                (run_status, now, lease.organization_id, lease.run_id),
            )
            from satsa.analysis.canonical import canonical_run_dict_from_row

            run = self.db.query_one(
                "SELECT * FROM satsa_runs WHERE id=?", (lease.run_id,)
            )
            self.db.execute(
                "UPDATE satsa_runs SET content_digest=? WHERE organization_id=? AND id=?",
                (
                    digest_document(canonical_run_dict_from_row(run)),
                    lease.organization_id,
                    lease.run_id,
                ),
            )
            return True

    def pause_for_review(self, lease: Lease) -> bool:
        """Release the lease only after LangGraph has durably interrupted."""
        now = time.time()
        with self.db.transaction():
            if self._lease_row(lease, now) is None:
                return False
            current = self.db.query_one(
                "SELECT status FROM satsa_runs WHERE organization_id=? AND id=?",
                (lease.organization_id, lease.run_id),
            )
            _transition(current["status"], "awaiting_review")
            self.db.execute(
                "UPDATE satsa_runs SET status='awaiting_review'"
                " WHERE organization_id=? AND id=?",
                (lease.organization_id, lease.run_id),
            )
            # A completed queue item is inert until an authorized decision
            # explicitly requeues it. LangGraph retains the interrupt state.
            self.db.execute(
                "UPDATE satsa_execution_jobs SET status='completed',completed_at=?,"
                "updated_at=?,lease_owner='',lease_expires_at=NULL"
                " WHERE organization_id=? AND run_id=?",
                (now, now, lease.organization_id, lease.run_id),
            )
            return True

    def fail(self, lease: Lease, *, code: str, message: str, retryable: bool) -> str:
        now = time.time()
        with self.db.transaction():
            row = self._lease_row(lease, now)
            if row is None:
                return "lease_lost"
            cancel = row["status"] == "cancel_requested"
            retry = (
                not cancel and retryable and lease.attempt < int(row["max_attempts"])
            )
            status = "cancelled" if cancel else "retry_wait" if retry else "failed"
            delay = min(300.0, 2 ** max(0, lease.attempt - 1)) if retry else 0
            self.db.execute(
                "UPDATE satsa_execution_jobs SET status=?,available_at=?,error_code=?,"
                "internal_error=?,updated_at=?,lease_owner='',lease_expires_at=NULL"
                " WHERE run_id=?",
                (status, now + delay, code[:80], message[:4000], now, lease.run_id),
            )
            self.db.execute(
                "UPDATE satsa_runs SET status=?,retry_count=?,error_code=?,internal_error=?,"
                "error=?,finished_at=? WHERE organization_id=? AND id=?",
                (
                    "cancelled" if cancel else "queued" if retry else "failed",
                    max(0, lease.attempt - 1),
                    code[:80],
                    message[:4000],
                    "" if retry or cancel else "Analysis execution failed",
                    None if retry else now,
                    lease.organization_id,
                    lease.run_id,
                ),
            )
            return status

    def _lease_row(self, lease: Lease, now: float) -> dict | None:
        return self.db.query_one(
            "SELECT * FROM satsa_execution_jobs WHERE organization_id=? AND run_id=?"
            " AND status IN ('running','cancel_requested') AND lease_owner=?"
            " AND lease_generation=? AND lease_expires_at>?",
            (
                lease.organization_id,
                lease.run_id,
                lease.worker_id,
                lease.generation,
                now,
            ),
        )


class LeaseLost(RuntimeError):
    pass


class AnalysisExecutionWorker:
    """Separate worker process facade; executes persisted run references only."""

    def __init__(
        self,
        engine,
        *,
        worker_id: str | None = None,
        lease_seconds: float = 60.0,
        trust_key_dir: str | None = None,
        workers_factory: Callable | None = None,
        audit=None,
    ) -> None:
        self.db = engine
        self.worker_id = (
            worker_id or f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
        )
        self.queue = ExecutionQueue(engine, lease_seconds=lease_seconds)
        self.trust_key_dir = trust_key_dir
        self.workers_factory = workers_factory or (
            lambda: _default_workers(DEFAULT_FAST_CLOSURE_POLICY)
        )
        if audit is None:
            raise ValueError("AuditService is required for analysis worker execution")
        self.audit = audit

    def run_once(self) -> str | None:
        claimed = self.queue.claim(self.worker_id)
        if claimed is None:
            return None
        lease = Lease(
            claimed["run_id"],
            claimed["organization_id"],
            self.worker_id,
            claimed["lease_generation"],
            claimed["attempt_count"],
        )
        stop_heartbeat = threading.Event()
        lost_lease = threading.Event()

        def heartbeat_loop() -> None:
            interval = max(0.01, self.queue.lease_seconds / 3)
            while not stop_heartbeat.wait(interval):
                if not self.queue.heartbeat(
                    lease.run_id, lease.worker_id, lease.generation
                ):
                    lost_lease.set()
                    return

        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            daemon=True,
            name=f"satsa-heartbeat-{lease.run_id[-8:]}",
        )
        heartbeat_thread.start()
        try:
            context = self._resolve_context(lease)
            if context["graph_enabled"]:
                from satsa.analysis.graph import (
                    AnalysisGraphRuntime,
                    durable_checkpointer,
                )

                with durable_checkpointer(self.db) as checkpointer:
                    outcome = AnalysisGraphRuntime(
                        self, lease, context, checkpointer
                    ).run()
                if outcome == "awaiting_review":
                    if not self.queue.pause_for_review(lease):
                        raise LeaseLost("lease expired before review checkpoint")
                    self._audit_run_safely(lease, "analysis.awaiting_review")
                    return "awaiting_review"
            else:
                self._execute(lease, context)
                if context["review_required"] and self._finish(lease) != "failed":
                    self._persist_recommendations(lease)
                    decision = self.db.query_one(
                        "SELECT id FROM satsa_run_review_decisions WHERE organization_id=? AND run_id=?",
                        (lease.organization_id, lease.run_id),
                    )
                    if decision is None:
                        if not self.queue.pause_for_review(lease):
                            raise LeaseLost("lease expired before review")
                        self._audit_run_safely(lease, "analysis.awaiting_review")
                        return "awaiting_review"
            current = self._job_state(lease.run_id)
            status = (
                "cancelled"
                if current["status"] == "cancel_requested"
                else self._finish(lease)
            )
            if status == "cancelled":
                self._mark_pending_cancelled(lease)
                if not self.queue.complete(lease, "cancelled"):
                    raise LeaseLost(
                        "execution lease expired before cancellation finalization"
                    )
                self._audit_run_safely(lease, "analysis.cancelled")
            elif status == "failed":
                failed_stage = self.db.query_one(
                    "SELECT worker_name,error FROM satsa_jobs WHERE run_id=? AND status='failed'"
                    " ORDER BY worker_name LIMIT 1",
                    (lease.run_id,),
                )
                detail = (
                    f"{failed_stage['worker_name']}: {failed_stage['error']}"
                    if failed_stage
                    else "All analytical stages failed"
                )
                outcome = self.queue.fail(
                    lease,
                    code="analytical_stage_failed",
                    message=detail,
                    retryable=False,
                )
                if outcome != "lease_lost":
                    self._audit_run_safely(lease, "analysis.failed")
                return outcome
            else:
                if context["graph_enabled"] or context["review_required"]:
                    self._finalize_supervisory(lease)
                if not self.queue.complete(lease, status):
                    raise LeaseLost("execution lease expired before finalization")
                self._audit_run_safely(lease, f"analysis.{status}")
                if status in {"completed", "partial"}:
                    self._attest_if_configured(lease, [])
            return status
        except CancelAtBoundary:
            self._mark_pending_cancelled(lease)
            if not self.queue.complete(lease, "cancelled"):
                return "lease_lost"
            self._audit_run_safely(lease, "analysis.cancelled")
            return "cancelled"
        except LeaseLost:
            log.info(
                "analysis lease lost",
                extra={"run_id": lease.run_id, "execution_id": lease.run_id},
            )
            return "lease_lost"
        except Exception as exc:  # durable internal diagnostic; generic external error
            log.exception(
                "analysis execution failed",
                extra={"run_id": lease.run_id, "execution_id": lease.run_id},
            )
            retryable = isinstance(exc, RetryableAnalysisError)
            outcome = self.queue.fail(
                lease,
                code=getattr(exc, "code", "analysis_failed"),
                message=f"{type(exc).__name__}: {exc}",
                retryable=retryable,
            )
            if outcome != "lease_lost":
                action = (
                    "analysis.retry_scheduled"
                    if outcome == "retry_wait"
                    else "analysis.failed"
                )
                self._audit_run_safely(lease, action)
            return outcome
        finally:
            stop_heartbeat.set()
            heartbeat_thread.join(timeout=max(0.2, self.queue.lease_seconds / 2))
        if lost_lease.is_set():
            return "lease_lost"

    def _resolve_context(self, lease: Lease) -> dict:
        row = self.db.query_one(
            "SELECT r.*,c.submission_id,c.submission_version_id,c.graph_enabled,c.review_required,"
            "c.organization_id AS context_org"
            " FROM satsa_runs r JOIN satsa_run_context c ON c.run_id=r.id"
            " JOIN satsa_submissions s ON s.id=c.submission_id AND s.organization_id=c.organization_id"
            " JOIN satsa_submission_versions v ON v.id=c.submission_version_id"
            " AND v.organization_id=c.organization_id AND v.submission_id=c.submission_id"
            " JOIN satsa_entities e ON e.id=s.entity_id AND e.organization_id=s.organization_id"
            " JOIN satsa_assessments a ON a.id=s.assessment_id AND a.entity_id=e.id"
            " AND a.organization_id=e.organization_id"
            " WHERE r.id=? AND r.organization_id=? AND c.organization_id=?"
            " AND r.entity_id=s.entity_id AND r.assessment_id=s.assessment_id AND v.status='valid'",
            (lease.run_id, lease.organization_id, lease.organization_id),
        )
        if row is None:
            raise PermissionDeniedError("persisted run scope is inconsistent")
        if (
            row["entity_id"]
            != self.db.query_one(
                "SELECT entity_id FROM satsa_submissions WHERE id=? AND organization_id=?",
                (row["submission_id"], lease.organization_id),
            )["entity_id"]
        ):
            raise PermissionDeniedError("run entity does not match owned submission")
        return row

    def _load_dataset(self, context: dict, org: str) -> CanonicalDataset:
        rows = self.db.query_all(
            "SELECT category,payload_json,content_digest,source_record_id FROM satsa_version_records"
            " WHERE organization_id=? AND version_id=? ORDER BY category,record_id",
            (org, context["submission_version_id"]),
        )
        records: dict[str, list] = {name: [] for name in _CATEGORY_TYPES}
        categories = set()
        for row in rows:
            cls = _CATEGORY_TYPES.get(row["category"])
            if cls is None:
                continue
            payload = json.loads(row["payload_json"])
            records[row["category"]].append(cls.from_dict(payload))
            categories.add(row["category"])
        report = self.db.query_one(
            "SELECT report_json FROM satsa_validation_reports WHERE organization_id=? AND version_id=?",
            (org, context["submission_version_id"]),
        )
        if report:
            data = json.loads(report["report_json"])
            categories.update(
                name
                for name, info in (data.get("categories") or {}).items()
                if info.get("accepted", 0) or info.get("present", False)
            )
        assessment = self.db.query_one(
            "SELECT a.period_start,a.period_end FROM satsa_assessments a"
            " JOIN satsa_entities e ON e.id=a.entity_id"
            " WHERE e.organization_id=? AND a.id=? AND e.id=?",
            (org, context["assessment_id"], context["entity_id"]),
        )
        if assessment is None:
            raise PermissionDeniedError(
                "assessment does not belong to run organization"
            )
        return CanonicalDataset(
            entity_id=context["entity_id"],
            assessment_id=context["assessment_id"],
            snapshot_digest=context["snapshot_digest"] or "",
            period_start=assessment["period_start"],
            period_end=assessment["period_end"],
            alerts=records["alerts"],
            cases=records["cases"],
            assets=records["assets"],
            steps=records["investigation_steps"],
            escalations=records["escalations"],
            dispositions=records["dispositions"],
            submitted_categories=frozenset(categories),
        )

    def _execute(self, lease: Lease, context: dict) -> None:
        dataset = self._load_dataset(context, lease.organization_id)
        run_context = RunContext(
            run_id=lease.run_id,
            entity_id=context["entity_id"],
            assessment_id=context["assessment_id"],
            code_version="",
            created_at=context["requested_at"],
            extras={},
        )
        snapshot = SnapshotRef(
            context["snapshot_digest"] or "",
            context["entity_id"],
            context["assessment_id"],
        )
        workers = list(self.workers_factory())
        configured_names = {worker.name for worker in workers}
        for worker in workers:
            existing = self.db.query_one(
                "SELECT status FROM satsa_jobs WHERE run_id=? AND worker_name=?",
                (lease.run_id, worker.name),
            )
            if existing is None:
                self.db.execute(
                    "INSERT INTO satsa_jobs (id,run_id,worker_name,status,created_at,"
                    "result_json,content_digest,attempt,retryable) VALUES (?,?,?,'pending',?,'{}','',0,0)",
                    (
                        _stable_id("stage", lease.run_id, worker.name),
                        lease.run_id,
                        worker.name,
                        time.time(),
                    ),
                )
        for stage in self.db.query_all(
            "SELECT worker_name FROM satsa_jobs WHERE run_id=? AND status='pending'",
            (lease.run_id,),
        ):
            if stage["worker_name"] not in configured_names:
                self.db.execute(
                    "UPDATE satsa_jobs SET status='skipped',finished_at=?"
                    " WHERE run_id=? AND worker_name=? AND status='pending'",
                    (time.time(), lease.run_id, stage["worker_name"]),
                )
        orch = Orchestrator()
        for worker in workers:
            if worker.name == "peer-benchmark":
                from satsa.analysis.workers import (
                    attach_baseline,
                )

                # Baseline provider below is intentionally organization-bound.
                attach_baseline(
                    worker,
                    self._organization_peer_baseline(
                        context, lease.organization_id, worker.thresholds.min_peers
                    ),
                )
            orch.register(worker)

        def before(name: str) -> None:
            self._assert_lease(lease)
            if self._cancel_requested(lease.run_id, lease.organization_id):
                raise CancelAtBoundary()
            self._step_start(lease, name)

        def after(job: Job) -> None:
            self._persist_stage(lease, context, job)

        try:
            jobs = orch.run(
                run_context,
                snapshot,
                dataset,
                [],
                None,
                before_worker=before,
                after_worker=after,
                skip_workers=self._completed_worker_names(lease.run_id),
                is_retryable_exception=lambda exc: isinstance(
                    exc, RetryableAnalysisError
                ),
            )
        except CancelAtBoundary:
            return
        if self._cancel_requested(lease.run_id, lease.organization_id):
            return
        retryable_job = next((job for job in jobs if job.retryable), None)
        if retryable_job is not None:
            raise RetryableAnalysisError(
                f"transient analytical worker failure: {retryable_job.worker_name}"
            )
        self._persist_risk(lease, context)

    def _organization_peer_baseline(self, context: dict, org: str, min_peers: int):
        # No cross-organization reads. Hosted population baselines currently
        # abstain until a governed aggregate service is introduced.
        from satsa.analysis.workers.peer_benchmark import METRIC_KEYS, PeerBaseline

        entity = self.db.query_one(
            "SELECT sector,environment_class FROM satsa_entities"
            " WHERE organization_id=? AND id=?",
            (org, context["entity_id"]),
        )
        cohort = (entity["sector"], entity["environment_class"]) if entity else ()
        empty = {
            key: {"median": 0.0, "mad": 0.0, "p25": 0.0, "p75": 0.0, "count": 0}
            for key in METRIC_KEYS
        }
        return PeerBaseline(context["entity_id"], cohort, "", empty, 0)

    def _completed_worker_names(self, run_id: str) -> set[str]:
        return {
            row["worker_name"]
            for row in self.db.query_all(
                "SELECT worker_name FROM satsa_jobs WHERE run_id=? AND status='completed'",
                (run_id,),
            )
        }

    def _step_start(self, lease: Lease, name: str) -> None:
        now = time.time()
        with self.db.transaction():
            self._assert_lease(lease)
            self.db.execute(
                "UPDATE satsa_jobs SET status='running',started_at=COALESCE(started_at,?),"
                "finished_at=NULL,error='',attempt=attempt+1 WHERE run_id=? AND worker_name=?",
                (now, lease.run_id, name),
            )

    def _persist_stage(self, lease: Lease, context: dict, job: Job) -> None:
        now = time.time()
        with self.db.transaction():
            self._assert_lease(lease)
            if job.status != "completed" or job.result is None:
                self.db.execute(
                    "UPDATE satsa_jobs SET status='failed',finished_at=?,error=?,"
                    "retryable=?,content_digest=? WHERE run_id=? AND worker_name=?",
                    (
                        now,
                        job.error[:2000],
                        int(job.retryable),
                        digest_document(job.to_dict()),
                        lease.run_id,
                        job.worker_name,
                    ),
                )
                return
            result = job.result
            obs_id = _stable_id("observation", lease.run_id, job.worker_name)
            observation = Observation(
                id=obs_id,
                run_id=lease.run_id,
                worker_name=result.worker_name,
                detector_version=result.detector_version,
                entity_id=context["entity_id"],
                assessment_id=context["assessment_id"],
                scope=dict(result.scope),
                created_at=now,
            )
            self.db.execute(
                "INSERT INTO satsa_observations (id,run_id,worker_name,detector_version,"
                "entity_id,assessment_id,scope_json,state,created_at,content_digest)"
                " VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                (
                    obs_id,
                    lease.run_id,
                    result.worker_name,
                    result.detector_version,
                    context["entity_id"],
                    context["assessment_id"],
                    _j(result.scope),
                    result.state,
                    now,
                    digest_document(observation.to_dict()),
                ),
            )
            finding_ids = []
            for index, finding in enumerate(result.findings):
                if not isinstance(finding, Finding):
                    continue
                finding.observation_id = obs_id
                if finding.validate():
                    log.warning(
                        "invalid finding withheld",
                        extra={"run_id": lease.run_id, "worker": job.worker_name},
                    )
                    continue
                finding.id = _stable_id(
                    "finding",
                    lease.run_id,
                    job.worker_name,
                    str(index),
                    finding.rule_or_category,
                )
                finding_ids.append(finding.id)
                self.db.execute(
                    "INSERT INTO satsa_findings (id,observation_id,rule_or_category,state,"
                    "rationale,scoped_subjects_json,statistic,effect,threshold,confidence_json,"
                    "evidence_refs_json,limitations,created_at,content_digest)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                    (
                        finding.id,
                        obs_id,
                        finding.rule_or_category,
                        finding.state,
                        finding.rationale,
                        _j(finding.scoped_subjects),
                        finding.statistic,
                        finding.effect,
                        finding.threshold,
                        _j(
                            finding.confidence.to_dict() if finding.confidence else {},
                            "{}",
                        ),
                        _j(finding.evidence_refs),
                        finding.limitations,
                        now,
                        _d(finding),
                    ),
                )
            self.db.execute(
                "UPDATE satsa_jobs SET status='completed',finished_at=?,error='',result_json=?,"
                "content_digest=?,retryable=0 WHERE run_id=? AND worker_name=?",
                (
                    now,
                    _j(
                        {
                            "observation_id": obs_id,
                            "finding_ids": finding_ids,
                            "batch": result.to_dict(),
                        },
                        "{}",
                    ),
                    digest_document(job.to_dict()),
                    lease.run_id,
                    job.worker_name,
                ),
            )
            ids = {
                row["id"]
                for row in self.db.query_all(
                    "SELECT o.id FROM satsa_observations o JOIN satsa_runs r ON r.id=o.run_id"
                    " WHERE r.organization_id=? AND r.id=?",
                    (lease.organization_id, lease.run_id),
                )
            }
            fids = [
                row["id"]
                for row in self.db.query_all(
                    "SELECT f.id FROM satsa_findings f JOIN satsa_observations o ON o.id=f.observation_id"
                    " JOIN satsa_runs r ON r.id=o.run_id WHERE r.organization_id=? AND r.id=?",
                    (lease.organization_id, lease.run_id),
                )
            ]
            completed = self.db.query_one(
                "SELECT COUNT(*) AS n FROM satsa_jobs WHERE run_id=?"
                " AND status IN ('completed','failed','skipped')",
                (lease.run_id,),
            )["n"]
            self.db.execute(
                "UPDATE satsa_runs SET observation_ids_json=?,finding_ids_json=?,"
                "progress_completed=?,content_digest=? WHERE organization_id=? AND id=?",
                (
                    _j(sorted(ids)),
                    _j(fids),
                    completed,
                    self._run_digest(lease.run_id),
                    lease.organization_id,
                    lease.run_id,
                ),
            )

    def _persist_risk(self, lease: Lease, context: dict) -> None:
        from satsa.analysis.risk import compute_entity_risk

        profile = compute_entity_risk(
            self._ScopedRiskEngine(self.db, lease.organization_id),
            context["entity_id"],
            run_id=lease.run_id,
        )
        content = profile.to_dict()
        now = time.time()
        self.db.execute(
            "INSERT INTO satsa_run_risk (run_id,organization_id,profile_json,content_digest,"
            "algorithm_version,created_at) VALUES (?,?,?,?,?,?) ON CONFLICT(run_id) DO NOTHING",
            (
                lease.run_id,
                lease.organization_id,
                _j(content, "{}"),
                digest_document(content),
                "satsa-risk/1",
                now,
            ),
        )

    def _persist_recommendations(self, lease: Lease) -> int:
        from satsa.analysis.recommend import recommend

        findings = self.db.query_all(
            "SELECT f.id,f.rule_or_category,f.evidence_refs_json FROM satsa_findings f"
            " JOIN satsa_observations o ON o.id=f.observation_id"
            " JOIN satsa_runs r ON r.id=o.run_id"
            " WHERE r.organization_id=? AND r.id=? ORDER BY f.id",
            (lease.organization_id, lease.run_id),
        )
        with self.db.transaction():
            self._assert_lease(lease)
            for finding in findings:
                item = recommend(
                    {
                        "id": finding["id"],
                        "rule_or_category": finding["rule_or_category"],
                        "evidence_refs": json.loads(
                            finding["evidence_refs_json"] or "[]"
                        ),
                    }
                ).to_dict()
                self.db.execute(
                    "INSERT INTO satsa_run_recommendations"
                    " (id,organization_id,run_id,finding_id,action,recommendation_json,"
                    "content_digest,created_at) VALUES (?,?,?,?,?,?,?,?)"
                    " ON CONFLICT(run_id,finding_id) DO NOTHING",
                    (
                        _stable_id("recommendation", lease.run_id, finding["id"]),
                        lease.organization_id,
                        lease.run_id,
                        finding["id"],
                        item["action"],
                        _j(item, "{}"),
                        digest_document(item),
                        time.time(),
                    ),
                )
        return len(findings)

    class _ScopedRiskEngine:
        def __init__(self, db, org):
            self.db, self.org = db, org

        def query_one(self, sql, params=()):
            if "FROM satsa_runs" in sql and "WHERE entity_id=?" in sql:
                sql = sql.replace(
                    "WHERE entity_id=?", "WHERE organization_id=? AND entity_id=?"
                )
                params = (self.org,) + tuple(params)
            return self.db.query_one(sql, params)

        def query_all(self, sql, params=()):
            if "FROM satsa_findings" in sql:
                sql = sql.replace(
                    "WHERE observation_id IN (SELECT id FROM satsa_observations WHERE run_id=?)",
                    "WHERE observation_id IN (SELECT o.id FROM satsa_observations o"
                    " JOIN satsa_runs r ON r.id=o.run_id WHERE r.organization_id=? AND o.run_id=?)",
                )
                params = (self.org,) + tuple(params)
            return self.db.query_all(sql, params)

    def _finalize_supervisory(self, lease: Lease) -> dict:
        self._assert_lease(lease)
        if self._cancel_requested(lease.run_id, lease.organization_id):
            raise CancelAtBoundary()
        if not self.trust_key_dir:
            raise DomainValidationError(
                "supervisory finalization requires SATSA_TRUST_KEY_DIR"
            )
        from pathlib import Path

        from satsa.analysis.trust import TrustService

        try:

            def boundary(_stage):
                self._assert_lease(lease)
                if self._cancel_requested(lease.run_id, lease.organization_id):
                    raise CancelAtBoundary()

            return TrustService(
                self.db, Path(self.trust_key_dir), organization_id=lease.organization_id
            ).finalize(lease.run_id, self.audit, boundary=boundary)
        except OSError as exc:
            raise RetryableAnalysisError(
                "trust storage temporarily unavailable"
            ) from exc

    def _attest_if_configured(self, lease: Lease, jobs: list[Job]) -> None:
        # Existing TRUST-SAT persistence is explicitly offline-SQLite-only.
        # Hosted execution records its run digest/provenance without claiming
        # a signature; hosted tenant-scoped receipt support is a later task.
        if not self.trust_key_dir or self.db.dialect != "sqlite":
            return
        from satsa.analysis.trust import attest_run_outputs

        run = self.db.query_one(
            "SELECT * FROM satsa_runs WHERE organization_id=? AND id=?",
            (lease.organization_id, lease.run_id),
        )
        findings = self.db.query_all(
            "SELECT f.* FROM satsa_findings f JOIN satsa_observations o ON o.id=f.observation_id"
            " WHERE o.run_id=?",
            (lease.run_id,),
        )
        try:
            summary = attest_run_outputs(self.db, self.trust_key_dir, run, findings)
            old = json.loads(run["summary_json"] or "{}")
            old["trust"] = summary
            self.db.execute(
                "UPDATE satsa_runs SET summary_json=? WHERE id=?",
                (_j(old, "{}"), lease.run_id),
            )
        except Exception:
            log.exception(
                "TRUST-SAT attestation failed", extra={"run_id": lease.run_id}
            )

    def _run_digest(self, run_id: str) -> str:
        from satsa.analysis.canonical import canonical_run_dict_from_row

        row = self.db.query_one("SELECT * FROM satsa_runs WHERE id=?", (run_id,))
        return digest_document(canonical_run_dict_from_row(row))

    def _assert_lease(self, lease: Lease) -> None:
        now = time.time()
        row = self.db.query_one(
            "SELECT run_id FROM satsa_execution_jobs WHERE organization_id=? AND run_id=?"
            " AND status IN ('running','cancel_requested') AND lease_owner=?"
            " AND lease_generation=? AND lease_expires_at>?",
            (
                lease.organization_id,
                lease.run_id,
                lease.worker_id,
                lease.generation,
                now,
            ),
        )
        if row is None:
            raise LeaseLost("execution lease expired or was reclaimed")

    def _cancel_requested(self, run_id: str, org: str) -> bool:
        row = self.db.query_one(
            "SELECT status FROM satsa_execution_jobs WHERE organization_id=? AND run_id=?",
            (org, run_id),
        )
        return bool(row and row["status"] == "cancel_requested")

    def _job_state(self, run_id: str) -> dict:
        row = self.db.query_one("SELECT * FROM satsa_runs WHERE id=?", (run_id,))
        if row is None:
            raise PermissionDeniedError("analysis run missing")
        return row

    def _finish(self, lease: Lease) -> str:
        failed = self.db.query_one(
            "SELECT COUNT(*) AS n FROM satsa_jobs WHERE run_id=? AND status='failed'",
            (lease.run_id,),
        )["n"]
        completed = self.db.query_one(
            "SELECT COUNT(*) AS n FROM satsa_jobs WHERE run_id=? AND status='completed'",
            (lease.run_id,),
        )["n"]
        return (
            "partial" if failed and completed else "failed" if failed else "completed"
        )

    def _mark_pending_cancelled(self, lease: Lease) -> None:
        self.db.execute(
            "UPDATE satsa_jobs SET status='cancelled',finished_at=? WHERE run_id=? AND status='pending'",
            (time.time(), lease.run_id),
        )

    def _audit_run(self, lease: Lease, action: str) -> None:
        row = self.db.query_one(
            "SELECT u.identity_id FROM satsa_run_context c JOIN satsa_users u"
            " ON u.id=c.requested_by_user_id WHERE c.organization_id=? AND c.run_id=?",
            (lease.organization_id, lease.run_id),
        )
        if row is None:
            raise PermissionDeniedError(
                "run requester identity is unavailable for audit"
            )
        from qsmlops.security.audit.events import AuditEvent

        self.audit.record(
            AuditEvent.create(
                actor=row["identity_id"],
                action=action,
                resource=f"analysis_run:{lease.run_id}",
                metadata={
                    "organization_id": lease.organization_id,
                    "worker_id": lease.worker_id,
                    "attempt": lease.attempt,
                },
            )
        )

    def _audit_run_safely(self, lease: Lease, action: str) -> None:
        try:
            self._audit_run(lease, action)
        except Exception:
            log.exception(
                "analysis audit append failed",
                extra={"run_id": lease.run_id, "action": action},
            )


class CancelAtBoundary(Exception):
    pass


class RetryableAnalysisError(RuntimeError):
    code = "transient_analysis_error"


def worker_main() -> int:
    """CLI entry point for a separately deployed analysis worker."""
    import signal
    import threading

    configure_logging(
        os.getenv("SATSA_LOG_LEVEL", "INFO"),
        json_format=os.getenv("SATSA_ENVIRONMENT", "development").lower()
        == "production",
    )

    from satsa.api.runtime import build_runtime

    engine, audit, _identity, storage, trust_key_dir = build_runtime()
    worker = AnalysisExecutionWorker(
        engine,
        trust_key_dir=str(trust_key_dir),
        audit=audit,
    )
    stopping = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signum, _frame: stopping.set())
    signal.signal(signal.SIGINT, lambda _signum, _frame: stopping.set())
    try:
        idle = 0
        while not stopping.is_set():
            outcome = worker.run_once()
            if outcome is None:
                idle += 1
                stopping.wait(min(2.0, 0.1 * idle))
            else:
                idle = 0
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        storage.close()
        engine.close()
