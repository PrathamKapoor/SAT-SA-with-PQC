"""Persistent asynchronous analysis queue tests for SQLite and PostgreSQL."""

from __future__ import annotations

import io
import json
import threading
import time

import pytest
from test_phase2_submission_platform import ALERTS

pytest_plugins = ["test_tenant_schema"]

from satsa.tenancy import TenantAdministration, TenantRepository


def test_execution_schema_builds_on_both_database_engines(engine):
    for table in ("satsa_run_context", "satsa_execution_jobs"):
        assert engine.query_one(f"SELECT COUNT(*) AS n FROM {table}") == {"n": 0}
    if engine.dialect == "postgresql":
        run_columns = {
            r["column_name"]
            for r in engine.query_all(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name='satsa_runs' AND table_schema=current_schema()"
            )
        }
    else:
        run_columns = {
            r["name"] for r in engine.query_all("PRAGMA table_info(satsa_runs)")
        }
    assert {
        "requested_at",
        "requested_by_user_id",
        "correlation_id",
        "progress_total",
        "progress_completed",
        "retry_count",
    } <= run_columns


def test_run_creation_is_idempotent_and_tenant_scoped(hosted_scope):
    from qsmlops.core.errors import PermissionDeniedError
    from satsa.analysis.execution import AnalysisExecutionService

    scope = hosted_scope
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    first = service.create_run(scope["version"], idempotency_key="analysis-1")
    second = service.create_run(scope["version"], idempotency_key="analysis-1")
    assert first["run_id"] == second["run_id"]
    assert first["status"] == "queued"
    assert first["entity_id"] == scope["entity"]
    assert first["assessment_id"] == scope["assessment"]
    assert first["submission_id"] == scope["submission"]
    assert first["submission_version_id"] == scope["version"]
    assert (
        scope["engine"].query_one(
            "SELECT COUNT(*) AS n FROM satsa_execution_jobs WHERE run_id=?",
            (first["run_id"],),
        )["n"]
        == 1
    )

    other_org = TenantAdministration(scope["engine"]).create_organization("Other CSE")
    identity = f"other-{other_org}"
    scope["engine"].execute(
        "INSERT INTO identities (identity_id, kind, name, owner, status, created_at, updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        (identity, "other", "other", time.time(), time.time()),
    )
    other_user = TenantAdministration(scope["engine"]).create_user(
        identity, "other@example.test"
    )
    TenantAdministration(scope["engine"]).add_membership(
        other_org, other_user, "satsa_analyst"
    )
    outsider = AnalysisExecutionService(
        scope["engine"], other_org, other_user, audit=scope["audit"]
    )
    with pytest.raises(PermissionDeniedError):
        outsider.get_run(first["run_id"])
    from satsa.analysis.execution import AnalysisExecutionWorker, Lease

    worker = AnalysisExecutionWorker(
        scope["engine"], worker_id="attacker-worker", audit=scope["audit"]
    )
    with pytest.raises(PermissionDeniedError):
        worker._resolve_context(
            Lease(first["run_id"], other_org, "attacker-worker", 1, 1)
        )


def test_queue_claim_and_lease_recovery_are_fenced(hosted_scope):
    from satsa.analysis.execution import AnalysisExecutionService, ExecutionQueue

    scope = hosted_scope
    run = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).create_run(scope["version"], idempotency_key="analysis-claim")
    queue = ExecutionQueue(scope["engine"], lease_seconds=0.05)
    claimed = queue.claim("worker-one")
    assert claimed["run_id"] == run["run_id"]
    assert queue.claim("worker-two") is None
    time.sleep(0.07)
    recovered = queue.claim("worker-two")
    assert recovered["run_id"] == run["run_id"]
    assert recovered["lease_generation"] == claimed["lease_generation"] + 1
    assert (
        queue.heartbeat(run["run_id"], "worker-one", claimed["lease_generation"])
        is False
    )
    assert (
        queue.heartbeat(run["run_id"], "worker-two", recovered["lease_generation"])
        is True
    )


def test_worker_executes_existing_analytics_and_persists_results(
    hosted_scope, tmp_path
):
    from qsmlops.core.errors import PermissionDeniedError
    from satsa.analysis.execution import (
        AnalysisExecutionService,
        AnalysisExecutionWorker,
    )

    scope = hosted_scope
    run = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).create_run(scope["version"], idempotency_key="analysis-execute")
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="test-worker",
        lease_seconds=60,
        audit=scope["audit"],
        trust_key_dir=str(tmp_path / "trust-keys"),
    )
    assert worker.run_once() in {"completed", "partial"}
    result = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).get_run(run["run_id"])
    assert result["status"] in {"completed", "partial"}
    assert result["progress_total"] > 0
    assert result["progress_completed"] == sum(
        step["status"] in {"completed", "failed", "skipped"} for step in result["steps"]
    )
    assert len(result["steps"]) == result["progress_total"]
    assert (
        scope["engine"].query_one(
            "SELECT COUNT(*) AS n FROM satsa_observations WHERE run_id=?",
            (run["run_id"],),
        )["n"]
        > 0
    )
    results = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    assert results.get_risk(run["run_id"]) is not None
    findings = results.list_findings(run["run_id"])
    assert findings
    assert results.get_finding(findings[0]["id"])["run_id"] == run["run_id"]
    assert results.list_evidence(run["run_id"])
    other_org = TenantAdministration(scope["engine"]).create_organization(
        "Finding isolation CSE"
    )
    identity = "phase3-finding-outsider"
    scope["engine"].execute(
        "INSERT INTO identities (identity_id, kind, name, owner, status, created_at, updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        (identity, "outsider", "outsider", time.time(), time.time()),
    )
    other_user = TenantAdministration(scope["engine"]).create_user(
        identity, "outsider@example.test"
    )
    TenantAdministration(scope["engine"]).add_membership(
        other_org, other_user, "satsa_analyst"
    )
    outsider = AnalysisExecutionService(
        scope["engine"], other_org, other_user, audit=scope["audit"]
    )
    with pytest.raises(PermissionDeniedError, match="finding does not belong"):
        outsider.get_finding(findings[0]["id"])
    with pytest.raises(PermissionDeniedError, match="analysis run does not belong"):
        outsider.list_evidence(run["run_id"])
    from satsa.analysis.execution import Lease
    from satsa.analysis.run import _default_workers
    from satsa.analysis.workers import DEFAULT_FAST_CLOSURE_POLICY, attach_baseline
    from satsa.contracts.orchestration import Orchestrator
    from satsa.contracts.worker import RunContext, SnapshotRef

    lease = Lease(run["run_id"], scope["org"], "test-worker", 1, 1)
    context = worker._resolve_context(lease)
    dataset = worker._load_dataset(context, scope["org"])
    reference_run = RunContext(
        run_id=run["run_id"],
        entity_id=scope["entity"],
        assessment_id=scope["assessment"],
        created_at=context["requested_at"],
    )
    reference_snapshot = SnapshotRef(
        context["snapshot_digest"], scope["entity"], scope["assessment"]
    )
    reference_workers = _default_workers(DEFAULT_FAST_CLOSURE_POLICY)
    for reference_worker in reference_workers:
        if reference_worker.name == "peer-benchmark":
            attach_baseline(
                reference_worker,
                worker._organization_peer_baseline(
                    context, scope["org"], reference_worker.thresholds.min_peers
                ),
            )
    reference_orchestrator = Orchestrator()
    for reference_worker in reference_workers:
        reference_orchestrator.register(reference_worker)
    synchronous = reference_orchestrator.run(
        reference_run, reference_snapshot, dataset, [], None
    )
    for job in synchronous:
        persisted = scope["engine"].query_one(
            "SELECT status,result_json FROM satsa_jobs WHERE run_id=? AND worker_name=?",
            (run["run_id"], job.worker_name),
        )
        assert persisted["status"] == job.status
        if job.result is None:
            assert json.loads(persisted["result_json"]) == {}
            continue
        stored_batch = json.loads(persisted["result_json"]).get("batch")
        assert stored_batch["state"] == job.result.state
        assert [f["rule_or_category"] for f in stored_batch["findings"]] == [
            f.rule_or_category for f in job.result.findings
        ]
    if scope["engine"].dialect == "sqlite":
        from satsa.analysis.run import RunService

        trust = RunService(scope["engine"]).verify_run(
            run["run_id"], tmp_path / "trust-keys"
        )
        assert trust["run"]["ok"] is True
        assert all(finding["ok"] for finding in trust["findings"])
    else:
        assert (
            scope["engine"].query_one(
                "SELECT COUNT(*) AS n FROM satsa_trust_receipts WHERE subject_id=?",
                (run["run_id"],),
            )["n"]
            == 0
        )
    assert scope["audit"].verify()[0] is True


def test_concurrent_workers_claim_a_run_once(hosted_scope):
    from satsa.analysis.execution import AnalysisExecutionService, ExecutionQueue

    scope = hosted_scope
    AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).create_run(scope["version"], idempotency_key="analysis-concurrent")
    queue = ExecutionQueue(scope["engine"], lease_seconds=1)
    barrier = threading.Barrier(3)
    claimed = []

    def claim(worker_id):
        barrier.wait()
        claimed.append(queue.claim(worker_id))

    threads = [
        threading.Thread(target=claim, args=(f"worker-{index}",)) for index in range(2)
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    assert sum(item is not None for item in claimed) == 1


def test_supervisor_cancellation_stops_at_worker_boundary(hosted_scope):
    from satsa.analysis.execution import (
        AnalysisExecutionService,
        AnalysisExecutionWorker,
    )

    scope = hosted_scope
    run = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).create_run(scope["version"], idempotency_key="analysis-cancel")
    admin = TenantAdministration(scope["engine"])
    identity = "phase3-supervisor"
    scope["engine"].execute(
        "INSERT INTO identities (identity_id, kind, name, owner, status, created_at, updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        (identity, "supervisor", "supervisor", time.time(), time.time()),
    )
    supervisor = admin.create_user(identity, "supervisor@example.test")
    admin.add_membership(scope["org"], supervisor, "satsa_supervisor")
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], supervisor, audit=scope["audit"]
    )
    assert service.cancel(run["run_id"])["status"] == "cancel_requested"
    worker = AnalysisExecutionWorker(
        scope["engine"], worker_id="cancel-worker", audit=scope["audit"]
    )
    assert worker.run_once() == "cancelled"
    assert service.get_run(run["run_id"])["status"] == "cancelled"


def test_running_worker_observes_supervisor_cancellation_at_boundary(hosted_scope):
    from satsa.analysis.execution import (
        AnalysisExecutionService,
        AnalysisExecutionWorker,
    )
    from satsa.contracts.worker import AnalyticalWorker, ObservationBatch

    entered = threading.Event()
    release = threading.Event()

    class SlowWorker(AnalyticalWorker):
        name = "cancellable-test-worker"
        version = "1"

        def evaluate(self, snapshot, dataset, baselines, policy, run_context):
            entered.set()
            assert release.wait(timeout=5)
            return ObservationBatch(self.name, self.version, {}, "not_applicable")

    scope = hosted_scope
    run = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).create_run(scope["version"], idempotency_key="analysis-running-cancel")
    admin = TenantAdministration(scope["engine"])
    identity = "phase3-running-supervisor"
    scope["engine"].execute(
        "INSERT INTO identities (identity_id, kind, name, owner, status, created_at, updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        (identity, "supervisor", "supervisor", time.time(), time.time()),
    )
    supervisor = admin.create_user(identity, "running-supervisor@example.test")
    admin.add_membership(scope["org"], supervisor, "satsa_supervisor")
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], supervisor, audit=scope["audit"]
    )
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="running-cancel-worker",
        lease_seconds=0.1,
        workers_factory=lambda: [SlowWorker()],
        audit=scope["audit"],
    )
    outcomes = []
    thread = threading.Thread(target=lambda: outcomes.append(worker.run_once()))
    thread.start()
    assert entered.wait(timeout=5)
    assert service.cancel(run["run_id"])["status"] == "cancel_requested"
    release.set()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert outcomes == ["cancelled"]
    final = service.get_run(run["run_id"])
    assert final["status"] == "cancelled"
    assert any(step["status"] == "completed" for step in final["steps"])


def test_retryable_failure_retries_then_exhausts_without_duplicate_stages(hosted_scope):
    from satsa.analysis.execution import (
        AnalysisExecutionService,
        AnalysisExecutionWorker,
        RetryableAnalysisError,
    )

    scope = hosted_scope
    run = AnalysisExecutionService(
        scope["engine"],
        scope["org"],
        scope["user"],
        audit=scope["audit"],
        max_attempts=2,
    ).create_run(scope["version"], idempotency_key="analysis-retry")

    def transient_factory():
        raise RetryableAnalysisError("temporary analytical dependency failure")

    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="retry-worker",
        workers_factory=transient_factory,
        audit=scope["audit"],
    )
    assert worker.run_once() == "retry_wait"
    job = scope["engine"].query_one(
        "SELECT status,attempt_count FROM satsa_execution_jobs WHERE run_id=?",
        (run["run_id"],),
    )
    assert job == {"status": "retry_wait", "attempt_count": 1}
    scope["engine"].execute(
        "UPDATE satsa_execution_jobs SET available_at=? WHERE run_id=?",
        (time.time() - 1, run["run_id"]),
    )
    assert worker.run_once() == "failed"
    finished = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).get_run(run["run_id"])
    assert finished["status"] == "failed"
    assert finished["retry_count"] == 1
    assert (
        scope["engine"].query_one(
            "SELECT COUNT(*) AS n FROM satsa_observations WHERE run_id=?",
            (run["run_id"],),
        )["n"]
        == 0
    )


def test_permanent_analytical_stage_failure_is_durable_and_sanitized(hosted_scope):
    from satsa.analysis.execution import (
        AnalysisExecutionService,
        AnalysisExecutionWorker,
    )
    from satsa.contracts.worker import AnalyticalWorker

    class BrokenWorker(AnalyticalWorker):
        name = "broken-test-worker"
        version = "1"

        def evaluate(self, snapshot, dataset, baselines, policy, run_context):
            raise ValueError("private diagnostic detail")

    scope = hosted_scope
    run = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).create_run(scope["version"], idempotency_key="analysis-permanent-failure")
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="failure-worker",
        workers_factory=lambda: [BrokenWorker()],
        audit=scope["audit"],
    )
    assert worker.run_once() == "failed"
    service = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    )
    state = service.get_run(run["run_id"])
    assert state["status"] == "failed"
    assert state["error_code"] == "analytical_stage_failed"
    assert "private diagnostic detail" not in str(state)
    failed_step = next(step for step in state["steps"] if step["status"] == "failed")
    assert failed_step["error"] == "Analytical stage failed."
    internal = scope["engine"].query_one(
        "SELECT internal_error FROM satsa_runs WHERE id=?", (run["run_id"],)
    )["internal_error"]
    assert "private diagnostic detail" in internal


def test_worker_heartbeat_keeps_long_stage_lease_alive(hosted_scope):
    from satsa.analysis.execution import (
        AnalysisExecutionService,
        AnalysisExecutionWorker,
    )
    from satsa.contracts.worker import AnalyticalWorker, ObservationBatch

    class SlowWorker(AnalyticalWorker):
        name = "slow-test-worker"
        version = "1"

        def evaluate(self, snapshot, dataset, baselines, policy, run_context):
            # Three lease lengths: without heartbeats the lease would expire.
            time.sleep(0.9)
            return ObservationBatch(self.name, self.version, {}, "not_applicable")

    scope = hosted_scope
    run = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).create_run(scope["version"], idempotency_key="analysis-heartbeat")
    worker = AnalysisExecutionWorker(
        scope["engine"],
        worker_id="heartbeat-worker",
        # A 0.3 s lease (heartbeat every 0.1 s) keeps the property under test
        # while leaving margin for scheduling delays on loaded CI runners.
        lease_seconds=0.3,
        workers_factory=lambda: [SlowWorker()],
        audit=scope["audit"],
    )
    assert worker.run_once() == "completed"
    assert (
        AnalysisExecutionService(
            scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
        ).get_run(run["run_id"])["status"]
        == "completed"
    )


def test_expired_lease_exhaustion_becomes_durable_failure(hosted_scope):
    from satsa.analysis.execution import AnalysisExecutionService, ExecutionQueue

    scope = hosted_scope
    run = AnalysisExecutionService(
        scope["engine"],
        scope["org"],
        scope["user"],
        audit=scope["audit"],
        max_attempts=1,
    ).create_run(scope["version"], idempotency_key="analysis-crash")
    queue = ExecutionQueue(scope["engine"], lease_seconds=0.04)
    assert queue.claim("crashed-worker") is not None
    time.sleep(0.06)
    assert queue.claim("recovery-worker") is None
    state = AnalysisExecutionService(
        scope["engine"], scope["org"], scope["user"], audit=scope["audit"]
    ).get_run(run["run_id"])
    assert state["status"] == "failed"
    assert state["error_code"] == "lease_exhausted"


def test_shared_audit_ledger_appends_are_serialized(hosted_scope, tmp_path):
    from qsmlops.evidence.ledger import EvidenceLedger
    from qsmlops.security.audit.events import AuditEvent
    from qsmlops.security.audit.service import AuditService

    scope = hosted_scope
    ledger_path = tmp_path / "shared-audit.jsonl"
    barrier = threading.Barrier(9)

    def append(index):
        audit = AuditService(EvidenceLedger(ledger_path), database=scope["engine"])
        barrier.wait()
        audit.record(
            AuditEvent.create(
                actor=f"actor-{index}", action="analysis.test", resource=f"run:{index}"
            )
        )

    threads = [threading.Thread(target=append, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    verifier = AuditService(EvidenceLedger(ledger_path), database=scope["engine"])
    assert verifier.verify()[0] is True
    assert len(verifier.query(action="analysis.test")) == 8
    assert (
        scope["engine"].query_one(
            "SELECT COUNT(*) AS n FROM audit_events WHERE action='analysis.test'"
        )["n"]
        == 8
    )


@pytest.fixture
def hosted_scope(engine, tmp_path):
    from qsmlops.evidence.ledger import EvidenceLedger
    from qsmlops.security.audit.service import AuditService
    from satsa.submissions import LocalArtifactStorage, SubmissionService

    admin = TenantAdministration(engine)
    org = admin.create_organization("Phase 3 CSE")
    engine.execute(
        "INSERT INTO identities (identity_id, kind, name, owner, status, created_at, updated_at)"
        " VALUES (?, 'human', ?, ?, 'active', ?, ?)",
        ("phase3-analyst", "analyst", "analyst", time.time(), time.time()),
    )
    user = admin.create_user("phase3-analyst", "phase3@example.test")
    admin.add_membership(org, user, "satsa_analyst")
    tenant = TenantRepository(engine, org, user)
    entity = tenant.create_entity("Execution test entity", sector="defence")
    assessment = tenant.create_assessment(entity, 1735689600.0, 1738281600.0)
    audit = AuditService(EvidenceLedger(tmp_path / "audit.jsonl"), database=engine)
    submissions = SubmissionService(
        engine,
        org,
        user,
        storage=LocalArtifactStorage(tmp_path / "artifacts"),
        audit=audit,
    )
    submission = submissions.create_submission(
        assessment, idempotency_key="assessment-1"
    )
    version = submissions.create_version(submission, idempotency_key="version-1")
    submissions.upload(
        version,
        category="alerts",
        stream=io.BytesIO(ALERTS),
        filename="alerts.csv",
        content_type="text/csv",
        idempotency_key="alerts",
    )
    submissions.complete_uploads(version)
    assert submissions.validate(version)["status"] == "valid"
    return {
        "engine": engine,
        "org": org,
        "user": user,
        "entity": entity,
        "assessment": assessment,
        "submission": submission,
        "version": version,
        "audit": audit,
        "submissions": submissions,
    }
