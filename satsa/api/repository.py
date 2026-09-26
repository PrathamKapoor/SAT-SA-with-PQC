"""Bounded API read models with mandatory tenant context below routes."""

from qsmlops.core.errors import PermissionDeniedError
from satsa.errors import DomainValidationError


class ApiRepository:
    def __init__(self, tenant):
        self.tenant = tenant
        self.db = tenant._db
        self.org = tenant.organization_id

    def collection(
        self, kind, *, limit=50, offset=0, entity_id=None, status=None, parent=None
    ):
        self.tenant._require("finding.view")
        if not 1 <= limit <= 200 or offset < 0:
            raise DomainValidationError("invalid pagination")
        projections = {
            "entities": (
                "satsa_entities",
                "id,organization_id,display_name,sector,environment_class,created_at",
            ),
            "assessments": (
                "satsa_assessments",
                "id,organization_id,entity_id,period_start,period_end,timezone,policy_version,status,created_at",
            ),
            "submissions": (
                "satsa_submissions",
                "id,organization_id,entity_id,assessment_id,ingest_status,created_at",
            ),
            "versions": (
                "satsa_submission_versions",
                "id,organization_id,submission_id,version,status,snapshot_digest,created_at",
            ),
            "artifacts": (
                "satsa_artifacts",
                "id,organization_id,submission_version_id,category,original_filename,content_type,size_bytes,sha3_256_digest,created_at",
            ),
            "runs": (
                "satsa_runs",
                "id,organization_id,entity_id,assessment_id,status,created_at,requested_at,started_at,finished_at,correlation_id,progress_total,progress_completed,retry_count,error,error_code",
            ),
        }
        table, columns = projections[kind]
        sql = f"SELECT {columns} FROM {table} WHERE organization_id=?"
        params = [self.org]
        if entity_id and kind in {"assessments", "submissions", "runs"}:
            if self.tenant.get_entity(entity_id) is None:
                raise PermissionDeniedError("entity is not accessible")
            sql += " AND entity_id=?"
            params.append(entity_id)
        if status:
            if kind != "runs":
                raise DomainValidationError("status filter is unsupported")
            sql += " AND status=?"
            params.append(status)
        if kind == "versions":
            self.require(self.tenant.get_submission(parent))
            sql += " AND submission_id=?"
            params.append(parent)
        if kind == "artifacts":
            self.tenant._require("evidence.view")
            self.require(self.tenant.get_submission_version(parent))
            sql += " AND submission_version_id=?"
            params.append(parent)
        rows = self.db.query_all(
            sql + " ORDER BY created_at,id LIMIT ? OFFSET ?",
            (*params, limit + 1, offset),
        )
        return {
            "items": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    @staticmethod
    def require(row):
        if row is None:
            from qsmlops.core.errors import NotFoundError

            raise NotFoundError("resource not found")
        return row

    def organizations(self, limit, offset):
        rows = self.db.query_all(
            "SELECT o.id,o.name,o.status,m.role FROM satsa_organizations o JOIN satsa_memberships m ON m.organization_id=o.id"
            " JOIN satsa_users u ON u.id=m.user_id JOIN identities i ON i.identity_id=u.identity_id"
            " WHERE m.user_id=? AND m.status='active' AND o.status='active' AND u.status='active' AND i.status='active'"
            " ORDER BY o.created_at,o.id LIMIT ? OFFSET ?",
            (self.tenant.user_id, limit + 1, offset),
        )
        return {
            "items": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    def members(self, limit, offset):
        self.tenant._require("identity.read")
        rows = self.db.query_all(
            "SELECT u.id,u.identity_id,i.name,u.email,m.role,u.status FROM satsa_users u"
            " JOIN satsa_memberships m ON m.user_id=u.id AND m.organization_id=?"
            " JOIN identities i ON i.identity_id=u.identity_id"
            " ORDER BY i.name,u.id LIMIT ? OFFSET ?",
            (self.org, limit + 1, offset),
        )
        return {
            "items": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    def set_member_status(self, user_id, status):
        self.tenant._require("identity.manage")
        with self.db.transaction():
            row = self.db.query_one(
                "SELECT user_id FROM satsa_memberships WHERE organization_id=? AND user_id=?",
                (self.org, user_id),
            )
            self.require(row)
            self.db.execute(
                "UPDATE satsa_memberships SET status=? WHERE organization_id=? AND user_id=?",
                (status, self.org, user_id),
            )

    def audit_events(self, limit, offset, *, run_id=None):
        self.tenant._require("audit.read")
        if run_id and self.tenant.get_run(run_id) is None:
            raise PermissionDeniedError("run is not accessible")
        expression = (
            "metadata::jsonb->>'organization_id'"
            if self.db.dialect == "postgresql"
            else "json_extract(metadata,'$.organization_id')"
        )
        sql = (
            f"SELECT a.event_id,a.timestamp,a.actor,a.action,a.resource,a.result FROM audit_events a WHERE "
            f"{expression}= ? OR (a.action IN ('session.login','session.logout') AND EXISTS "
            "(SELECT 1 FROM satsa_users u JOIN satsa_memberships m ON m.user_id=u.id "
            "WHERE u.identity_id=a.actor AND m.organization_id=? AND m.status='active'))"
        )
        params = [self.org, self.org]
        if run_id:
            sql += " AND resource=?"
            params.append(f"analysis_run:{run_id}")
        rows = self.db.query_all(
            sql + " ORDER BY timestamp DESC,event_id DESC LIMIT ? OFFSET ?",
            (*params, limit + 1, offset),
        )
        return {
            "items": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }

    def evidence(self, run_id, limit, offset):
        self.tenant._require("evidence.view")
        self.require(self.tenant.get_run(run_id))
        # Input provenance is useful even where a finding represents missing
        # evidence. This endpoint is the run's source corpus, not a claim that
        # every record supports every finding; findings carry exact references.
        rows = self.db.query_all(
            "SELECT sr.id AS source_record_id,sr.artifact_id,sr.locator,sr.format,sr.file_digest,sr.original_record_digest,"
            "v.record_id,v.category,v.content_digest AS canonical_record_digest"
            " FROM satsa_run_context c JOIN satsa_version_records v ON v.version_id=c.submission_version_id AND v.organization_id=c.organization_id"
            " JOIN satsa_source_records sr ON sr.id=v.source_record_id AND sr.submission_id=c.submission_id"
            " JOIN satsa_artifacts a ON a.id=sr.artifact_id AND a.organization_id=c.organization_id"
            " WHERE c.organization_id=? AND c.run_id=? ORDER BY sr.id LIMIT ? OFFSET ?",
            (self.org, run_id, limit + 1, offset),
        )
        return {
            "items": rows[:limit],
            "limit": limit,
            "offset": offset,
            "has_more": len(rows) > limit,
        }
