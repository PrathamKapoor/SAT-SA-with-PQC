"""Phase 2 — SAT-SA worker/orchestration skeleton tests (Part K).

Proves the Analysis Run -> Job -> Processor -> Result skeleton actually
executes, using only the trivial EchoWorker/CrashingWorker test doubles
defined in satsa.contracts.worker — no real detector exists yet, and this
file does not pretend otherwise.
"""
from __future__ import annotations

import pytest

from satsa.contracts.orchestration import Orchestrator
from satsa.contracts.worker import (
    BaselineRef,
    CrashingWorker,
    EchoWorker,
    ObservationBatch,
    PolicyRef,
    RunContext,
    SnapshotRef,
)


def _run_context() -> RunContext:
    return RunContext(run_id="run-1", entity_id="entity-1", assessment_id="assess-1")


def _empty_dataset():
    from satsa.store.dataset import CanonicalDataset
    return CanonicalDataset(entity_id="entity-1", assessment_id="assess-1")


def test_echo_worker_produces_a_completed_job():
    orch = Orchestrator()
    orch.register(EchoWorker())
    jobs = orch.run(_run_context(), SnapshotRef("d", "entity-1", "assess-1"),
                    _empty_dataset(), [], None)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.status == "completed"
    assert job.worker_name == "echo-worker"
    assert job.result is not None
    assert job.result.state == "not_applicable"
    assert job.error == ""


def test_crashing_worker_produces_a_failed_job_not_a_crashed_orchestrator():
    orch = Orchestrator()
    orch.register(EchoWorker())
    orch.register(CrashingWorker())
    jobs = orch.run(_run_context(), SnapshotRef("d", "entity-1", "assess-1"),
                    _empty_dataset(), [], None)

    by_name = {j.worker_name: j for j in jobs}
    assert len(jobs) == 2
    assert by_name["echo-worker"].status == "completed"
    assert by_name["crashing-worker"].status == "failed"
    assert "simulated worker crash" in by_name["crashing-worker"].error
    assert by_name["crashing-worker"].result is None  # withheld, not a default/empty batch


def test_duplicate_worker_registration_rejected():
    orch = Orchestrator()
    orch.register(EchoWorker())
    with pytest.raises(ValueError, match="already registered"):
        orch.register(EchoWorker())


def test_invalid_observation_batch_becomes_a_failed_job():
    """A worker that returns a structurally invalid batch (Part K:
    "A malformed output is an error, not automatically a cyber finding" —
    docs/phase1/agent-architecture.md) must not silently pass through as a
    completed job with garbage results."""

    class BadWorker(EchoWorker):
        name = "bad-worker"

        def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
            return ObservationBatch(
                worker_name=self.name, detector_version="0.0.1", scope={},
                state="definitely-not-a-real-state",
            )

    orch = Orchestrator()
    orch.register(BadWorker())
    jobs = orch.run(_run_context(), SnapshotRef("d", "e", "a"),
                    _empty_dataset(), [], None)

    assert jobs[0].status == "failed"
    assert "invalid ObservationBatch" in jobs[0].error


def test_registered_workers_run_in_deterministic_order():
    orch = Orchestrator()
    orch.register(CrashingWorker())
    orch.register(EchoWorker())
    assert orch.registered_workers == ["crashing-worker", "echo-worker"]  # sorted, not insertion order

    jobs = orch.run(_run_context(), SnapshotRef("d", "e", "a"),
                    _empty_dataset(), [], None)
    assert [j.worker_name for j in jobs] == ["crashing-worker", "echo-worker"]


def test_job_to_dict_serializes_result_when_present():
    orch = Orchestrator()
    orch.register(EchoWorker())
    job = orch.run(_run_context(), SnapshotRef("d", "e", "a"),
                   _empty_dataset(), [], None)[0]
    doc = job.to_dict()
    assert doc["status"] == "completed"
    assert doc["result"]["worker_name"] == "echo-worker"


def test_baseline_and_policy_refs_reach_the_worker():
    """Confirms the contract actually threads snapshot/baselines/policy
    through to evaluate() unchanged — not just that *something* runs."""

    received = {}

    class RecordingWorker(EchoWorker):
        name = "recording-worker"

        def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
            received["snapshot"] = snapshot
            received["baselines"] = baselines
            received["policy"] = policy
            received["run_context"] = run_context
            return super().evaluate(snapshot, dataset, baselines, policy, run_context)

    orch = Orchestrator()
    orch.register(RecordingWorker())
    snapshot = SnapshotRef("digest-x", "entity-1", "assess-1")
    baselines = [BaselineRef("peer_cohort", "digest-y")]
    policy = PolicyRef("v1", "digest-z")
    run_context = _run_context()

    orch.run(run_context, snapshot, _empty_dataset(), baselines, policy)

    assert received["snapshot"] is snapshot
    assert received["baselines"] is baselines
    assert received["policy"] is policy
    assert received["run_context"] is run_context
