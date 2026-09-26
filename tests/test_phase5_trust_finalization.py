"""Supervisory trust integration using real SQLite and PostgreSQL."""

import json
import threading
from pathlib import Path

import pytest
from test_phase4_langgraph import _supervisor

from satsa.analysis.execution import AnalysisExecutionService, AnalysisExecutionWorker
from satsa.analysis.trust import TrustService

pytest_plugins = ["test_tenant_schema", "test_phase3_analysis_execution"]


def _reviewed(scope, tmp_path, *, graph=False, prepare=None):
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    run = service.create_run(
        scope["version"],
        idempotency_key="reviewed",
        graph_enabled=graph,
        review_required=True,
    )
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="review-worker",
        audit=scope["audit"],
        trust_key_dir=str(tmp_path / "keys"),
    )
    assert worker.run_once() == "awaiting_review"
    if prepare:
        prepare(scope["engine"], run)
    decision = _supervisor(scope).decide(
        run["id"], action="confirm", reason="Evidence reviewed — सत्य"
    )
    trust = TrustService(
        scope["engine"], tmp_path / "keys", organization_id=scope["org"]
    )
    return service, run, worker, decision, trust


def test_supervisory_receipt_binds_live_decision(hosted_scope, tmp_path):
    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    run = service.create_run(
        scope["version"], idempotency_key="trusted", graph_enabled=True
    )
    keys = Path(tmp_path / "keys")
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="trust-worker",
        audit=scope["audit"],
        trust_key_dir=str(keys),
    )
    assert worker.run_once() == "awaiting_review"
    decision = _supervisor(scope).decide(
        run["id"], action="confirm", reason="Examined evidence ✓"
    )
    assert worker.run_once() in {"completed", "partial"}
    trust = TrustService(scope["engine"], keys, organization_id=scope["org"])
    assert trust.verify_finalization(run["id"], scope["audit"]) == (True, "ok")
    scope["engine"].execute(
        "UPDATE satsa_run_review_decisions SET reason=? WHERE id=?",
        ("Different decision", decision["id"]),
    )
    assert trust.verify_finalization(run["id"], scope["audit"])[0] is False


def test_non_graph_finalization_and_repeated_execution(hosted_scope, tmp_path):
    service, run, worker, decision, trust = _reviewed(hosted_scope, tmp_path)
    assert worker.run_once() in {"completed", "partial"}
    first = service.get_trust_receipt(run["id"])
    for _ in range(3):
        assert trust.finalize(run["id"], hosted_scope["audit"]) == first
        assert service.verify_trust(run["id"]) == (True, "ok")
    db = hosted_scope["engine"]
    assert db.query_one("SELECT COUNT(*) AS n FROM satsa_trust_finalizations")["n"] == 1
    assert (
        db.query_one(
            "SELECT COUNT(*) AS n FROM satsa_trust_receipts WHERE subject_type='supervisory_finalization'"
        )["n"]
        == 1
    )
    assert len(hosted_scope["audit"].query(action="trust.supervisory_finalized")) == 1
    assert service.get_review_decision(run["id"])["id"] == decision["id"]
    assert "secret_key" not in json.dumps(first)


@pytest.mark.parametrize(
    "stage",
    ["canonicalized", "prepared", "signed", "recorded", "ledger_appended", "verified"],
)
def test_finalization_recovers_at_durable_boundaries(hosted_scope, tmp_path, stage):
    _service, run, worker, _decision, trust = _reviewed(hosted_scope, tmp_path)

    def crash(boundary):
        if boundary == stage:
            raise RuntimeError("simulated process interruption")

    with pytest.raises(RuntimeError, match="interruption"):
        trust.finalize(run["id"], hosted_scope["audit"], boundary=crash)
    # Reconstruct the service, not an in-memory reconstruction of progress.
    restarted = TrustService(
        hosted_scope["engine"], tmp_path / "keys", organization_id=hosted_scope["org"]
    )
    restarted.finalize(run["id"], hosted_scope["audit"])
    assert restarted.verify_finalization(run["id"], hosted_scope["audit"]) == (
        True,
        "ok",
    )
    assert worker.run_once() in {"completed", "partial"}
    assert len(hosted_scope["audit"].query(action="trust.supervisory_finalized")) == 1


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("decision", "decision digest mismatch"),
        ("decision_time", "decision digest mismatch"),
        ("decision_id", "live canonical state mismatch"),
        ("finding", "finding digest mismatch"),
        ("risk", "risk digest mismatch"),
        ("recommendation", "recommendation digest mismatch"),
        ("evidence", "finding digest mismatch"),
        ("provenance", "source provenance relationship mismatch"),
        ("source", "reviewed context changed before finalization"),
        ("canonical", "live canonical state mismatch"),
        ("receipt", "signature does not verify"),
        ("receipt_time", "final ledger binding mismatch"),
        ("ledger", "ledger integrity failure"),
    ],
)
def test_live_tamper_detection(hosted_scope, tmp_path, mutation, reason):
    _service, run, worker, decision, trust = _reviewed(hosted_scope, tmp_path)
    assert worker.run_once() in {"completed", "partial"}
    db = hosted_scope["engine"]
    if mutation == "decision":
        db.execute(
            "UPDATE satsa_run_review_decisions SET action='dismiss' WHERE id=?",
            (decision["id"],),
        )
    elif mutation == "decision_time":
        db.execute(
            "UPDATE satsa_run_review_decisions SET created_at=created_at+1 WHERE id=?",
            (decision["id"],),
        )
    elif mutation == "decision_id":
        row = db.query_one("SELECT canonical_json FROM satsa_trust_finalizations")
        document = json.loads(row["canonical_json"])
        document["decision"]["id"] = "forged-decision"
        db.execute(
            "UPDATE satsa_trust_finalizations SET canonical_json=?",
            (json.dumps(document),),
        )
    elif mutation == "finding":
        db.execute("UPDATE satsa_findings SET rationale='altered'")
    elif mutation == "risk":
        db.execute("UPDATE satsa_run_risk SET profile_json='{}'")
    elif mutation == "recommendation":
        db.execute("UPDATE satsa_run_recommendations SET recommendation_json='{}'")
    elif mutation == "evidence":
        db.execute("UPDATE satsa_findings SET evidence_refs_json='[]'")
    elif mutation == "provenance":
        db.execute("UPDATE satsa_source_records SET version_id=NULL")
    elif mutation == "source":
        db.execute("UPDATE satsa_source_records SET locator='changed'")
    elif mutation == "canonical":
        db.execute("UPDATE satsa_trust_finalizations SET canonical_json='{}'")
    elif mutation == "receipt":
        db.execute(
            "UPDATE satsa_trust_receipts SET signature=? WHERE subject_type='supervisory_finalization'",
            (b"broken",),
        )
    elif mutation == "receipt_time":
        db.execute(
            "UPDATE satsa_trust_receipts SET created_at=created_at+1 WHERE subject_type='supervisory_finalization'"
        )
    elif mutation == "ledger":
        path = hosted_scope["audit"]._ledger.path
        lines = path.read_text(encoding="utf-8").splitlines()
        entry = json.loads(lines[-1])
        entry["prev_hash"] = "0" * 64
        lines[-1] = json.dumps(entry)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok, message = trust.verify_finalization(run["id"], hosted_scope["audit"])
    assert ok is False and reason in message


def test_concurrent_finalization_has_one_receipt_and_ledger_event(
    hosted_scope, tmp_path
):
    service, run, _worker, _decision, trust = _reviewed(hosted_scope, tmp_path)
    errors = []

    def finalize():
        try:
            trust.finalize(run["id"], hosted_scope["audit"])
        except Exception as exc:  # noqa: BLE001 - collect worker-thread failures
            errors.append(exc)

    threads = [threading.Thread(target=finalize) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()
    assert not errors
    assert service.verify_trust(run["id"]) == (True, "ok")
    assert len(hosted_scope["audit"].query(action="trust.supervisory_finalized")) == 1


def test_tenant_trust_cannot_use_foreign_run_or_receipt(hosted_scope, tmp_path):
    from qsmlops.core.errors import PermissionDeniedError
    from satsa.tenancy import TenantAdministration

    service, run, worker, _decision, _trust = _reviewed(hosted_scope, tmp_path)
    worker.run_once()
    other = TenantAdministration(hosted_scope["engine"]).create_organization(
        "Other trust CSE"
    )
    outsider = TrustService(hosted_scope["engine"], None, organization_id=other)
    for call in (
        lambda: outsider.get_final_receipt(run["id"]),
        lambda: outsider.verify_finalization(run["id"], hosted_scope["audit"]),
        lambda: outsider.finalize(run["id"], hosted_scope["audit"]),
        lambda: outsider.get_final_receipt(service.get_trust_receipt(run["id"])["id"]),
    ):
        with pytest.raises(PermissionDeniedError):
            call()


def test_graph_retry_reuses_receipt_and_checkpoint(hosted_scope, tmp_path, monkeypatch):
    from satsa.analysis.execution import RetryableAnalysisError

    service, run, worker, _decision, _trust = _reviewed(
        hosted_scope, tmp_path, graph=True
    )
    original = TrustService.finalize
    crashed = False

    def interrupted(self, run_id, audit, **kwargs):
        nonlocal crashed

        def boundary(stage):
            nonlocal crashed
            if stage == "ledger_appended" and not crashed:
                crashed = True
                raise RetryableAnalysisError("worker interrupted")

        return original(self, run_id, audit, boundary=boundary)

    monkeypatch.setattr(TrustService, "finalize", interrupted)
    assert worker.run_once() == "retry_wait"
    assert service.get_run(run["id"])["status"] != "completed"
    hosted_scope["engine"].execute(
        "UPDATE satsa_execution_jobs SET available_at=0 WHERE run_id=?", (run["id"],)
    )
    restarted = AnalysisExecutionWorker(
        hosted_scope["engine"],
        worker_id="restart",
        audit=hosted_scope["audit"],
        trust_key_dir=str(tmp_path / "keys"),
    )
    assert restarted.run_once() in {"completed", "partial"}
    assert service.verify_trust(run["id"]) == (True, "ok")
    assert len(hosted_scope["audit"].query(action="trust.supervisory_finalized")) == 1


def test_canonical_document_is_stable_and_references_only(hosted_scope, tmp_path):
    from qsmlops.crypto.hashing import canonical_json, digest_document
    from satsa.analysis.canonical import supervisory_document

    _service, run, _worker, _decision, _trust = _reviewed(hosted_scope, tmp_path)
    first = supervisory_document(hosted_scope["engine"], hosted_scope["org"], run["id"])
    second = supervisory_document(
        hosted_scope["engine"], hosted_scope["org"], run["id"]
    )
    assert canonical_json(first) == canonical_json(second)
    assert canonical_json(first) == canonical_json(dict(reversed(list(first.items()))))
    assert first["run"]["model_version"] is None
    assert "सत्य" in canonical_json(first).decode("utf-8")
    assert "payload_json" not in json.dumps(first)
    different = json.loads(json.dumps(first))
    different["decision"]["reason"] = "changed"
    assert digest_document(first) != digest_document(different)


def test_changed_results_after_review_cannot_be_finalized(hosted_scope, tmp_path):
    service, run, worker, _decision, _trust = _reviewed(hosted_scope, tmp_path)
    hosted_scope["engine"].execute(
        "UPDATE satsa_run_recommendations SET action='changed'"
    )
    assert worker.run_once() == "failed"
    assert service.get_run(run["id"])["status"] == "failed"
    assert (
        hosted_scope["engine"].query_one(
            "SELECT COUNT(*) AS n FROM satsa_trust_finalizations"
        )["n"]
        == 0
    )


def test_missing_key_configuration_does_not_complete_supervised_run(
    hosted_scope, tmp_path
):
    service, run, worker, _decision, _trust = _reviewed(hosted_scope, tmp_path)
    worker.trust_key_dir = None
    assert worker.run_once() == "failed"
    assert service.get_run(run["id"])["status"] == "failed"
    assert service.verify_trust(run["id"])[0] is False


def test_legacy_unscoped_verifier_cannot_access_supervisory_receipts(
    hosted_scope, tmp_path
):
    if hosted_scope["engine"].dialect != "sqlite":
        from qsmlops.core.errors import PermissionDeniedError

        with pytest.raises(PermissionDeniedError, match="offline-only"):
            TrustService(hosted_scope["engine"], tmp_path / "keys")
        return
    service, run, worker, _decision, _trust = _reviewed(hosted_scope, tmp_path)
    worker.run_once()
    receipt = service.get_trust_receipt(run["id"])
    legacy = TrustService(hosted_scope["engine"], tmp_path / "keys")
    with pytest.raises(ValueError, match="requires tenant context"):
        legacy.verify_subject(
            "supervisory_finalization", receipt["id"], receipt["content_digest"]
        )


def test_cutover_validator_includes_supervisory_trust_records(hosted_scope, tmp_path):
    from satsa.migration_validation import validate_migration

    _service, _run, worker, _decision, _trust = _reviewed(hosted_scope, tmp_path)
    worker.run_once()
    counts = validate_migration(
        hosted_scope["engine"],
        hosted_scope["engine"],
        {hosted_scope["entity"]: hosted_scope["org"]},
    )
    assert counts["satsa_trust_finalizations"] == 1
    assert counts["satsa_run_review_decisions"] == 1


def test_cancel_requested_lease_can_heartbeat_until_safe_boundary(
    hosted_scope, monkeypatch
):
    from satsa.analysis.execution import ExecutionQueue

    service = AnalysisExecutionService(
        hosted_scope["engine"],
        hosted_scope["org"],
        hosted_scope["user"],
        audit=hosted_scope["audit"],
    )
    run = service.create_run(
        hosted_scope["version"], idempotency_key="cancel-heartbeat"
    )
    queue = ExecutionQueue(hosted_scope["engine"], lease_seconds=60)
    claim = queue.claim("cancel-worker")
    _supervisor(hosted_scope).cancel(run["id"])
    before = hosted_scope["engine"].query_one(
        "SELECT lease_expires_at FROM satsa_execution_jobs WHERE run_id=?", (run["id"],)
    )["lease_expires_at"]
    monkeypatch.setattr("satsa.analysis.execution.time.time", lambda: before - 30)
    assert queue.heartbeat(run["id"], "cancel-worker", claim["lease_generation"])
    after = hosted_scope["engine"].query_one(
        "SELECT lease_expires_at,status FROM satsa_execution_jobs WHERE run_id=?",
        (run["id"],),
    )
    assert after["lease_expires_at"] == before + 30
    assert after["status"] == "cancel_requested"


@pytest.mark.parametrize(
    "column,value",
    [
        ("scoped_subjects_json", "[]"),
        ("evidence_refs_json", "[]"),
        ("confidence_json", "null"),
    ],
)
def test_malformed_empty_finding_fields_do_not_verify(
    hosted_scope, tmp_path, column, value
):
    from satsa.analysis.canonical import live_finding_digest

    selected = {}

    def prepare(db, run):
        row = db.query_one(
            "SELECT f.* FROM satsa_findings f JOIN satsa_observations o ON o.id=f.observation_id WHERE o.run_id=? ORDER BY f.id LIMIT 1",
            (run["id"],),
        )
        selected["id"] = row["id"]
        row[column] = value
        db.execute(
            f"UPDATE satsa_findings SET {column}=?,content_digest=? WHERE id=?",
            (value, live_finding_digest(row), row["id"]),
        )

    service, run, worker, _decision, _trust = _reviewed(
        hosted_scope, tmp_path, prepare=prepare
    )
    assert worker.run_once() in {"completed", "partial"}
    hosted_scope["engine"].execute(
        f"UPDATE satsa_findings SET {column}=? WHERE id=?", ("{broken", selected["id"])
    )
    assert service.verify_trust(run["id"])[0] is False


def test_cancellation_during_finalization_does_not_claim_trusted_completion(
    hosted_scope, tmp_path, monkeypatch
):
    service, run, worker, _decision, _trust = _reviewed(
        hosted_scope, tmp_path, graph=True
    )
    reviewer = hosted_scope["engine"].query_one(
        "SELECT user_id FROM satsa_run_review_decisions WHERE run_id=?", (run["id"],)
    )["user_id"]
    cancellation = AnalysisExecutionService(
        hosted_scope["engine"],
        hosted_scope["org"],
        reviewer,
        audit=hosted_scope["audit"],
    )
    original = TrustService.finalize

    def cancel_at_recorded(self, run_id, audit, **kwargs):
        outer = kwargs["boundary"]

        def boundary(stage):
            if stage == "recorded":
                cancellation.cancel(run_id)
            outer(stage)

        return original(self, run_id, audit, boundary=boundary)

    monkeypatch.setattr(TrustService, "finalize", cancel_at_recorded)
    assert worker.run_once() == "cancelled"
    assert service.get_run(run["id"])["status"] == "cancelled"
    assert service.verify_trust(run["id"])[0] is False
    assert not hosted_scope["audit"].query(action="trust.verification_completed")


def test_cancellation_after_verification_before_queue_commit_is_cancelled(
    hosted_scope, tmp_path, monkeypatch
):
    service, run, worker, _decision, _trust = _reviewed(hosted_scope, tmp_path)
    reviewer = hosted_scope["engine"].query_one(
        "SELECT user_id FROM satsa_run_review_decisions WHERE run_id=?", (run["id"],)
    )["user_id"]
    cancellation = AnalysisExecutionService(
        hosted_scope["engine"],
        hosted_scope["org"],
        reviewer,
        audit=hosted_scope["audit"],
    )
    original = TrustService.finalize

    def after_verification(self, run_id, audit, **kwargs):
        receipt = original(self, run_id, audit, **kwargs)
        cancellation.cancel(run_id)
        return receipt

    monkeypatch.setattr(TrustService, "finalize", after_verification)
    assert worker.run_once() == "cancelled"
    assert service.get_run(run["id"])["status"] == "cancelled"
    assert service.verify_trust(run["id"]) == (
        True,
        "ok",
    )  # proves decision, not completion
    assert service.get_run(run["id"])["error_code"] == ""
    assert not hosted_scope["audit"].query(action="analysis.failed")


@pytest.mark.parametrize(
    "table,key", [("satsa_entities", "entity"), ("satsa_assessments", "assessment")]
)
def test_verification_rechecks_context_ownership_not_only_run_ownership(
    hosted_scope, tmp_path, table, key
):
    from satsa.tenancy import TenantAdministration

    service, run, worker, _decision, _trust = _reviewed(hosted_scope, tmp_path)
    worker.run_once()
    other = TenantAdministration(hosted_scope["engine"]).create_organization(
        "Other entity owner"
    )
    hosted_scope["engine"].execute(
        f"UPDATE {table} SET organization_id=? WHERE id=?", (other, hosted_scope[key])
    )
    assert service.verify_trust(run["id"])[0] is False
