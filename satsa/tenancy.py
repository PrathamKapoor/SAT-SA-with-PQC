"""Phase 1 tenant-owned repository and persistent hosted session primitives.

Provisioning methods are internal administration operations; no public route
is registered for them. Normal resource methods bind both organization and
user and repeat membership/role checks on every operation.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from enum import Enum
from uuid import uuid4

from qsmlops.core.errors import PermissionDeniedError
from qsmlops.crypto.hashing import digest_document
from qsmlops.security.permissions.model import (
    ANALYSIS_RUN, FINDING_VIEW, EVIDENCE_VIEW, REVIEW_READ, TRUST_VERIFY,
    SATSA_ROLE_NAMES, has_permission,
)
from satsa.domain.entities import Assessment, Entity
from satsa.errors import DomainValidationError


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def require_offline_store(engine) -> None:
    """Prevent legacy unscoped SAT-SA stores from accessing hosted data."""
    if getattr(engine, "dialect", None) == "postgresql":
        raise PermissionDeniedError(
            "legacy SAT-SA stores are offline-only; use a tenant-bound repository"
        )


class PeerAccessPolicy(str, Enum):
    ORGANIZATION_ONLY = "organization_only"
    AUTHORIZED_AGGREGATE = "authorized_aggregate"


class TenantAdministration:
    """Trusted provisioning layer; callers must authorize administrators."""

    def __init__(self, engine) -> None:
        self._db = engine

    def create_organization(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise DomainValidationError("organization name is required")
        organization_id = _id("org")
        self._db.execute(
            "INSERT INTO satsa_organizations (id, name, created_at) VALUES (?,?,?)",
            (organization_id, name, time.time()),
        )
        return organization_id

    def create_user(self, identity_id: str, email: str) -> str:
        identity = self._db.query_one(
            "SELECT kind, status FROM identities WHERE identity_id=?", (identity_id,)
        )
        if identity is None or identity["kind"] != "human" or identity["status"] != "active":
            raise DomainValidationError("active human identity is required")
        email = email.strip().lower()
        if not email or "@" not in email:
            raise DomainValidationError("valid email is required")
        user_id = _id("usr")
        self._db.execute(
            "INSERT INTO satsa_users (id, identity_id, email, created_at) VALUES (?,?,?,?)",
            (user_id, identity_id, email, time.time()),
        )
        return user_id

    def add_membership(self, organization_id: str, user_id: str, role: str) -> None:
        if role not in SATSA_ROLE_NAMES:
            raise DomainValidationError("unknown SAT-SA organization role")
        self._db.execute(
            "INSERT INTO satsa_memberships (organization_id, user_id, role, created_at)"
            " VALUES (?,?,?,?)", (organization_id, user_id, role, time.time()),
        )

    def set_membership_status(self, organization_id: str, user_id: str, status: str) -> None:
        if status not in {"active", "revoked"}:
            raise DomainValidationError("invalid membership status")
        self._db.execute(
            "UPDATE satsa_memberships SET status=? WHERE organization_id=? AND user_id=?",
            (status, organization_id, user_id),
        )


class TenantRepository:
    """SAT-SA resource access with mandatory tenant and member context."""

    def __init__(self, engine, organization_id: str, user_id: str, *,
                 peer_policy: PeerAccessPolicy = PeerAccessPolicy.ORGANIZATION_ONLY) -> None:
        if not organization_id or not user_id:
            raise PermissionDeniedError("organization and user context are required")
        self._db = engine
        self.organization_id = organization_id
        self.user_id = user_id
        self.peer_policy = PeerAccessPolicy(peer_policy)

    def _require(self, permission: str) -> None:
        membership = self._db.query_one(
            "SELECT m.role FROM satsa_memberships m"
            " JOIN satsa_organizations o ON o.id=m.organization_id"
            " JOIN satsa_users u ON u.id=m.user_id"
            " JOIN identities i ON i.identity_id=u.identity_id"
            " WHERE m.organization_id=? AND m.user_id=?"
            " AND m.status='active' AND o.status='active'"
            " AND u.status='active' AND i.status='active'",
            (self.organization_id, self.user_id),
        )
        if membership is None or not has_permission({membership["role"]}, permission):
            raise PermissionDeniedError("organization membership or permission denied")

    def create_entity(self, display_name: str, *, sector: str = "",
                      environment_class: str = "") -> str:
        self._require(ANALYSIS_RUN)
        entity = Entity(display_name=display_name.strip(), sector=sector,
                        environment_class=environment_class)
        errors = entity.validate()
        if errors:
            raise DomainValidationError("; ".join(errors))
        self._db.execute(
            "INSERT INTO satsa_entities (id, organization_id, display_name, sector,"
            " environment_class, cohort_attributes_json, access_scope, schema_version,"
            " content_digest, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (entity.id, self.organization_id, entity.display_name, entity.sector,
             entity.environment_class, "{}", "", entity.schema_version,
             digest_document(entity.to_dict()), time.time()),
        )
        return entity.id

    def get_entity(self, entity_id: str) -> dict | None:
        self._require(FINDING_VIEW)
        return self._db.query_one(
            "SELECT * FROM satsa_entities WHERE organization_id=? AND id=?",
            (self.organization_id, entity_id),
        )

    def list_entities(self) -> list[dict]:
        self._require(FINDING_VIEW)
        return self._db.query_all(
            "SELECT * FROM satsa_entities WHERE organization_id=? ORDER BY display_name",
            (self.organization_id,),
        )

    def peer_entity_ids(self, entity_id: str) -> list[str]:
        """Return only local peer IDs; aggregate sharing has no raw-ID path."""
        self._require(FINDING_VIEW)
        if self.peer_policy is PeerAccessPolicy.AUTHORIZED_AGGREGATE:
            raise PermissionDeniedError(
                "cross-organization peer aggregates require a governed aggregate service"
            )
        entity = self._db.query_one(
            "SELECT sector, environment_class FROM satsa_entities"
            " WHERE organization_id=? AND id=?", (self.organization_id, entity_id),
        )
        if entity is None:
            raise PermissionDeniedError("entity does not belong to organization")
        return [row["id"] for row in self._db.query_all(
            "SELECT id FROM satsa_entities WHERE organization_id=? AND id<>?"
            " AND sector=? AND environment_class=? ORDER BY id",
            (self.organization_id, entity_id, entity["sector"],
             entity["environment_class"]),
        )]

    def create_assessment(self, entity_id: str, period_start: float, period_end: float) -> str:
        self._require(ANALYSIS_RUN)
        if self._db.query_one(
            "SELECT id FROM satsa_entities WHERE organization_id=? AND id=?",
            (self.organization_id, entity_id),
        ) is None:
            raise PermissionDeniedError("entity does not belong to organization")
        assessment = Assessment(entity_id=entity_id, period_start=float(period_start),
                                period_end=float(period_end), status="open")
        errors = assessment.validate()
        if errors:
            raise DomainValidationError("; ".join(errors))
        self._db.execute(
            "INSERT INTO satsa_assessments (id, organization_id, entity_id, period_start,"
            " period_end, timezone, policy_version, status, schema_version, content_digest,"
            " created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (assessment.id, self.organization_id, entity_id,
             assessment.period_start, assessment.period_end,
             assessment.timezone, assessment.policy_version, assessment.status,
             assessment.schema_version, digest_document(assessment.to_dict()), time.time()),
        )
        return assessment.id

    def get_assessment(self, assessment_id: str) -> dict | None:
        self._require(FINDING_VIEW)
        return self._db.query_one(
            "SELECT * FROM satsa_assessments WHERE organization_id=? AND id=?",
            (self.organization_id, assessment_id),
        )

    def close_assessment(self, assessment_id: str) -> None:
        self._require(ANALYSIS_RUN)
        row = self._db.query_one(
            "SELECT * FROM satsa_assessments WHERE organization_id=? AND id=?",
            (self.organization_id, assessment_id),
        )
        if row is None:
            raise PermissionDeniedError("assessment does not belong to organization")
        assessment = Assessment.from_dict({**row, "status": "closed"})
        self._db.execute(
            "UPDATE satsa_assessments SET status='closed', content_digest=?"
            " WHERE organization_id=? AND id=?",
            (digest_document(assessment.to_dict()), self.organization_id, assessment_id),
        )

    def create_submission(self, assessment_id: str) -> str:
        self._require(ANALYSIS_RUN)
        assessment = self._db.query_one(
            "SELECT entity_id FROM satsa_assessments WHERE organization_id=? AND id=?",
            (self.organization_id, assessment_id),
        )
        if assessment is None:
            raise PermissionDeniedError("assessment does not belong to organization")
        submission_id = _id("submission")
        self._db.execute(
            "INSERT INTO satsa_submissions (id, organization_id, assessment_id, entity_id,"
            " ingest_status, created_at) VALUES (?,?,?,?,?,?)",
            (submission_id, self.organization_id, assessment_id,
             assessment["entity_id"], "created", time.time()),
        )
        return submission_id

    def get_submission(self, submission_id: str) -> dict | None:
        self._require(FINDING_VIEW)
        return self._db.query_one(
            "SELECT * FROM satsa_submissions WHERE organization_id=? AND id=?",
            (self.organization_id, submission_id),
        )

    def create_submission_version(self, submission_id: str, version: int) -> str:
        self._require(ANALYSIS_RUN)
        if self._db.query_one(
            "SELECT id FROM satsa_submissions WHERE organization_id=? AND id=?",
            (self.organization_id, submission_id),
        ) is None:
            raise PermissionDeniedError("submission does not belong to organization")
        if version < 1:
            raise DomainValidationError("version must be positive")
        version_id = _id("version")
        self._db.execute(
            "INSERT INTO satsa_submission_versions"
            " (id, organization_id, submission_id, version, created_at) VALUES (?,?,?,?,?)",
            (version_id, self.organization_id, submission_id, version, time.time()),
        )
        return version_id

    def get_submission_version(self, version_id: str) -> dict | None:
        self._require(FINDING_VIEW)
        return self._db.query_one(
            "SELECT * FROM satsa_submission_versions WHERE organization_id=? AND id=?",
            (self.organization_id, version_id),
        )

    def create_artifact(self, version_id: str, storage_key: str, content_type: str,
                        size_bytes: int, sha3_256_digest: str) -> str:
        self._require(ANALYSIS_RUN)
        if self._db.query_one(
            "SELECT id FROM satsa_submission_versions WHERE organization_id=? AND id=?",
            (self.organization_id, version_id),
        ) is None:
            raise PermissionDeniedError("version does not belong to organization")
        if (not storage_key or not content_type or size_bytes < 0
                or len(sha3_256_digest) != 64
                or any(c not in "0123456789abcdef" for c in sha3_256_digest)):
            raise DomainValidationError("invalid artifact metadata")
        artifact_id = _id("artifact")
        self._db.execute(
            "INSERT INTO satsa_artifacts (id, organization_id, submission_version_id,"
            " storage_key, content_type, size_bytes, sha3_256_digest, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (artifact_id, self.organization_id, version_id, storage_key,
             content_type, size_bytes, sha3_256_digest, time.time()),
        )
        return artifact_id

    def get_artifact(self, artifact_id: str) -> dict | None:
        self._require(EVIDENCE_VIEW)
        return self._db.query_one(
            "SELECT * FROM satsa_artifacts WHERE organization_id=? AND id=?",
            (self.organization_id, artifact_id),
        )

    def get_run(self, run_id: str) -> dict | None:
        self._require(FINDING_VIEW)
        return self._db.query_one(
            "SELECT * FROM satsa_runs WHERE organization_id=? AND id=?",
            (self.organization_id, run_id),
        )

    def get_finding(self, finding_id: str) -> dict | None:
        self._require(FINDING_VIEW)
        return self._db.query_one(
            "SELECT f.* FROM satsa_findings f"
            " JOIN satsa_observations o ON o.id=f.observation_id"
            " JOIN satsa_runs r ON r.id=o.run_id"
            " WHERE r.organization_id=? AND f.id=?",
            (self.organization_id, finding_id),
        )

    def get_source_record(self, source_record_id: str) -> dict | None:
        self._require(EVIDENCE_VIEW)
        return self._db.query_one(
            "SELECT e.* FROM satsa_source_records e"
            " JOIN satsa_submissions s ON s.id=e.submission_id"
            " WHERE s.organization_id=? AND e.id=?",
            (self.organization_id, source_record_id),
        )

    def get_review(self, review_id: str) -> dict | None:
        self._require(REVIEW_READ)
        return self._db.query_one(
            "SELECT d.* FROM satsa_review_decisions d"
            " JOIN satsa_findings f ON f.id=d.finding_id"
            " JOIN satsa_observations o ON o.id=f.observation_id"
            " JOIN satsa_runs r ON r.id=o.run_id"
            " WHERE r.organization_id=? AND d.id=?",
            (self.organization_id, review_id),
        )

    def get_trust_receipt(self, receipt_id: int) -> dict | None:
        self._require(TRUST_VERIFY)
        return self._db.query_one(
            "SELECT t.* FROM satsa_trust_receipts t"
            " LEFT JOIN satsa_runs r ON t.subject_type='run' AND r.id=t.subject_id"
            " LEFT JOIN satsa_findings f ON t.subject_type='finding' AND f.id=t.subject_id"
            " LEFT JOIN satsa_observations o ON o.id=f.observation_id"
            " LEFT JOIN satsa_runs fr ON fr.id=o.run_id"
            " WHERE t.id=? AND (r.organization_id=? OR fr.organization_id=?)",
            (receipt_id, self.organization_id, self.organization_id),
        )


class SessionRepository:
    """Opaque random browser-session tokens stored as SHA3-256 digests."""

    def __init__(self, engine) -> None:
        self._db = engine

    def create(self, user_id: str, *, ttl_seconds: float, now: float | None = None) -> str:
        if ttl_seconds <= 0:
            raise DomainValidationError("session lifetime must be positive")
        at = time.time() if now is None else now
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha3_256(token.encode()).hexdigest()
        self._db.execute(
            "INSERT INTO satsa_sessions (id, user_id, token_digest, created_at,"
            " expires_at, last_activity_at) VALUES (?,?,?,?,?,?)",
            (_id("session"), user_id, digest, at, at + ttl_seconds, at),
        )
        return token

    def resolve(self, token: str, *, now: float | None = None) -> dict | None:
        if not token:
            return None
        at = time.time() if now is None else now
        digest = hashlib.sha3_256(token.encode()).hexdigest()
        return self._db.query_one(
            "SELECT s.id, s.user_id, s.created_at, s.expires_at, s.last_activity_at"
            " FROM satsa_sessions s JOIN satsa_users u ON u.id=s.user_id"
            " JOIN identities i ON i.identity_id=u.identity_id"
            " WHERE s.token_digest=? AND s.expires_at>? AND s.revoked_at IS NULL"
            " AND u.status='active' AND i.status='active'",
            (digest, at),
        )

    def revoke(self, token: str, *, now: float | None = None) -> bool:
        session = self.resolve(token, now=now)
        if session is None:
            return False
        at = time.time() if now is None else now
        self._db.execute(
            "UPDATE satsa_sessions SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
            (at, session["id"]),
        )
        return True

    def touch(self, token: str, *, now: float | None = None) -> bool:
        """Record activity only for an unexpired, active session."""
        at = time.time() if now is None else now
        session = self.resolve(token, now=at)
        if session is None:
            return False
        self._db.execute(
            "UPDATE satsa_sessions SET last_activity_at=? WHERE id=?"
            " AND revoked_at IS NULL AND expires_at>?",
            (at, session["id"], at),
        )
        return True
