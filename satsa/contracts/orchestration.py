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
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
    started_at: float | None = None
    finished_at: float | None = None
    error: str = ""
    retryable: bool = False
    result: ObservationBatch | None = None
    id: str = field(default_factory=lambda: new_id("job"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "worker_name": self.worker_name,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "result": self.result.to_dict() if self.result else None,
            "retryable": self.retryable,
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
        dataset: CanonicalDataset,
        baselines: list[BaselineRef],
        policy: PolicyRef | None,
        *,
        before_worker: Callable[[str], None] | None = None,
        after_worker: Callable[[Job], None] | None = None,
        skip_workers: Iterable[str] = (),
        is_retryable_exception: Callable[[Exception], bool] | None = None,
    ) -> list[Job]:
        """Execute every registered worker for this run. Returns one Job per
        worker, in registration order, regardless of how many fail — a
        caller inspects each Job's status rather than the run aborting on
        the first failure (no dependent conclusion is silently produced
        from a failed worker's absence: the Job simply records 'failed',
        it never substitutes a default/empty ObservationBatch)."""
        jobs: list[Job] = []
        skipped = set(skip_workers)
        for name in self.registered_workers:
            if name in skipped:
                continue
            # The callback may stop the run at a safe worker boundary. It is
            # deliberately outside the worker exception handler so cancellation
            # and lease loss are not misreported as detector failures.
            if before_worker is not None:
                before_worker(name)
            worker = self._workers[name]
            job = Job(run_id=run_context.run_id, worker_name=name)
            job.status = "running"
            job.started_at = time.time()
            try:
                batch = worker.evaluate(
                    snapshot, dataset, baselines, policy, run_context
                )
                errors = batch.validate()
                if errors:
                    job.status = "failed"
                    job.error = "invalid ObservationBatch: " + "; ".join(errors)
                else:
                    job.status = "completed"
                    job.result = batch
            except Exception as exc:  # noqa: BLE001 - isolate analytical worker failures
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
                job.retryable = bool(
                    is_retryable_exception and is_retryable_exception(exc)
                )
            job.finished_at = time.time()
            # Persistence is owned by the execution coordinator, not by a
            # worker. A persistence exception must abort the run so the lease
            # can retry instead of recording a false success.
            if after_worker is not None:
                after_worker(job)
            jobs.append(job)
        return jobs
