"""Analysis Run -> Job -> Processor -> Result skeleton (Part K).

Deliberately a plain in-process orchestrator, not a distributed job queue —
Part K is explicit: "Do not introduce a heavy distributed system unless the
repository genuinely requires it," and nothing about a single-installation,
air-gapped supervisory tool does. A future phase may swap this for a
persistent job table (reusing the transactional pattern already built in
qsmlops.database.evidence_store) without changing the AnalyticalWorker
contract itself.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from satsa.contracts.worker import (
    AnalyticalWorker,
    BaselineRef,
    ObservationBatch,
    PolicyRef,
    RunContext,
    SnapshotRef,
)
from satsa.domain.base import new_id

if TYPE_CHECKING:
    from satsa.store.dataset import CanonicalDataset

JOB_STATUSES = ("pending", "running", "completed", "failed")


@dataclass
class Job:
    """One worker's execution record within an AnalysisRun. A crashed or
    invalid-output worker produces a 'failed' Job with its result withheld
    (``result`` stays None) — it never contaminates other workers' Jobs
    (Part M: "A crashed worker leaves an error and withheld dependent
    conclusions"; Part K's "Result" stage)."""

    run_id: str
    worker_name: str
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: str = ""
    result: Optional[ObservationBatch] = None
    id: str = field(default_factory=lambda: new_id("job"))

    def to_dict(self) -> dict:
        return {
            "id": self.id, "run_id": self.run_id, "worker_name": self.worker_name,
            "status": self.status, "created_at": self.created_at,
            "started_at": self.started_at, "finished_at": self.finished_at,
            "error": self.error, "result": self.result.to_dict() if self.result else None,
        }


class Orchestrator:
    """Registers AnalyticalWorkers and executes all of them for one run,
    isolating each worker's failure from the others and from the caller."""

    def __init__(self) -> None:
        self._workers: dict[str, AnalyticalWorker] = {}

    def register(self, worker: AnalyticalWorker) -> None:
        if worker.name in self._workers:
            raise ValueError(f"worker {worker.name!r} is already registered")
        self._workers[worker.name] = worker

    @property
    def registered_workers(self) -> list[str]:
        return sorted(self._workers)

    def run(
        self,
        run_context: RunContext,
        snapshot: SnapshotRef,
        dataset: "CanonicalDataset",
        baselines: list[BaselineRef],
        policy: Optional[PolicyRef],
    ) -> list[Job]:
        """Execute every registered worker for this run. Returns one Job per
        worker, in registration order, regardless of how many fail — a
        caller inspects each Job's status rather than the run aborting on
        the first failure (no dependent conclusion is silently produced
        from a failed worker's absence: the Job simply records 'failed',
        it never substitutes a default/empty ObservationBatch)."""
        jobs: list[Job] = []
        for name in self.registered_workers:
            worker = self._workers[name]
            job = Job(run_id=run_context.run_id, worker_name=name)
            job.status = "running"
            job.started_at = time.time()
            try:
                batch = worker.evaluate(snapshot, dataset, baselines, policy, run_context)
                errors = batch.validate()
                if errors:
                    job.status = "failed"
                    job.error = "invalid ObservationBatch: " + "; ".join(errors)
                else:
                    job.status = "completed"
                    job.result = batch
            except Exception as exc:  # a crashing worker must not crash the run
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
            job.finished_at = time.time()
            jobs.append(job)
        return jobs
