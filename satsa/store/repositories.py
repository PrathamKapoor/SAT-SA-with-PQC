"""Typed row access for the SAT-SA canonical store (tables added by
migrations 5-6 in qsmlops.database.migrations).

Follows the exact construction/error-handling pattern of
qsmlops.database.repositories (plain classes over the shared engine,
DuplicateEntryError propagation, dict rows) — no new abstraction layer.
Each row carries a content_digest (SHA3-256 of the domain record's
canonical to_dict(), via qsmlops.crypto.hashing.digest_document), matching
the convention Phase 2 established for the qsmlops evidence tables.
"""
from __future__ import annotations

import json

from qsmlops.crypto.hashing import digest_document
from satsa.domain.entities import Assessment, Asset, Entity, Submission
from satsa.domain.evidence import SourceRecord
from satsa.domain.workflow import (
    Alert,
    Case,
    Disposition,
    Escalation,
    InvestigationStep,
)


def _d(obj) -> str:
    return digest_document(obj.to_dict())


def _j(value) -> str:
    return json.dumps(value if value is not None else [], sort_keys=True, default=str)


def _jd(value) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True, default=str)


class EntityStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, e: Entity, *, created_at: float) -> None:
        self._db.execute(
            "INSERT INTO satsa_entities (id, display_name, sector, environment_class,"
            " cohort_attributes_json, access_scope, schema_version, content_digest, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (e.id, e.display_name, e.sector, e.environment_class, _jd(e.cohort_attributes),
             e.access_scope, e.schema_version, _d(e), created_at),
        )

    def get(self, entity_id: str) -> dict | None:
        row = self._db.query_one("SELECT * FROM satsa_entities WHERE id=?", (entity_id,))
        return dict(row) if row else None

    def get_by_name(self, display_name: str) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM satsa_entities WHERE display_name=?", (display_name,))
        return dict(row) if row else None

    def list(self) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_entities ORDER BY display_name")]


class AssessmentStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, a: Assessment, *, created_at: float) -> None:
        self._db.execute(
            "INSERT INTO satsa_assessments (id, entity_id, period_start, period_end,"
            " timezone, submission_cutoff, policy_version, status, supersedes_id,"
            " schema_version, content_digest, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (a.id, a.entity_id, a.period_start, a.period_end, a.timezone,
             a.submission_cutoff, a.policy_version, a.status, a.supersedes_id,
             a.schema_version, _d(a), created_at),
        )

    def get(self, assessment_id: str) -> dict | None:
        row = self._db.query_one("SELECT * FROM satsa_assessments WHERE id=?", (assessment_id,))
        return dict(row) if row else None

    def set_status(self, assessment_id: str, status: str) -> None:
        self._db.execute(
            "UPDATE satsa_assessments SET status=? WHERE id=?", (status, assessment_id))

    def list_for_entity(self, entity_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_assessments WHERE entity_id=? ORDER BY period_start",
            (entity_id,))]


class SubmissionStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, s: Submission, *, entity_id: str, ingest_status: str,
               ingest_report: dict, snapshot_digest: str, created_at: float) -> None:
        self._db.execute(
            "INSERT INTO satsa_submissions (id, assessment_id, entity_id, source_system,"
            " declared_period_start, declared_period_end, file_digests_json,"
            " declared_counts_json, schema_name, received_at, signature_status,"
            " ingest_status, ingest_report_json, snapshot_digest, schema_version,"
            " content_digest, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (s.id, s.assessment_id, entity_id,
             s.source_system, s.declared_period_start, s.declared_period_end,
             _jd(s.file_digests), _jd(s.declared_counts), s.schema_name, s.received_at,
             s.signature_status, ingest_status, _jd(ingest_report), snapshot_digest,
             s.schema_version, _d(s), created_at),
        )

    def update_outcome(self, submission_id: str, *, ingest_status: str,
                       ingest_report: dict, snapshot_digest: str) -> None:
        self._db.execute(
            "UPDATE satsa_submissions SET ingest_status=?, ingest_report_json=?,"
            " snapshot_digest=? WHERE id=?",
            (ingest_status, _jd(ingest_report), snapshot_digest, submission_id),
        )

    def get(self, submission_id: str) -> dict | None:
        row = self._db.query_one("SELECT * FROM satsa_submissions WHERE id=?", (submission_id,))
        return dict(row) if row else None

    def list_for_assessment(self, assessment_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_submissions WHERE assessment_id=? ORDER BY created_at",
            (assessment_id,))]

    def has_identical(self, assessment_id: str, file_digests: dict) -> bool:
        """True when an identical file-digest set was already ingested for this
        assessment (duplicate-submission guard — re-ingesting the same bytes is
        not a new submission)."""
        target = _jd(file_digests)
        rows = self._db.query_all(
            "SELECT id FROM satsa_submissions WHERE assessment_id=? AND file_digests_json=?",
            (assessment_id, target),
        )
        return bool(rows)


class SourceRecordStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, sr: SourceRecord) -> None:
        self._db.execute(
            "INSERT INTO satsa_source_records (id, submission_id, file_digest, format,"
            " locator, original_record_digest, content_digest) VALUES (?,?,?,?,?,?,?)",
            (sr.id, sr.submission_id, sr.file_digest, sr.format, sr.locator,
             sr.original_record_digest, _d(sr)),
        )

    def get(self, source_record_id: str) -> dict | None:
        row = self._db.query_one(
            "SELECT * FROM satsa_source_records WHERE id=?", (source_record_id,))
        return dict(row) if row else None


class AlertStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, a: Alert, *, submission_id: str) -> None:
        self._db.execute(
            "INSERT INTO satsa_alerts (id, entity_id, assessment_id, submission_id,"
            " native_id, created_at, native_severity, mapped_severity, native_category,"
            " mapped_category, asset_refs_json, case_refs_json, detector_refs_json,"
            " acknowledged_at, closed_at, disposition_id, source_record_ref,"
            " schema_version, content_digest)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a.id, a.entity_id, a.assessment_id, submission_id, a.native_id, a.created_at,
             a.native_severity, a.mapped_severity, a.native_category, a.mapped_category,
             _j(a.asset_refs), _j(a.case_refs), _j(a.detector_refs),
             a.acknowledged_at, a.closed_at, a.disposition_id, a.source_record_ref,
             a.schema_version, _d(a)),
        )

    def list_for_scope(self, entity_id: str, assessment_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_alerts WHERE entity_id=? AND assessment_id=?"
            " ORDER BY created_at", (entity_id, assessment_id))]


class CaseStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, c: Case, *, submission_id: str) -> None:
        self._db.execute(
            "INSERT INTO satsa_cases (id, entity_id, assessment_id, submission_id,"
            " native_id, opened_at, alert_refs_json, owner_pseudonym, status, closed_at,"
            " closure_reason, investigation_refs_json, remediation_refs_json,"
            " source_record_ref, schema_version, content_digest)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (c.id, c.entity_id, c.assessment_id, submission_id, c.native_id, c.opened_at,
             _j(c.alert_refs), c.owner_pseudonym, c.status, c.closed_at, c.closure_reason,
             _j(c.investigation_refs), _j(c.remediation_refs), c.source_record_ref,
             c.schema_version, _d(c)),
        )

    def list_for_scope(self, entity_id: str, assessment_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_cases WHERE entity_id=? AND assessment_id=?"
            " ORDER BY opened_at", (entity_id, assessment_id))]


class InvestigationStepStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, s: InvestigationStep, *, submission_id: str) -> None:
        self._db.execute(
            "INSERT INTO satsa_investigation_steps (id, case_id, submission_id,"
            " action_type, performed_at, sequence, analyst_pseudonym, evidence_refs_json,"
            " result_refs_json, note_text, content_digest) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (s.id, s.case_id, submission_id, s.action_type, s.performed_at, s.sequence,
             s.analyst_pseudonym, _j(s.evidence_refs), _j(s.result_refs), s.note_text,
             _d(s)),
        )

    def list_for_submission(self, submission_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_investigation_steps WHERE submission_id=?"
            " ORDER BY case_id, sequence", (submission_id,))]


class EscalationStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, e: Escalation, *, submission_id: str) -> None:
        self._db.execute(
            "INSERT INTO satsa_escalations (id, entity_id, assessment_id, submission_id,"
            " occurred_at, alert_id, case_id, destination_role, trigger, outcome,"
            " policy_exception_ref, content_digest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (e.id, e.entity_id, e.assessment_id, submission_id, e.occurred_at,
             e.alert_id, e.case_id, e.destination_role, e.trigger, e.outcome,
             e.policy_exception_ref, _d(e)),
        )

    def list_for_scope(self, entity_id: str, assessment_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_escalations WHERE entity_id=? AND assessment_id=?"
            " ORDER BY occurred_at", (entity_id, assessment_id))]


class DispositionStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, d: Disposition, *, submission_id: str) -> None:
        self._db.execute(
            "INSERT INTO satsa_dispositions (id, entity_id, assessment_id, submission_id,"
            " occurred_at, alert_id, case_id, mapped_category, reason, approver_role,"
            " exception_ref, supporting_refs_json, content_digest)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.id, d.entity_id, d.assessment_id, submission_id, d.occurred_at,
             d.alert_id, d.case_id, d.mapped_category, d.reason, d.approver_role,
             d.exception_ref, _j(d.supporting_refs), _d(d)),
        )

    def list_for_scope(self, entity_id: str, assessment_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_dispositions WHERE entity_id=? AND assessment_id=?"
            " ORDER BY occurred_at", (entity_id, assessment_id))]


class AssetStore:
    def __init__(self, engine) -> None:
        self._db = engine

    def insert(self, a: Asset, *, assessment_id: str, submission_id: str) -> None:
        self._db.execute(
            "INSERT INTO satsa_assets (id, entity_id, assessment_id, submission_id,"
            " native_id, criticality, environment, active_intervals_json,"
            " control_applicability_json, content_digest) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (a.id, a.entity_id, assessment_id, submission_id, a.native_id, a.criticality,
             a.environment, _j(a.active_intervals), _j(a.control_applicability), _d(a)),
        )

    def list_for_scope(self, entity_id: str, assessment_id: str) -> list[dict]:
        return [dict(r) for r in self._db.query_all(
            "SELECT * FROM satsa_assets WHERE entity_id=? AND assessment_id=?",
            (entity_id, assessment_id))]
