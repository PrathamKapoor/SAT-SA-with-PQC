"""Tenant-bound, versioned submission workflow for the hosted ingestion path."""
from __future__ import annotations

import hashlib
import json
import tempfile
import time
from pathlib import Path

from qsmlops.core.errors import (
    DuplicateEntryError,
    IntegrityError,
    PermissionDeniedError,
)
from qsmlops.core.logging import get_logger
from qsmlops.crypto.hashing import digest_document
from qsmlops.security.audit.events import AuditEvent
from qsmlops.security.permissions.model import ANALYSIS_RUN, EVIDENCE_VIEW, FINDING_VIEW
from satsa.domain.base import new_id
from satsa.errors import DomainValidationError
from satsa.ingest.normalize import extract_fields, normalize_category
from satsa.ingest.readers import IngestionFormatError
from satsa.ingest.service import NORMALIZE_ORDER
from satsa.ingest.spec import ALERT_FIELDS, ASSET_FIELDS, CASE_FIELDS, CATEGORY_FIELDS
from satsa.submissions.readers import parse_streamed_file
from satsa.submissions.storage import CHUNK_BYTES, ArtifactStorage, file_sha3_256
from satsa.tenancy import TenantRepository, _id

ALLOWED_TYPES = {
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
    ".json": {"application/json"},
    ".jsonl": {"application/x-ndjson", "application/jsonl"},
    ".ndjson": {"application/x-ndjson", "application/jsonl"},
}
MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
VALIDATOR_VERSION = "satsa-submission-validation/1"
log = get_logger(__name__)


class SubmissionService:
    """Operations require member context and check ownership below the API."""

    def __init__(self, engine, organization_id: str, user_id: str, *, storage: ArtifactStorage,
                 audit, max_artifact_bytes: int = MAX_ARTIFACT_BYTES,
                 max_rows: int = 100_000) -> None:
        if not 0 < max_artifact_bytes <= MAX_ARTIFACT_BYTES or max_rows < 1:
            raise ValueError("invalid submission limits")
        self.db = engine
        self.tenant = TenantRepository(engine, organization_id, user_id)
        self.org = organization_id
        self.user = user_id
        self.storage = storage
        self.audit = audit
        self.max_artifact_bytes = max_artifact_bytes
        self.max_rows = max_rows

    def _audit(self, action: str, resource: str, **metadata) -> None:
        actor = self.db.query_one("SELECT identity_id FROM satsa_users WHERE id=?", (self.user,))
        self.audit.record(AuditEvent.create(
            actor=actor["identity_id"], action=action, resource=resource,
            metadata={"organization_id": self.org, **metadata},
        ))

    def _audit_artifact_uploaded(self, artifact: dict) -> None:
        actor = self.db.query_one(
            "SELECT identity_id FROM satsa_users WHERE id=?",
            (artifact["uploaded_by_user_id"],),
        )
        event_id = hashlib.sha3_256(
            f"{self.org}:submission.artifact_uploaded:{artifact['id']}".encode()
        ).hexdigest()[:32]
        self.audit.record_once(AuditEvent(
            event_id=event_id,
            timestamp=artifact["created_at"],
            actor=actor["identity_id"],
            action="submission.artifact_uploaded",
            resource=f"artifact:{artifact['id']}",
            result="SUCCESS",
            metadata={
                "organization_id": self.org,
                "version_id": artifact["submission_version_id"],
                "category": artifact["category"],
                "size_bytes": artifact["size_bytes"],
            },
        ))

    @staticmethod
    def _key(key: str) -> None:
        if not isinstance(key, str) or not 1 <= len(key) <= 128 or any(ord(c) < 33 for c in key):
            raise DomainValidationError("idempotency key must be 1-128 printable non-space characters")

    def _version(self, version_id: str, permission: str = ANALYSIS_RUN) -> dict:
        self.tenant._require(permission)
        row = self.db.query_one(
            "SELECT v.*, s.assessment_id, s.entity_id FROM satsa_submission_versions v"
            " JOIN satsa_submissions s ON s.id=v.submission_id"
            " WHERE v.organization_id=? AND s.organization_id=? AND v.id=?",
            (self.org, self.org, version_id),
        )
        if row is None:
            raise PermissionDeniedError("submission version does not belong to organization")
        return row

    def create_submission(self, assessment_id: str, *, idempotency_key: str) -> str:
        self.tenant._require(ANALYSIS_RUN)
        self._key(idempotency_key)
        assessment = self.tenant.get_assessment(assessment_id)
        if assessment is None:
            raise PermissionDeniedError("assessment does not belong to organization")
        if assessment["status"] != "open":
            raise DomainValidationError("assessment is closed")
        try:
            with self.db.transaction():
                existing = self.db.query_one(
                    "SELECT id FROM satsa_submissions WHERE organization_id=?"
                    " AND assessment_id=? AND create_idempotency_key=?",
                    (self.org, assessment_id, idempotency_key),
                )
                if existing:
                    return existing["id"]
                submission_id = _id("submission")
                self.db.execute(
                    "INSERT INTO satsa_submissions"
                    " (id, organization_id, assessment_id, entity_id, ingest_status,"
                    " created_at, created_by_user_id, create_idempotency_key)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (submission_id, self.org, assessment_id, assessment["entity_id"],
                     "created", time.time(), self.user, idempotency_key),
                )
        except DuplicateEntryError:
            existing = self.db.query_one(
                "SELECT id FROM satsa_submissions WHERE organization_id=?"
                " AND assessment_id=? AND create_idempotency_key=?",
                (self.org, assessment_id, idempotency_key),
            )
            if existing:
                return existing["id"]
            raise
        self._audit("submission.created", f"submission:{submission_id}")
        return submission_id

    def create_version(self, submission_id: str, *, idempotency_key: str) -> str:
        self.tenant._require(ANALYSIS_RUN)
        self._key(idempotency_key)
        if self.tenant.get_submission(submission_id) is None:
            raise PermissionDeniedError("submission does not belong to organization")
        for attempt in range(3):
            try:
                with self.db.transaction():
                    existing = self.db.query_one(
                        "SELECT id FROM satsa_submission_versions WHERE organization_id=?"
                        " AND submission_id=? AND idempotency_key=?",
                        (self.org, submission_id, idempotency_key),
                    )
                    if existing:
                        return existing["id"]
                    current = self.db.query_one(
                        "SELECT MAX(version) AS number FROM satsa_submission_versions"
                        " WHERE organization_id=? AND submission_id=?",
                        (self.org, submission_id),
                    )
                    version_id = _id("version")
                    self.db.execute(
                        "INSERT INTO satsa_submission_versions"
                        " (id, organization_id, submission_id, version, status, created_at,"
                        " created_by_user_id, idempotency_key) VALUES (?,?,?,?,?,?,?,?)",
                        (version_id, self.org, submission_id, (current["number"] or 0) + 1,
                         "created", time.time(), self.user, idempotency_key),
                    )
                break
            except DuplicateEntryError:
                if attempt == 2:
                    raise
        self._audit("submission.version_created", f"version:{version_id}")
        return version_id

    def upload(self, version_id: str, *, category: str, stream, filename: str,
               content_type: str, idempotency_key: str) -> dict:
        version = self._version(version_id)
        self._key(idempotency_key)
        if category not in CATEGORY_FIELDS:
            raise DomainValidationError("unsupported evidence category")
        if (not filename or "/" in filename or "\\" in filename or filename in {".", ".."}
                or any(ord(c) < 32 for c in filename) or len(filename) > 255):
            raise DomainValidationError("invalid upload filename")
        suffix = Path(filename).suffix.lower()
        if content_type.lower().split(";", 1)[0].strip() not in ALLOWED_TYPES.get(suffix, set()):
            raise DomainValidationError("filename extension and content type do not agree")
        digest = hashlib.sha3_256()
        size = 0
        with tempfile.TemporaryDirectory(prefix="satsa-upload-") as temporary:
            source = Path(temporary) / f"upload{suffix}"
            with source.open("wb") as destination:
                while chunk := stream.read(CHUNK_BYTES):
                    if not isinstance(chunk, bytes):
                        raise DomainValidationError("upload stream must contain bytes")
                    size += len(chunk)
                    if size > self.max_artifact_bytes:
                        raise DomainValidationError(
                            "upload exceeds artifact size limit"
                        )
                    digest.update(chunk)
                    destination.write(chunk)
            if size == 0:
                raise DomainValidationError("empty artifact")
            with source.open("rb") as content:
                first = content.read(4096).lstrip(b"\xef\xbb\xbf \t\r\n")
            if b"\x00" in first:
                raise DomainValidationError("binary content is not a supported dataset")
            if suffix == ".json" and not first.startswith((b"[", b"{")):
                raise DomainValidationError("JSON artifact does not contain JSON data")
            if suffix in {".jsonl", ".ndjson"} and not first.startswith(b"{"):
                raise DomainValidationError("JSONL artifact must begin with an object")
            artifact_digest = digest.hexdigest()
            existing = self.db.query_one(
                "SELECT * FROM satsa_artifacts WHERE organization_id=?"
                " AND submission_version_id=? AND upload_idempotency_key=?",
                (self.org, version_id, idempotency_key),
            )
            if existing:
                if (
                    existing["sha3_256_digest"] != artifact_digest
                    or existing["category"] != category
                    or existing["original_filename"] != filename
                    or existing["content_type"] != content_type
                ):
                    raise DomainValidationError(
                        "idempotency key reused for different artifact"
                    )
                if existing.get("storage_status", "stored") == "stored":
                    self._audit_artifact_uploaded(existing)
                    return existing
                artifact_id = existing["id"]
                storage_key = existing["storage_key"]
            else:
                artifact_id = None
                storage_key = None
            if version["status"] not in {"created", "uploading"}:
                raise DomainValidationError(
                    "version is immutable after upload completion"
                )
            if existing is None and self.db.query_one(
                "SELECT id FROM satsa_artifacts WHERE organization_id=?"
                " AND submission_version_id=? AND category=?",
                (self.org, version_id, category),
            ):
                # A concurrent request with this idempotency key may have
                # inserted the row after the lookup above: that is a replay.
                replay = self.db.query_one(
                    "SELECT * FROM satsa_artifacts WHERE organization_id=?"
                    " AND submission_version_id=? AND upload_idempotency_key=?",
                    (self.org, version_id, idempotency_key),
                )
                if not (
                    replay
                    and replay["sha3_256_digest"] == artifact_digest
                    and replay["category"] == category
                    and replay["original_filename"] == filename
                    and replay["content_type"] == content_type
                ):
                    raise DomainValidationError("category already uploaded in this version")
                if replay.get("storage_status", "stored") == "stored":
                    return replay
                artifact_id, storage_key = replay["id"], replay["storage_key"]
            # Keep local paths below Windows MAX_PATH even under deep test/user roots.
            # Ownership is stored and checked in SQL; this is only an opaque blob key.
            scope_key = hashlib.sha3_256(
                f"{self.org}\0{version_id}".encode()
            ).hexdigest()[:32]
            if not storage_key:
                storage_key = f"{scope_key}/{category}/{artifact_digest}{suffix}"
                artifact_id = _id("artifact")
                try:
                    with self.db.transaction():
                        # Persist intent before external storage. Retries can resume
                        # an interrupted write without changing artifact identity.
                        self.db.execute(
                            "UPDATE satsa_submission_versions SET status='uploading'"
                            " WHERE organization_id=? AND id=? AND status IN ('created','uploading')",
                            (self.org, version_id),
                        )
                        current = self.db.query_one(
                            "SELECT status FROM satsa_submission_versions"
                            " WHERE organization_id=? AND id=?",
                            (self.org, version_id),
                        )
                        if current is None or current["status"] != "uploading":
                            raise DomainValidationError(
                                "version is immutable after upload completion"
                            )
                        self.db.execute(
                            "INSERT INTO satsa_artifacts"
                            " (id, organization_id, submission_version_id, storage_key, content_type,"
                            " size_bytes, sha3_256_digest, created_at, category, original_filename,"
                            " upload_idempotency_key, format, uploaded_by_user_id, storage_status)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'uploading')",
                            (
                                artifact_id,
                                self.org,
                                version_id,
                                storage_key,
                                content_type,
                                size,
                                artifact_digest,
                                time.time(),
                                category,
                                filename,
                                idempotency_key,
                                suffix[1:],
                                self.user,
                            ),
                        )
                except DuplicateEntryError:
                    existing = self.db.query_one(
                        "SELECT * FROM satsa_artifacts WHERE organization_id=?"
                        " AND submission_version_id=? AND upload_idempotency_key=?",
                        (self.org, version_id, idempotency_key),
                    )
                    if (
                        existing
                        and existing["sha3_256_digest"] == artifact_digest
                        and existing["category"] == category
                        and existing["original_filename"] == filename
                        and existing["content_type"] == content_type
                    ):
                        if existing.get("storage_status", "stored") == "stored":
                            return existing
                        artifact_id, storage_key = (
                            existing["id"],
                            existing["storage_key"],
                        )
                    else:
                        raise DomainValidationError(
                            "artifact category or idempotency key already used"
                        )
            try:
                self.storage.put_file(
                    source, storage_key, content_type, artifact_digest
                )
                completed = self.db.query_one(
                    "UPDATE satsa_artifacts SET storage_status='stored'"
                    " WHERE organization_id=? AND id=? AND storage_status IN ('uploading','failed')"
                    " RETURNING id",
                    (self.org, artifact_id),
                )
            except Exception:
                self.db.execute(
                    "UPDATE satsa_artifacts SET storage_status='failed'"
                    " WHERE organization_id=? AND id=? AND storage_status='uploading'",
                    (self.org, artifact_id),
                )
                raise
            artifact = self.tenant.get_artifact(artifact_id)
            if artifact is None:
                raise RuntimeError("stored artifact metadata disappeared")
            if completed or existing is not None:
                self._audit_artifact_uploaded(artifact)
            return artifact

    def read_artifact(self, artifact_id: str) -> bytes:
        artifact = self.tenant.get_artifact(artifact_id)
        if artifact is None:
            raise PermissionDeniedError("artifact does not belong to organization")
        if artifact.get("storage_status", "stored") != "stored":
            raise DomainValidationError("artifact storage is not complete")
        if artifact["size_bytes"] > self.max_artifact_bytes:
            raise DomainValidationError("artifact too large for byte retrieval")
        with tempfile.TemporaryDirectory(prefix="satsa-read-") as temporary:
            destination = Path(temporary) / "artifact"
            self.storage.copy_to(artifact["storage_key"], destination)
            if file_sha3_256(destination) != artifact["sha3_256_digest"]:
                raise IngestionFormatError("stored artifact digest mismatch")
            return destination.read_bytes()

    def complete_uploads(self, version_id: str) -> None:
        version = self._version(version_id)
        if version["status"] in {"uploaded", "validating", "valid", "invalid", "failed"}:
            return
        if version["status"] != "uploading":
            raise DomainValidationError("version has no open uploads")
        artifacts = self._artifacts(version_id)
        if any(a.get("storage_status", "stored") != "stored" for a in artifacts):
            raise DomainValidationError("all artifacts must be stored before completion")
        if "alerts" not in {r["category"] for r in artifacts}:
            raise DomainValidationError("alerts artifact is required")
        self.db.execute("UPDATE satsa_submission_versions SET status='uploaded'"
                        " WHERE organization_id=? AND id=? AND status='uploading'",
                        (self.org, version_id))
        self._audit("submission.upload_completed", f"version:{version_id}")

    def _artifacts(self, version_id: str) -> list[dict]:
        return self.db.query_all(
            "SELECT * FROM satsa_artifacts WHERE organization_id=?"
            " AND submission_version_id=? ORDER BY category",
            (self.org, version_id),
        )

    def validate(self, version_id: str) -> dict:
        version = self._version(version_id)
        existing = self.get_validation_report(version_id)
        if existing:
            return existing
        if version["status"] != "uploaded":
            raise DomainValidationError("version must be uploaded before validation")
        artifacts = self._artifacts(version_id)
        if any(a.get("storage_status", "stored") != "stored" for a in artifacts):
            raise DomainValidationError("all artifacts must be stored before completion")
        # Claim the version atomically: one concurrent caller validates, the
        # others return the recorded report or a conflict.
        claimed = self.db.query_one(
            "UPDATE satsa_submission_versions SET status='validating'"
            " WHERE organization_id=? AND id=? AND status='uploaded' RETURNING id",
            (self.org, version_id))
        if claimed is None:
            existing = self.get_validation_report(version_id)
            if existing:
                return existing
            raise DomainValidationError("validation already in progress for this version")
        self._audit("submission.validation_started", f"version:{version_id}")
        try:
            return self._validate_claimed(version_id, version, artifacts)
        except BaseException:
            # An interrupted validation must not strand the version in
            # 'validating'; it returns to 'uploaded' and can be retried.
            self.db.execute(
                "UPDATE satsa_submission_versions SET status='uploaded'"
                " WHERE organization_id=? AND id=? AND status='validating'",
                (self.org, version_id))
            raise

    def _validate_claimed(self, version_id: str, version: dict, artifacts: list) -> dict:
        parsed, errors, failures, results = {}, [], [], {}
        with tempfile.TemporaryDirectory(prefix="satsa-validate-") as temporary:
            for artifact in artifacts:
                path = Path(temporary) / f"{artifact['id']}.{artifact['format']}"
                try:
                    self.storage.copy_to(artifact["storage_key"], path)
                    if file_sha3_256(path) != artifact["sha3_256_digest"]:
                        raise IntegrityError("stored artifact digest mismatch")
                    parsed[artifact["category"]] = parse_streamed_file(
                        path, artifact["category"], max_rows=self.max_rows)
                except IngestionFormatError as exc:
                    errors.append({"category": artifact["category"], "message": str(exc)})
                except Exception:
                    log.exception("submission artifact validation failed: version=%s category=%s",
                                  version_id, artifact["category"])
                    failures.append({"category": artifact["category"],
                                     "message": "artifact storage or integrity failure"})
        if not errors and not failures:
            for category, parsed_file in parsed.items():
                seen = set()
                for row in parsed_file.rows:
                    if row.original_digest in seen:
                        errors.append({"category": category, "locator": row.locator,
                                       "message": "duplicate record bytes within artifact"})
                    seen.add(row.original_digest)
        if not errors and not failures:
            try:
                results = self._normalize(parsed, version["entity_id"], version["assessment_id"])
            except (ValueError, TypeError, DomainValidationError) as exc:
                errors.append({"category": "normalization", "message": str(exc)})
        categories = {category: result.summary() for category, result in results.items()}
        for category, parsed_file in parsed.items():
            summary = categories.setdefault(category, {"present": True})
            summary["format"] = parsed_file.format
            summary["fields"] = sorted(parsed_file.rows[0].data) if parsed_file.rows else []
        for error in errors + failures:
            categories[error["category"]] = {"present": True, "error": error["message"]}
        rejected = (sum(len(result.rejected) for result in results.values())
                    + sum(1 for error in errors if error.get("locator")))
        accepted = sum(len(result.records) for result in results.values())
        for category, result in results.items():
            for row in result.rejected:
                errors.append({"category": category, "locator": row.locator,
                               "native_id": row.native_id, "reasons": row.reasons})
        if not accepted and not errors and not failures:
            # Otherwise an empty dataset is reported invalid with no reason.
            errors.append({"category": "submission", "message": "no records were accepted"})
        status = "failed" if failures else "invalid" if errors or not accepted else "valid"
        report = {
            "status": status, "validator_version": VALIDATOR_VERSION,
            "version_id": version_id, "categories": categories, "errors": errors + failures,
            "warnings": [w for result in results.values() for w in result.warnings],
            "totals": {"received": sum(len(p.rows) for p in parsed.values()),
                       "accepted": accepted, "rejected": rejected},
            "artifact_digests": {a["category"]: a["sha3_256_digest"] for a in artifacts},
            "created_at": time.time(),
        }
        snapshot_digest = digest_document({
            "organization_id": self.org, "version_id": version_id,
            "artifact_digests": report["artifact_digests"],
            "records": sorted(digest_document(r.to_dict()) for result in results.values()
                              for r in result.records),
        }) if status == "valid" else ""
        with self.db.transaction():
            if status == "valid":
                by_category = {a["category"]: a for a in artifacts}
                for category, result in results.items():
                    artifact = by_category[category]
                    for record, source in zip(result.records, result.source_records):
                        source.submission_id = version["submission_id"]
                        self.db.execute(
                            "INSERT INTO satsa_source_records"
                            " (id, submission_id, file_digest, format, locator,"
                            " original_record_digest, content_digest, version_id, artifact_id)"
                            " VALUES (?,?,?,?,?,?,?,?,?)",
                            (source.id, source.submission_id, source.file_digest, source.format,
                             source.locator, source.original_record_digest,
                             digest_document(source.to_dict()), version_id, artifact["id"]),
                        )
                        payload = record.to_dict()
                        self.db.execute(
                            "INSERT INTO satsa_version_records"
                            " (record_id, organization_id, version_id, category, source_record_id,"
                            " payload_json, content_digest, created_at) VALUES (?,?,?,?,?,?,?,?)",
                            (record.id, self.org, version_id, category, source.id,
                             json.dumps(payload, sort_keys=True), digest_document(payload),
                             time.time()),
                        )
            self.db.execute(
                "INSERT INTO satsa_validation_reports"
                " (id, organization_id, version_id, status, validator_version, report_json,"
                " content_digest, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (_id("validation"), self.org, version_id, status, VALIDATOR_VERSION,
                 json.dumps(report, sort_keys=True), digest_document(report), report["created_at"]),
            )
            self.db.execute(
                "UPDATE satsa_submission_versions SET status=?, validated_at=?,"
                " snapshot_digest=?, content_digest=? WHERE organization_id=? AND id=?",
                (status, report["created_at"], snapshot_digest, digest_document(report),
                 self.org, version_id),
            )
            self.db.execute(
                "UPDATE satsa_submissions SET ingest_status=? WHERE organization_id=? AND id=?",
                (status, self.org, version["submission_id"]),
            )
        self._audit("submission.validation_failed" if status == "failed"
                    else "submission.validation_completed", f"version:{version_id}",
                    status=status, accepted=accepted, rejected=rejected)
        if status in {"valid", "invalid"}:
            self._audit("submission.accepted" if status == "valid"
                        else "submission.invalidated", f"version:{version_id}")
        return report

    def _normalize(self, parsed: dict, entity_id: str, assessment_id: str) -> dict:
        maps: dict[str, dict[str, str]] = {
            category: {} for category in ("alerts", "cases", "assets")
        }
        specs = {"alerts": ALERT_FIELDS, "cases": CASE_FIELDS, "assets": ASSET_FIELDS}
        prefixes = {"alerts": "alert", "cases": "case", "assets": "asset"}
        for category, spec in specs.items():
            if category not in parsed:
                continue
            for row in parsed[category].rows:
                native = str(extract_fields(row, spec).get("native_id") or "").strip()
                if native and native not in maps[category]:
                    maps[category][native] = new_id(prefixes[category])
        results = {}
        for category in NORMALIZE_ORDER:
            if category not in parsed:
                continue
            result = normalize_category(
                parsed[category], entity_id=entity_id, assessment_id=assessment_id,
                case_native_to_id=maps["cases"], alert_native_to_id=maps["alerts"],
                asset_native_to_id=maps["assets"], preassigned=maps.get(category, {}),
            )
            results[category] = result
            if category in maps:
                accepted = set(result.accepted_native)
                for native in list(maps[category]):
                    if native not in accepted:
                        maps[category].pop(native)
        return results

    def get_validation_report(self, version_id: str) -> dict | None:
        self._version(version_id, FINDING_VIEW)
        row = self.db.query_one(
            "SELECT report_json FROM satsa_validation_reports"
            " WHERE organization_id=? AND version_id=?",
            (self.org, version_id),
        )
        return json.loads(row["report_json"]) if row else None

    def count_canonical_records(self, version_id: str) -> dict[str, int]:
        self._version(version_id, EVIDENCE_VIEW)
        rows = self.db.query_all(
            "SELECT category, COUNT(*) AS n FROM satsa_version_records"
            " WHERE organization_id=? AND version_id=? GROUP BY category",
            (self.org, version_id),
        )
        return {row["category"]: row["n"] for row in rows}

    def list_canonical_records(self, version_id: str, *, category: str | None = None,
                               limit: int = 100, offset: int = 0) -> list[dict]:
        """Return a bounded, tenant-scoped version snapshot with source pointers."""
        self._version(version_id, EVIDENCE_VIEW)
        if category is not None and category not in CATEGORY_FIELDS:
            raise DomainValidationError("unsupported evidence category")
        if not 1 <= limit <= 500 or offset < 0:
            raise DomainValidationError("invalid pagination")
        sql = (
            "SELECT r.record_id, r.category, r.payload_json, r.content_digest,"
            " r.source_record_id, s.artifact_id, s.locator, s.file_digest,"
            " s.original_record_digest FROM satsa_version_records r"
            " JOIN satsa_source_records s ON s.id=r.source_record_id"
            " JOIN satsa_artifacts a ON a.id=s.artifact_id"
            " WHERE r.organization_id=? AND r.version_id=? AND a.organization_id=?"
        )
        params: tuple = (self.org, version_id, self.org)
        if category is not None:
            sql += " AND r.category=?"
            params += (category,)
        sql += " ORDER BY r.category, r.record_id LIMIT ? OFFSET ?"
        rows = self.db.query_all(sql, params + (limit, offset))
        return [{**{key: value for key, value in row.items() if key != "payload_json"},
                 "payload": json.loads(row["payload_json"])} for row in rows]
