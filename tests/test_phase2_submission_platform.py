"""Versioned tenant submission flow on SQLite and PostgreSQL."""
from __future__ import annotations

import io
import time
from pathlib import Path

import pytest
from test_postgres_engine import postgres_dsn  # noqa: F401
from test_tenant_schema import engine  # noqa: F401

from qsmlops.core.errors import PermissionDeniedError
from qsmlops.crypto.hashing import sha3_hex
from qsmlops.evidence.ledger import EvidenceLedger
from qsmlops.security.audit.service import AuditService
from satsa.errors import DomainValidationError
from satsa.tenancy import TenantAdministration

ALERTS = b"native_id,created_at,severity\nA1,1735689700,critical\n"


def test_phase2_schema_preserves_versioned_snapshots(engine):  # noqa: F811
    assert engine.query_one("SELECT COUNT(*) AS n FROM satsa_validation_reports") == {"n": 0}
    assert engine.query_one("SELECT COUNT(*) AS n FROM satsa_version_records") == {"n": 0}
    assert engine.query_one(
        "SELECT created_by_user_id, create_idempotency_key FROM satsa_submissions LIMIT 1"
    ) is None


@pytest.fixture
def submission_scope(engine, tmp_path):  # noqa: F811
    from satsa.submissions import LocalArtifactStorage, SubmissionService

    admin = TenantAdministration(engine)
    org = admin.create_organization("CSE Phase 2")
    engine.execute(
        "INSERT INTO identities (identity_id, kind, name, owner, status, created_at, updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        ("analyst", "analyst", "analyst", time.time(), time.time()),
    )
    user = admin.create_user("analyst", "analyst@example.test")
    admin.add_membership(org, user, "satsa_analyst")
    storage = LocalArtifactStorage(tmp_path / "artifacts")
    audit = AuditService(EvidenceLedger(tmp_path / "audit.jsonl"), database=engine)
    service = SubmissionService(engine, org, user, storage=storage, audit=audit)
    entity = service.tenant.create_entity("Test entity")
    assessment = service.tenant.create_assessment(entity, 1735689600.0, 1738281600.0)
    return service, storage, audit, org, user, assessment


def test_valid_upload_normalizes_and_persists_report(submission_scope):
    service, _, audit, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="assessment-1")
    assert service.create_submission(assessment, idempotency_key="assessment-1") == submission
    version = service.create_version(submission, idempotency_key="version-1")
    assert service.create_version(submission, idempotency_key="version-1") == version
    artifact = service.upload(
        version, category="alerts", stream=io.BytesIO(ALERTS),
        filename="alerts.csv", content_type="text/csv", idempotency_key="upload-1",
    )
    assert artifact["sha3_256_digest"] == sha3_hex(ALERTS)
    assert service.upload(
        version, category="alerts", stream=io.BytesIO(ALERTS),
        filename="alerts.csv", content_type="text/csv", idempotency_key="upload-1",
    )["id"] == artifact["id"]
    assert service.read_artifact(artifact["id"]) == ALERTS
    service.complete_uploads(version)
    report = service.validate(version)
    assert report["status"] == "valid"
    assert report["totals"]["accepted"] == 1
    assert report["totals"]["rejected"] == 0
    assert report["categories"]["alerts"]["fields"] == ["created_at", "native_id", "severity"]
    assert service.get_validation_report(version) == report
    service.complete_uploads(version)
    assert service.upload(
        version, category="alerts", stream=io.BytesIO(ALERTS), filename="alerts.csv",
        content_type="text/csv", idempotency_key="upload-1",
    )["id"] == artifact["id"]
    assert service.tenant.get_submission_version(version)["status"] == "valid"
    assert service.tenant.get_submission(submission)["ingest_status"] == "valid"
    assert service.count_canonical_records(version)["alerts"] == 1
    record = service.list_canonical_records(version, category="alerts")[0]
    assert record["artifact_id"] == artifact["id"]
    assert record["payload"]["native_id"] == "A1"
    assert record["file_digest"] == artifact["sha3_256_digest"]
    actions = {event.action for event in audit.query()}
    assert {"submission.created", "submission.version_created", "submission.artifact_uploaded",
            "submission.upload_completed", "submission.validation_started",
            "submission.validation_completed", "submission.accepted"} <= actions
    assert sum(event.action == "submission.artifact_uploaded" for event in audit.query()) == 1


def test_streamed_reader_does_not_read_whole_file(tmp_path, monkeypatch):
    from satsa.submissions.readers import parse_streamed_file

    path = tmp_path / "alerts.csv"
    path.write_bytes(ALERTS)
    monkeypatch.setattr(type(path), "read_bytes", lambda self: (_ for _ in ()).throw(AssertionError("whole-file read")))
    parsed = parse_streamed_file(path, "alerts", max_rows=10)
    assert len(parsed.rows) == 1
    assert parsed.file_digest == sha3_hex(ALERTS)


def test_upload_rejects_unsafe_and_oversized_inputs(submission_scope):
    service, _, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")
    for filename, content_type in (("../alerts.csv", "text/csv"),
                                   ("alerts.exe", "application/octet-stream"),
                                   ("alerts.csv", "application/json")):
        with pytest.raises(DomainValidationError):
            service.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                           filename=filename, content_type=content_type, idempotency_key="bad")
    service.max_artifact_bytes = 8
    with pytest.raises(DomainValidationError, match="size limit"):
        service.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                       filename="alerts.csv", content_type="text/csv", idempotency_key="big")
    assert service.tenant.get_submission_version(version)["status"] == "created"


def test_invalid_report_preserves_rejections_and_version_is_immutable(submission_scope):
    service, _, audit, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    first = service.create_version(submission, idempotency_key="v1")
    bad = b"native_id,created_at,severity\nA1,not-a-date,critical\n"
    service.upload(first, category="alerts", stream=io.BytesIO(bad),
                   filename="alerts.csv", content_type="text/csv", idempotency_key="a1")
    service.complete_uploads(first)
    report = service.validate(first)
    assert report["status"] == "invalid"
    assert report["totals"]["rejected"] == 1
    assert "timestamp" in str(report["errors"])
    assert service.count_canonical_records(first) == {}
    with pytest.raises(DomainValidationError):
        service.upload(first, category="alerts", stream=io.BytesIO(ALERTS),
                       filename="alerts.csv", content_type="text/csv", idempotency_key="a2")
    second = service.create_version(submission, idempotency_key="v2")
    service.upload(second, category="alerts", stream=io.BytesIO(ALERTS),
                   filename="alerts.csv", content_type="text/csv", idempotency_key="a1")
    service.complete_uploads(second)
    assert service.validate(second)["status"] == "valid"
    assert service.get_validation_report(first) == report
    assert service.count_canonical_records(second) == {"alerts": 1}
    assert "submission.invalidated" in {event.action for event in audit.query()}


def test_upload_retry_cannot_change_bytes(submission_scope):
    service, _, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")
    service.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                   filename="alerts.csv", content_type="text/csv", idempotency_key="u")
    with pytest.raises(DomainValidationError, match="idempotency"):
        service.upload(version, category="alerts", stream=io.BytesIO(ALERTS + b"\n"),
                       filename="alerts.csv", content_type="text/csv", idempotency_key="u")


def test_failed_object_write_is_persisted_and_same_request_recovers(submission_scope):
    service, storage, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")

    class FailOnce:
        def __init__(self):
            self.failed = False

        def put_file(self, *args):
            if not self.failed:
                self.failed = True
                raise OSError("temporary object store failure")
            storage.put_file(*args)

        def copy_to(self, *args):
            return storage.copy_to(*args)

        def check_ready(self):
            return storage.check_ready()

        def close(self):
            return storage.close()

    service.storage = FailOnce()
    with pytest.raises(OSError, match="temporary object store"):
        service.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                       filename="alerts.csv", content_type="text/csv", idempotency_key="u")
    row = service.db.query_one(
        "SELECT storage_status FROM satsa_artifacts WHERE organization_id=?",
        (service.org,),
    )
    assert row == {"storage_status": "failed"}
    retried = service.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                             filename="alerts.csv", content_type="text/csv", idempotency_key="u")
    assert retried["storage_status"] == "stored"
    service.complete_uploads(version)


def test_upload_reads_in_bounded_chunks(submission_scope):
    service, _, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")

    class BoundedStream(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 64 * 1024
            return super().read(size)

    body = ALERTS + b"A2,1735689701,high\n" * 7000
    artifact = service.upload(version, category="alerts", stream=BoundedStream(body),
                              filename="alerts.csv", content_type="text/csv",
                              idempotency_key="u")
    assert artifact["size_bytes"] == len(body)


def test_cross_tenant_direct_ids_are_denied(submission_scope):
    from satsa.submissions import SubmissionService

    service, storage, audit, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")
    artifact = service.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                              filename="alerts.csv", content_type="text/csv", idempotency_key="u")
    admin = TenantAdministration(service.db)
    other_org = admin.create_organization("Other CSE")
    admin.add_membership(other_org, service.user, "satsa_analyst")
    other = SubmissionService(service.db, other_org, service.user, storage=storage, audit=audit)
    operations = (
        lambda: other.create_submission(assessment, idempotency_key="s"),
        lambda: other.create_version(submission, idempotency_key="v"),
        lambda: other.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                             filename="alerts.csv", content_type="text/csv", idempotency_key="u"),
        lambda: other.read_artifact(artifact["id"]),
        lambda: other.complete_uploads(version),
        lambda: other.get_validation_report(version),
    )
    for operation in operations:
        with pytest.raises(PermissionDeniedError):
            operation()


def test_schema_failure_is_persisted(submission_scope):
    service, _, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")
    service.upload(version, category="alerts", stream=io.BytesIO(b"other,severity\nA1,high\n"),
                   filename="alerts.csv", content_type="text/csv", idempotency_key="u")
    service.complete_uploads(version)
    report = service.validate(version)
    assert report["status"] == "invalid"
    assert "missing required" in report["errors"][0]["message"]
    assert service.get_validation_report(version) == report


@pytest.mark.parametrize("filename,content_type,body", [
    ("alerts.json", "application/json",
     b'{"alerts":[{"native_id":"A1","created_at":1735689700,"severity":"critical"}]}'),
    ("alerts.jsonl", "application/x-ndjson",
     b'{"native_id":"A1","created_at":1735689700,"severity":"critical"}\n'),
    ("alerts.ndjson", "application/x-ndjson",
     b'{"native_id":"A1","created_at":1735689700,"severity":"critical"}\n'),
])
def test_existing_json_normalizer_is_reused(submission_scope, filename, content_type, body):
    service, _, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")
    service.upload(version, category="alerts", stream=io.BytesIO(body),
                   filename=filename, content_type=content_type, idempotency_key="u")
    service.complete_uploads(version)
    report = service.validate(version)
    assert report["status"] == "valid"
    assert service.count_canonical_records(version) == {"alerts": 1}


def test_six_evidence_categories_form_one_version_snapshot(submission_scope):
    service, _, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")
    demo = Path(__file__).resolve().parents[1] / "docs/demo/submissions/CSE-EXEC"
    categories = ("alerts", "cases", "assets", "investigation_steps",
                  "escalations", "dispositions")
    for category in categories:
        with (demo / f"{category}.csv").open("rb") as stream:
            service.upload(version, category=category, stream=stream,
                           filename=f"{category}.csv", content_type="text/csv",
                           idempotency_key=category)
    service.complete_uploads(version)
    report = service.validate(version)
    assert report["status"] == "valid", report["errors"]
    assert set(service.count_canonical_records(version)) == set(categories)


def test_corrupt_stored_artifact_fails_validation(submission_scope):
    service, storage, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")
    artifact = service.upload(version, category="alerts", stream=io.BytesIO(ALERTS),
                              filename="alerts.csv", content_type="text/csv", idempotency_key="u")
    storage._path(artifact["storage_key"]).write_bytes(ALERTS + b"changed")
    service.complete_uploads(version)
    report = service.validate(version)
    assert report["status"] == "failed"
    assert service.tenant.get_submission_version(version)["status"] == "failed"
    assert not service.list_canonical_records(version)


def test_duplicate_raw_records_are_explained(submission_scope):
    service, _, _, _, _, assessment = submission_scope
    submission = service.create_submission(assessment, idempotency_key="s")
    version = service.create_version(submission, idempotency_key="v")
    body = ALERTS + b"A1,1735689700,critical\n"
    service.upload(version, category="alerts", stream=io.BytesIO(body),
                   filename="alerts.csv", content_type="text/csv", idempotency_key="u")
    service.complete_uploads(version)
    report = service.validate(version)
    assert report["status"] == "invalid"
    assert report["errors"][0]["locator"] == "row 2"
    assert "duplicate" in report["errors"][0]["message"]
