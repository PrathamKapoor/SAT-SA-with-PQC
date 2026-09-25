"""Tenant ownership and session behavior, exercised in both storage modes."""
from __future__ import annotations

import time
import sqlite3

import pytest

from qsmlops.core.errors import PermissionDeniedError, StorageError
from satsa.tenancy import (
    PeerAccessPolicy, TenantAdministration, TenantRepository, SessionRepository,
)
from test_tenant_schema import engine
from test_postgres_engine import postgres_dsn


def _identity(db, name):
    db.execute(
        "INSERT INTO identities (identity_id, kind, name, owner, status, created_at, updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        (name, name, name, time.time(), time.time()),
    )
    return name


def test_membership_role_and_direct_id_isolation(engine):
    admin = TenantAdministration(engine)
    org_a = admin.create_organization("CSE A")
    org_b = admin.create_organization("CSE B")
    alice = admin.create_user(_identity(engine, "alice"), "alice@example.test")
    bob = admin.create_user(_identity(engine, "bob"), "bob@example.test")
    admin.add_membership(org_a, alice, "satsa_analyst")
    admin.add_membership(org_b, bob, "satsa_analyst")
    a = TenantRepository(engine, org_a, alice)
    b = TenantRepository(engine, org_b, bob)
    entity_a = a.create_entity("Same entity")
    entity_b = b.create_entity("Same entity")
    assert entity_a != entity_b
    assert a.get_entity(entity_a)["id"] == entity_a
    assert b.get_entity(entity_b)["id"] == entity_b
    assert a.peer_entity_ids(entity_a) == []
    with pytest.raises(PermissionDeniedError):
        TenantRepository(engine, org_a, alice,
                         peer_policy=PeerAccessPolicy.AUTHORIZED_AGGREGATE).peer_entity_ids(entity_a)
    assert a.get_entity(entity_b) is None
    assert b.get_entity(entity_a) is None
    assessment_b = b.create_assessment(entity_b, 1.0, 2.0)
    assert a.get_assessment(assessment_b) is None
    with pytest.raises(PermissionDeniedError):
        a.close_assessment(assessment_b)
    assert b.get_assessment(assessment_b)["status"] == "open"
    submission_b = b.create_submission(assessment_b)
    assert a.get_submission(submission_b) is None
    version_b = b.create_submission_version(submission_b, 1)
    with pytest.raises((sqlite3.IntegrityError, StorageError)):
        engine.execute(
            "INSERT INTO satsa_submission_versions"
            " (id, organization_id, submission_id, version, created_at)"
            " VALUES (?,?,?,?,?)",
            ("wrong-owner-version", org_a, submission_b, 2, 1.0),
        )
    assert a.get_submission_version(version_b) is None
    with pytest.raises(PermissionDeniedError):
        a.create_artifact(version_b, "file.csv", "text/csv", 3, "a" * 64)
    artifact_b = b.create_artifact(version_b, "file.csv", "text/csv", 3, "a" * 64)
    assert a.get_artifact(artifact_b) is None
    assert b.get_artifact(artifact_b)["size_bytes"] == 3

    engine.execute(
        "INSERT INTO satsa_source_records (id, submission_id, file_digest, format,"
        " locator, original_record_digest) VALUES (?,?,?,?,?,?)",
        ("source-b", submission_b, "file-digest", "csv", "row:1", "record-digest"),
    )
    engine.execute(
        "INSERT INTO satsa_runs (id, organization_id, entity_id, assessment_id,"
        " snapshot_digest, created_at) VALUES (?,?,?,?,?,?)",
        ("run-b", org_b, entity_b, assessment_b, "snapshot", 1.0),
    )
    engine.execute(
        "INSERT INTO satsa_observations (id, run_id, worker_name, entity_id,"
        " assessment_id, created_at) VALUES (?,?,?,?,?,?)",
        ("observation-b", "run-b", "worker", entity_b, assessment_b, 1.0),
    )
    engine.execute(
        "INSERT INTO satsa_findings (id, observation_id, rule_or_category, state,"
        " created_at) VALUES (?,?,?,?,?)",
        ("finding-b", "observation-b", "rule", "signal", 1.0),
    )
    engine.execute(
        "INSERT INTO satsa_review_decisions (id, finding_id, principal_identity_id,"
        " action, occurred_at, created_at) VALUES (?,?,?,?,?,?)",
        ("review-b", "finding-b", "bob", "confirm", 1.0, 1.0),
    )
    engine.execute(
        "INSERT INTO satsa_trust_receipts (subject_type, subject_id, algorithm_id,"
        " public_key, content_digest, signature, created_at) VALUES (?,?,?,?,?,?,?)",
        ("finding", "finding-b", "ML-DSA-65", b"key", "digest", b"sig", 1.0),
    )
    receipt_id = engine.query_one(
        "SELECT id FROM satsa_trust_receipts WHERE subject_id=?", ("finding-b",)
    )["id"]
    assert b.get_source_record("source-b")["id"] == "source-b"
    assert b.get_run("run-b")["id"] == "run-b"
    assert b.get_finding("finding-b")["id"] == "finding-b"
    assert b.get_review("review-b")["id"] == "review-b"
    assert b.get_trust_receipt(receipt_id)["id"] == receipt_id
    assert a.get_source_record("source-b") is None
    assert a.get_run("run-b") is None
    assert a.get_finding("finding-b") is None
    assert a.get_review("review-b") is None
    assert a.get_trust_receipt(receipt_id) is None

    admin.set_membership_status(org_a, alice, "revoked")
    with pytest.raises(PermissionDeniedError):
        a.get_entity(entity_a)


def test_role_enforcement_and_session_lifecycle(engine):
    admin = TenantAdministration(engine)
    org = admin.create_organization("CSE C")
    viewer = admin.create_user(_identity(engine, "viewer"), "viewer@example.test")
    admin.add_membership(org, viewer, "satsa_viewer")
    scope = TenantRepository(engine, org, viewer)
    with pytest.raises(PermissionDeniedError):
        scope.create_entity("No write")

    sessions = SessionRepository(engine)
    token = sessions.create(viewer, ttl_seconds=60, now=100.0)
    assert sessions.resolve(token, now=101.0)["user_id"] == viewer
    assert sessions.touch(token, now=120.0)
    assert sessions.resolve(token, now=121.0)["last_activity_at"] == 120.0
    assert sessions.resolve(token, now=160.0) is None
    another = sessions.create(viewer, ttl_seconds=60, now=200.0)
    assert sessions.revoke(another, now=210.0)
    assert sessions.resolve(another, now=211.0) is None


def test_legacy_unscoped_repository_is_rejected_for_postgres(postgres_dsn):
    from qsmlops.database.engine import create_engine
    from satsa.store.repositories import EntityStore
    from satsa.analysis.repository import FindingStore

    db = create_engine(postgres_dsn)
    try:
        with pytest.raises(PermissionDeniedError):
            EntityStore(db)
        with pytest.raises(PermissionDeniedError):
            FindingStore(db)
    finally:
        db.close()
