"""Real SQLite/PostgreSQL LangGraph checkpoint and review integration."""

from __future__ import annotations

import threading
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
    assert service.get_graph_progress(run["id"])["current_stage"] == "human_review"
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
        assert (
            scope["engine"].query_one(
                "SELECT COUNT(*) AS n FROM satsa_trust_receipts"
                " WHERE subject_type='run' AND subject_id=?",
                (run["id"],),
            )["n"]
            == 1
        )
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
        lambda: outsider.get_graph_progress(run["id"]),
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


def test_graph_has_real_stage_edges(hosted_scope):
    from satsa.analysis.execution import ExecutionQueue, Lease
    from satsa.analysis.graph import AnalysisGraphRuntime, durable_checkpointer

    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    run = service.create_run(
        scope["version"], idempotency_key="graph-edges", graph_enabled=True
    )
    assert service.get_graph_progress(run["id"])["checkpointed"] is False
    worker = AnalysisExecutionWorker(
        scope["engine"], worker_id="graph-edges", audit=scope["audit"]
    )
    claim = ExecutionQueue(scope["engine"]).claim("graph-edges")
    lease = Lease(
        run["id"],
        scope["org"],
        "graph-edges",
        claim["lease_generation"],
        claim["attempt_count"],
    )
    with durable_checkpointer(scope["engine"]) as saver:
        runtime = AnalysisGraphRuntime(
            worker, lease, worker._resolve_context(lease), saver
        )
        edges = {(edge.source, edge.target) for edge in runtime.graph.get_graph().edges}
    assert {
        ("readiness", "analysis"),
        ("analysis", "recommendations"),
        ("recommendations", "human_review"),
        ("human_review", "trust_boundary"),
    } <= edges


def test_graph_cancel_before_start_and_after_review_decision(hosted_scope):
    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    supervisor = _supervisor(scope)
    queued = service.create_run(
        scope["version"], idempotency_key="graph-pre-cancel", graph_enabled=True
    )
    supervisor.cancel(queued["id"])
    worker = AnalysisExecutionWorker(
        scope["engine"], worker_id="graph-pre-cancel", audit=scope["audit"]
    )
    assert worker.run_once() == "cancelled"
    assert service.get_run(queued["id"])["status"] == "cancelled"

    run = service.create_run(
        scope["version"], idempotency_key="graph-post-review-cancel", graph_enabled=True
    )
    assert worker.run_once() == "awaiting_review"
    supervisor.decide(run["id"], action="confirm")
    supervisor.cancel(run["id"])
    assert worker.run_once() == "cancelled"
    assert service.get_run(run["id"])["status"] == "cancelled"


def test_graph_cancel_during_analytical_worker(hosted_scope):
    from satsa.contracts.worker import AnalyticalWorker, ObservationBatch

    started = threading.Event()
    release = threading.Event()

    class SlowWorker(AnalyticalWorker):
        name = "graph-slow-test"
        version = "1"

        def evaluate(self, snapshot, dataset, baselines, policy, run_context):
            started.set()
            assert release.wait(5)
            return ObservationBatch(self.name, self.version, {}, "not_applicable")

    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    supervisor = _supervisor(scope)
    run = service.create_run(
        scope["version"], idempotency_key="graph-running-cancel", graph_enabled=True
    )
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="graph-running-cancel",
        audit=scope["audit"],
        workers_factory=lambda: [SlowWorker()],
    )
    result = []
    thread = threading.Thread(target=lambda: result.append(worker.run_once()))
    thread.start()
    assert started.wait(5)
    supervisor.cancel(run["id"])
    release.set()
    thread.join(timeout=10)
    assert result == ["cancelled"]
    assert service.get_run(run["id"])["status"] == "cancelled"
    assert service.get_review_decision(run["id"]) is None


def test_graph_does_not_request_review_when_all_stages_fail(hosted_scope):
    from satsa.contracts.worker import AnalyticalWorker

    class BrokenWorker(AnalyticalWorker):
        name = "graph-broken-test"
        version = "1"

        def evaluate(self, snapshot, dataset, baselines, policy, run_context):
            raise ValueError("invalid detector state")

    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    run = service.create_run(
        scope["version"], idempotency_key="graph-fail", graph_enabled=True
    )
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="graph-fail",
        audit=scope["audit"],
        workers_factory=lambda: [BrokenWorker()],
    )
    assert worker.run_once() == "failed"
    assert service.get_run(run["id"])["status"] == "failed"
    assert service.get_review_decision(run["id"]) is None
