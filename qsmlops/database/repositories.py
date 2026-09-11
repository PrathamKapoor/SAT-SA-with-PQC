"""Repository pattern over the platform database.

Repositories encapsulate all SQL; services never touch the engine directly
for entity operations. Documents are stored canonically JSON-serialized in
TEXT columns (the tables are mirrors/indexes — the ledger is the evidence
source of truth).
"""
from __future__ import annotations

import json
import time
from typing import Any

from qsmlops.core.errors import DuplicateEntryError, IdentityError, NotFoundError
from qsmlops.database.engine import DatabaseEngine
from qsmlops.security.audit.events import AuditEvent
from qsmlops.security.identity.models import Identity


class BaseRepository:
    """Accepts either a raw DatabaseEngine or a DatabaseService."""

    def __init__(self, db) -> None:
        if hasattr(db, "ensure_ready"):
            db.ensure_ready()
            db = db.engine
        self._db: DatabaseEngine = db
        self._db.connect()


class AuditEventRepository(BaseRepository):
    def insert_mirror(self, event: AuditEvent, entry_hash: str) -> None:
        try:
            self._db.execute(
                """
                INSERT INTO audit_events
                    (event_id, timestamp, actor, action, resource, result,
                     evidence_reference, metadata, ledger_entry_hash)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    event.event_id,
                    event.timestamp,
                    event.actor,
                    event.action,
                    event.resource,
                    event.result,
                    event.evidence_reference,
                    json.dumps(event.metadata, sort_keys=True),
                    entry_hash,
                ),
            )
        except DuplicateEntryError:
            pass  # already mirrored (idempotent rebuilds)

    def fetch(self, event_id: str) -> AuditEvent | None:
        row = self._db.query_one(
            "SELECT * FROM audit_events WHERE event_id=?", (event_id,)
        )
        if row is None:
            return None
        event = AuditEvent(
            event_id=row["event_id"],
            timestamp=row["timestamp"],
            actor=row["actor"],
            action=row["action"],
            resource=row["resource"],
            result=row["result"],
            evidence_reference=row["evidence_reference"],
            metadata=json.loads(row["metadata"]),
        )
        return event

    def query(
        self,
        *,
        actor: str | None = None,
        action: str | None = None,
        resource: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        sql = "SELECT * FROM audit_events WHERE 1=1"
        params: list[Any] = []
        if actor:
            sql += " AND actor=?"
            params.append(actor)
        if action:
            sql += " AND action=?"
            params.append(action)
        if resource:
            sql += " AND resource=?"
            params.append(resource)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._db.query_all(sql, params)
        return [
            AuditEvent(
                event_id=row["event_id"],
                timestamp=row["timestamp"],
                actor=row["actor"],
                action=row["action"],
                resource=row["resource"],
                result=row["result"],
                evidence_reference=row["evidence_reference"],
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]


class IdentityRepository(BaseRepository):
    """Persistence of identity records (queryable mirror of the TrustedObject)."""

    def insert(self, identity: Identity) -> None:
        try:
            self._db.execute(
                """
                INSERT INTO identities
                    (identity_id, kind, name, owner, role, status, description,
                     version, permissions, created_at, updated_at, hash,
                     signature, verification_status, metadata)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    identity.id,
                    identity.kind,
                    identity.name,
                    identity.owner,
                    identity.role,
                    identity.status,
                    identity.description,
                    identity.version,
                    json.dumps(sorted(identity.permissions)),
                    identity.created_at,
                    identity.updated_at,
                    identity.hash,
                    json.dumps(identity.signature, sort_keys=True),
                    identity.verification_status,
                    json.dumps(identity.metadata, sort_keys=True),
                ),
            )
        except DuplicateEntryError as exc:
            raise IdentityError(
                f"identity {identity.kind}:{identity.name} already exists"
            ) from exc

    def update(self, identity: Identity) -> None:
        self._db.execute(
            """
            UPDATE identities SET
                status=?, version=?, permissions=?, updated_at=?, hash=?,
                signature=?, verification_status=?, metadata=?, description=?
            WHERE identity_id=?
            """,
            (
                identity.status,
                identity.version,
                json.dumps(sorted(identity.permissions)),
                identity.updated_at,
                identity.hash,
                json.dumps(identity.signature, sort_keys=True),
                identity.verification_status,
                json.dumps(identity.metadata, sort_keys=True),
                identity.description,
                identity.id,
            ),
        )

    def get(self, identity_id: str) -> Identity | None:
        row = self._db.query_one(
            "SELECT * FROM identities WHERE identity_id=?", (identity_id,)
        )
        return self._row_to_identity(row) if row else None

    def find_by_name(self, kind: str, name: str) -> Identity | None:
        row = self._db.query_one(
            "SELECT * FROM identities WHERE kind=? AND name=?", (kind, name)
        )
        return self._row_to_identity(row) if row else None

    def list(self, kind: str | None = None, status: str | None = None) -> list[Identity]:
        sql = "SELECT * FROM identities WHERE 1=1"
        params: list[Any] = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY kind, name"
        return [self._row_to_identity(r) for r in self._db.query_all(sql, params)]

    def delete(self, identity_id: str) -> None:
        if self.get(identity_id) is None:
            raise NotFoundError(f"identity {identity_id} not found")
        self._db.execute("DELETE FROM identities WHERE identity_id=?", (identity_id,))

    @staticmethod
    def _row_to_identity(row: dict) -> Identity:
        return Identity.from_dict(
            {
                "object_type": "identity",
                "id": row["identity_id"],
                "kind": row["kind"],
                "name": row["name"],
                "owner": row["owner"],
                "role": row["role"],
                "status": row["status"],
                "description": row["description"],
                "version": row["version"],
                "permissions": json.loads(row["permissions"] or "[]"),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "hash": row["hash"],
                "signature": json.loads(row["signature"] or "null"),
                "verification_status": row["verification_status"],
                "metadata": json.loads(row["metadata"] or "{}"),
            }
        )


class IdentityCredentialRepository(BaseRepository):
    """Persistence for local API-key credentials (Phase 2 identity auth).

    Only ``key_hash``/``salt`` are stored — never the raw credential secret.
    ``key_id`` is a non-secret lookup prefix that lets authentication find the
    right row without a full-table scan or a secret-dependent index.
    """

    def set_credential(
        self, identity_id: str, key_id: str, key_hash: str, salt: str, created_at: float
    ) -> None:
        try:
            self._db.execute(
                """
                INSERT INTO identity_credentials
                    (identity_id, key_id, key_hash, salt, created_at, revoked_at)
                VALUES (?,?,?,?,?,NULL)
                ON CONFLICT(identity_id) DO UPDATE SET
                    key_id=excluded.key_id, key_hash=excluded.key_hash,
                    salt=excluded.salt, created_at=excluded.created_at,
                    revoked_at=NULL
                """,
                (identity_id, key_id, key_hash, salt, created_at),
            )
        except DuplicateEntryError as exc:
            raise IdentityError(f"credential key_id {key_id} already issued") from exc

    def get_by_key_id(self, key_id: str) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM identity_credentials WHERE key_id=?", (key_id,)
        )
        return dict(row) if row else None

    def revoke(self, identity_id: str, *, revoked_at: float) -> None:
        self._db.execute(
            "UPDATE identity_credentials SET revoked_at=? WHERE identity_id=?",
            (revoked_at, identity_id),
        )


# ==================== Phase 2: evidence/provenance persistence ====================
#
# Part E of docs/phase2 identified these tables (observations, findings,
# supervisor_decisions, provenance_edges) as schema-only: migrated, indexed,
# but with no repository/insert path anywhere in the codebase (verified by
# grep — the classes below are the first). See
# docs/phase2/evidence-persistence.md for what this closes and what it
# deliberately does not yet claim (signed/ledger-committed provenance is
# later-phase work; these are durable, digest-checkable rows, not that).


class ObservationRepository(BaseRepository):
    """Persistence for agent Observations (qsmlops.agents.base.Observation)."""

    def insert(self, observation, *, content_digest: str) -> None:
        self._db.execute(
            """
            INSERT INTO observations
                (observation_id, agent, subject_id, recommendation, notes,
                 max_severity, mean_confidence, created_at, content_digest)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                observation.observation_id,
                observation.agent,
                observation.subject_id,
                observation.recommendation,
                observation.notes,
                observation.max_severity,
                observation.mean_confidence,
                observation.created_at,
                content_digest,
            ),
        )

    def get(self, observation_id: str) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM observations WHERE observation_id=?", (observation_id,)
        )
        return dict(row) if row else None

    def list_for_subject(self, subject_id: str, limit: int = 100) -> list[dict]:
        rows = self._db.query_all(
            "SELECT * FROM observations WHERE subject_id=? ORDER BY created_at DESC LIMIT ?",
            (subject_id, limit),
        )
        return [dict(r) for r in rows]


class FindingRepository(BaseRepository):
    """Persistence for individual Findings within an Observation."""

    def insert(
        self,
        finding,
        *,
        observation_id: str,
        agent: str,
        subject_id: str,
        content_digest: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO findings
                (finding_id, observation_id, agent, subject_id, name, passed,
                 severity, risk, detail, observation_text, evidence_json,
                 confidence, recommendation, created_at, content_digest)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                finding.finding_id,
                observation_id,
                agent,
                subject_id,
                finding.name,
                1 if finding.passed else 0,
                finding.severity,
                finding.risk,
                finding.detail,
                finding.observation,
                json.dumps([e.to_dict() for e in finding.evidence], sort_keys=True),
                finding.confidence,
                finding.recommendation,
                time.time(),
                content_digest,
            ),
        )

    def get(self, finding_id: str) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM findings WHERE finding_id=?", (finding_id,)
        )
        return dict(row) if row else None

    def list_for_observation(self, observation_id: str) -> list[dict]:
        rows = self._db.query_all(
            "SELECT * FROM findings WHERE observation_id=? ORDER BY created_at",
            (observation_id,),
        )
        return [dict(r) for r in rows]

    def list_for_subject(self, subject_id: str, limit: int = 200) -> list[dict]:
        rows = self._db.query_all(
            "SELECT * FROM findings WHERE subject_id=? ORDER BY created_at DESC LIMIT ?",
            (subject_id, limit),
        )
        return [dict(r) for r in rows]


class SupervisorDecisionRepository(BaseRepository):
    """Persistence for supervisor DecisionReports
    (qsmlops.supervisor.decisions.DecisionReport)."""

    def insert(
        self,
        decision_id: str,
        report,
        *,
        model_name: str = "",
        packet_id: str = "",
        action_success: bool | None = None,
        verified: bool | None = None,
        detail: str = "",
        content_digest: str,
    ) -> None:
        self._db.execute(
            """
            INSERT INTO supervisor_decisions
                (decision_id, subject_id, model_name, decision, risk_score,
                 rationale, facts_json, policy_decisions_json,
                 category_scores_json, scores_json, packet_id, action_success,
                 verified, detail, created_at, content_digest)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                decision_id,
                report.subject_id,
                model_name,
                report.decision.value if hasattr(report.decision, "value") else str(report.decision),
                report.risk_score,
                report.rationale,
                json.dumps(report.facts, sort_keys=True, default=str),
                json.dumps(report.policy_decisions, sort_keys=True, default=str),
                json.dumps(report.category_scores, sort_keys=True),
                json.dumps(report.scores, sort_keys=True),
                packet_id,
                None if action_success is None else (1 if action_success else 0),
                None if verified is None else (1 if verified else 0),
                detail,
                time.time(),
                content_digest,
            ),
        )

    def get(self, decision_id: str) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM supervisor_decisions WHERE decision_id=?", (decision_id,)
        )
        return dict(row) if row else None

    def list_for_subject(self, subject_id: str, limit: int = 100) -> list[dict]:
        rows = self._db.query_all(
            "SELECT * FROM supervisor_decisions WHERE subject_id=? ORDER BY created_at DESC LIMIT ?",
            (subject_id, limit),
        )
        return [dict(r) for r in rows]


class ProvenanceEdgeRepository(BaseRepository):
    """Persistence for provenance edges: typed subject->predicate->object
    links (e.g. finding -> derived_from -> observation, decision ->
    based_on -> finding). Idempotent: asserting the same edge twice is a
    no-op, since the same lifecycle stage may legitimately be reprocessed."""

    def insert(
        self,
        subject_type: str,
        subject_id: str,
        predicate: str,
        object_type: str,
        object_id: str,
        *,
        metadata: dict | None = None,
        content_digest: str,
    ) -> None:
        try:
            self._db.execute(
                """
                INSERT INTO provenance_edges
                    (subject_type, subject_id, predicate, object_type, object_id,
                     metadata_json, created_at, content_digest)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    subject_type,
                    subject_id,
                    predicate,
                    object_type,
                    object_id,
                    json.dumps(metadata or {}, sort_keys=True, default=str),
                    time.time(),
                    content_digest,
                ),
            )
        except DuplicateEntryError:
            pass  # same edge already asserted — idempotent by design

    def list_for_subject(self, subject_type: str, subject_id: str) -> list[dict]:
        rows = self._db.query_all(
            "SELECT * FROM provenance_edges WHERE subject_type=? AND subject_id=? ORDER BY created_at",
            (subject_type, subject_id),
        )
        return [dict(r) for r in rows]

    def list_for_object(self, object_type: str, object_id: str) -> list[dict]:
        rows = self._db.query_all(
            "SELECT * FROM provenance_edges WHERE object_type=? AND object_id=? ORDER BY created_at",
            (object_type, object_id),
        )
        return [dict(r) for r in rows]
