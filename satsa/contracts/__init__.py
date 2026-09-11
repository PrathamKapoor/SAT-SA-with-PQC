"""SAT-SA worker/orchestration contracts (Part K). See
docs/phase2/orchestration-foundation.md. This is the plumbing future
analytics workers plug into — it contains no detector logic itself, only
``EchoWorker``, a trivial no-op implementation that exists solely to prove
the Job/Processor/Result skeleton actually executes end to end."""
from __future__ import annotations

from satsa.contracts.orchestration import Job, Orchestrator
from satsa.contracts.worker import (
    AnalyticalWorker,
    BaselineRef,
    EchoWorker,
    ObservationBatch,
    PolicyRef,
    RunContext,
    SnapshotRef,
)

__all__ = [
    "AnalyticalWorker", "SnapshotRef", "BaselineRef", "PolicyRef", "RunContext",
    "ObservationBatch", "EchoWorker", "Job", "Orchestrator",
]
