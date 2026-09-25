"""Real SQLite/PostgreSQL LangGraph checkpoint and review integration."""

from __future__ import annotations

import time

import pytest

pytest_plugins = ["test_tenant_schema", "test_phase3_analysis_execution"]

from qsmlops.core.errors import PermissionDeniedError
from satsa.analysis.execution import AnalysisExecutionService, AnalysisExecutionWorker
from satsa.errors import DomainValidationError
from satsa.tenancy import TenantAdministration


def _supervisor(scope):
    db = scope["engine"]
    identity = f"supervisor-{scope['org']}"
    db.execute(
        "INSERT INTO identities (identity_id,kind,name,owner,status,created_at,updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        (identity, "supervisor", "supervisor", time.time(), time.time()),
    )
    user = TenantAdministration(db).create_user(identity, f"{identity}@example.test")
    TenantAdministration(db).add_membership(scope["org"], user, "satsa_supervisor")
    return AnalysisExecutionService(db, scope["org"], user, audit=scope["audit"])


def test_graph_pauses_persists_and_resumes_without_duplicate_results(
    hosted_scope, tmp_path
):
    from satsa.analysis.graph import durable_checkpointer

    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    run = service.create_run(
        scope["version"], idempotency_key="graph-main", graph_enabled=True
    )
    with pytest.raises(DomainValidationError):
        service.create_run(scope["version"], idempotency_key="graph-main")
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="graph-worker",
        audit=scope["audit"],
        trust_key_dir=str(tmp_path / "keys"),
    )
    assert worker.run_once() == "awaiting_review"
    assert service.get_run(run["id"])["status"] == "awaiting_review"
    findings = service.list_findings(run["id"])
    recommendations = service.list_recommendations(run["id"])
    assert findings and len(recommendations) == len(findings)
    assert service.get_risk(run["id"])
    with durable_checkpointer(scope["engine"]) as saver:
        checkpoint = saver.get_tuple(
            {"configurable": {"thread_id": f"satsa:{run['id']}"}}
        )
        assert checkpoint is not None
        assert (
            checkpoint.checkpoint["channel_values"]["current_stage"] == "human_review"
        )

    analyst = service
    with pytest.raises(PermissionDeniedError):
        analyst.decide(run["id"], action="confirm")
    supervisor = _supervisor(scope)
    with pytest.raises(DomainValidationError):
        supervisor.decide(run["id"], action="annotate")
    decision = supervisor.decide(
        run["id"], action="confirm", reason="Reviewed evidence"
    )
    assert (
        supervisor.decide(run["id"], action="confirm", reason="Reviewed evidence")["id"]
        == decision["id"]
    )
    # A new worker object must recover the persisted graph interrupt.
    restarted = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="restarted-worker",
        audit=scope["audit"],
        trust_key_dir=str(tmp_path / "keys"),
    )
    assert restarted.run_once() in {"completed", "partial"}
    assert restarted.run_once() is None
    assert service.get_run(run["id"])["status"] in {"completed", "partial"}
    assert len(service.list_findings(run["id"])) == len(findings)
    assert len(service.list_recommendations(run["id"])) == len(recommendations)
    assert service.get_review_decision(run["id"])["id"] == decision["id"]
    assert (
        scope["engine"].query_one(
            "SELECT COUNT(*) AS n FROM satsa_run_review_decisions WHERE run_id=?",
            (run["id"],),
        )["n"]
        == 1
    )
    if scope["engine"].dialect == "sqlite":
        from satsa.analysis.run import RunService

        trust = RunService(scope["engine"]).verify_run(run["id"], tmp_path / "keys")
        assert trust["run"]["ok"] is True
        assert all(item["ok"] for item in trust["findings"])
    else:
        assert (
            scope["engine"].query_one(
                "SELECT COUNT(*) AS n FROM satsa_trust_receipts WHERE subject_id=?",
                (run["id"],),
            )["n"]
            == 0
        )
    assert scope["audit"].verify()[0] is True


def test_graph_review_is_tenant_scoped(hosted_scope):
    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    run = service.create_run(
        scope["version"], idempotency_key="graph-isolation", graph_enabled=True
    )
    other_org = TenantAdministration(scope["engine"]).create_organization(
        "Other review CSE"
    )
    identity = f"other-supervisor-{other_org}"
    scope["engine"].execute(
        "INSERT INTO identities (identity_id,kind,name,owner,status,created_at,updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        (identity, "other", "other", time.time(), time.time()),
    )
    user = TenantAdministration(scope["engine"]).create_user(
        identity, f"{identity}@example.test"
    )
    TenantAdministration(scope["engine"]).add_membership(
        other_org, user, "satsa_supervisor"
    )
    outsider = AnalysisExecutionService(
        scope["engine"], other_org, user, audit=scope["audit"]
    )
    for operation in (
        lambda: outsider.get_run(run["id"]),
        lambda: outsider.list_recommendations(run["id"]),
        lambda: outsider.get_review_decision(run["id"]),
        lambda: outsider.decide(run["id"], action="confirm"),
    ):
        with pytest.raises(PermissionDeniedError):
            operation()


def test_graph_checkpoint_resumes_after_transient_node_failure(
    hosted_scope, monkeypatch
):
    from satsa.analysis.execution import RetryableAnalysisError

    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    run = service.create_run(
        scope["version"], idempotency_key="graph-retry", graph_enabled=True
    )
    worker = AnalysisExecutionWorker(
        scope["engine"], worker_id="graph-retry-one", audit=scope["audit"]
    )
    original = worker._persist_recommendations
    called = False

    def fail_once(lease):
        nonlocal called
        if not called:
            called = True
            raise RetryableAnalysisError("temporary recommendation storage failure")
        return original(lease)

    monkeypatch.setattr(worker, "_persist_recommendations", fail_once)
    assert worker.run_once() == "retry_wait"
    before = {
        row["worker_name"]: row["attempt"]
        for row in scope["engine"].query_all(
            "SELECT worker_name,attempt FROM satsa_jobs WHERE run_id=?", (run["id"],)
        )
    }
    scope["engine"].execute(
        "UPDATE satsa_execution_jobs SET available_at=0 WHERE run_id=?", (run["id"],)
    )
    restarted = AnalysisExecutionWorker(
        scope["engine"], worker_id="graph-retry-two", audit=scope["audit"]
    )
    assert restarted.run_once() == "awaiting_review"
    after = {
        row["worker_name"]: row["attempt"]
        for row in scope["engine"].query_all(
            "SELECT worker_name,attempt FROM satsa_jobs WHERE run_id=?", (run["id"],)
        )
    }
    assert before == after
    assert service.list_recommendations(run["id"])


def test_supervisor_can_cancel_graph_at_review_checkpoint(hosted_scope):
    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    run = service.create_run(
        scope["version"], idempotency_key="graph-cancel", graph_enabled=True
    )
    worker = AnalysisExecutionWorker(
        scope["engine"], worker_id="graph-cancel-one", audit=scope["audit"]
    )
    assert worker.run_once() == "awaiting_review"
    supervisor = _supervisor(scope)
    assert supervisor.cancel(run["id"])["status"] == "cancel_requested"
    resumed = AnalysisExecutionWorker(
        scope["engine"], worker_id="graph-cancel-two", audit=scope["audit"]
    )
    assert resumed.run_once() == "cancelled"
    assert service.get_run(run["id"])["status"] == "cancelled"
    with pytest.raises(DomainValidationError):
        supervisor.decide(run["id"], action="confirm")
