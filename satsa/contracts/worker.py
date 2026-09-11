"""The analytical worker contract: ``evaluate(snapshot, baselines, policy,
run_context) -> ObservationBatch``, exactly as specified in
docs/phase1/agent-architecture.md's target design. This module defines the
contract and its typed inputs/outputs only — no detector implements real
analytics yet (that is explicitly later-phase work per Rule 3); ``EchoWorker``
below is a trivial no-op that exists only to prove the contract is callable
end to end through the orchestrator (satsa.contracts.orchestration).
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from satsa.domain.evidence import Finding  # noqa: F401  (kept for type imports)

if TYPE_CHECKING:
    from satsa.store.dataset import CanonicalDataset

BATCH_STATES = ("signal", "no_signal", "insufficient_data", "not_applicable", "error")


@dataclass(frozen=True)
class SnapshotRef:
    """A reference to a frozen, normalized data snapshot — never the data
    itself. A worker resolves this against the (later-phase) snapshot store;
    Phase 2 only defines the shape of the reference."""

    digest: str
    entity_id: str
    assessment_id: str


@dataclass(frozen=True)
class BaselineRef:
    """A reference to an immutable baseline (peer cohort, historical
    period, etc.) a comparative/longitudinal worker may need."""

    name: str
    digest: str


@dataclass(frozen=True)
class PolicyRef:
    """A reference to a versioned policy document (thresholds, escalation
    SLAs, cohort membership rules) — see
    qsmlops.security.policies.loader.DynamicPolicySet, whose hot-reload/
    fail-safe pattern a future PolicyRef resolver should reuse rather than
    reinvent (Part L: identify reusable orchestration interfaces)."""

    version: str
    digest: str


@dataclass
class RunContext:
    """Everything a worker needs to know about *why* it is running, without
    giving it any write/signing authority — workers receive this and a set
    of Refs, never a mutable service handle (Part K / agent-architecture.md:
    "No agent receives signing secrets, mutable registry or unscoped
    database handle").

    ``extras`` is the supervisor's narrow, opt-in channel for handing
    cross-cutting inputs to specific workers without widening the
    ``evaluate`` signature for every worker. It is populated by
    ``RunService.run`` (e.g. ``previous_period`` for the DriftWorker,
    ``cross_entity_aggregate`` for the CrossEntityInsightsWorker) and
    left empty for workers that do not consume it. Workers MUST ignore
    extras they do not understand and MUST abstain (return
    ``insufficient_data``) if a required extra is missing — never
    fabricate a value.
    """

    run_id: str
    entity_id: str
    assessment_id: str
    code_version: str = ""
    created_at: float = field(default_factory=time.time)
    extras: dict = field(default_factory=dict)


@dataclass
class ObservationBatch:
    """A worker's typed output for one run. Mirrors
    satsa.domain.evidence.Observation/Finding but as an in-memory execution
    result rather than a persisted record — a caller decides whether/how to
    persist it (Phase 2 does not wire this automatically, matching the
    equivalent decision in docs/phase2/evidence-persistence.md for the
    qsmlops side)."""

    worker_name: str
    detector_version: str
    scope: dict
    state: str
    findings: list = field(default_factory=list)  # list[Finding]
    evidence_refs: list = field(default_factory=list)
    confidence_components: dict = field(default_factory=dict)
    exclusions: list = field(default_factory=list)
    processing_metrics: dict = field(default_factory=dict)
    error: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.state not in BATCH_STATES:
            errors.append(f"state {self.state!r} must be one of {BATCH_STATES}")
        if self.state == "error" and not self.error:
            errors.append("state='error' requires a non-empty error message")
        # Note: Finding.validate() is *not* recursively called here. The
        # worker's findings arrive with observation_id="" by design — the
        # Observation id is assigned by the persistence layer
        # (satsa.analysis.run.RunService) once the Observation row exists.
        # Calling Finding.validate() here would reject every "signal"
        # finding. The persistence layer runs Finding.validate() again
        # after the observation_id back-fill (see RunService.run).
        return errors

    def to_dict(self) -> dict:
        return {
            "worker_name": self.worker_name, "detector_version": self.detector_version,
            "scope": dict(self.scope), "state": self.state,
            "findings": [f.to_dict() if isinstance(f, Finding) else f for f in self.findings],
            "evidence_refs": list(self.evidence_refs),
            "confidence_components": dict(self.confidence_components),
            "exclusions": list(self.exclusions),
            "processing_metrics": dict(self.processing_metrics), "error": self.error,
        }


class AnalyticalWorker(ABC):
    """Base contract every future detector-owning worker implements.

    Deliberately NOT a subclass of qsmlops.agents.base.BaseAgent: Part L is
    explicit that SAT-SA agents "should be introduced in later phases" as
    their own thing, reusing the *interface pattern* (typed evaluate,
    typed output, no mutation authority) rather than the MLOps class
    hierarchy itself, which carries MLOps-specific assumptions (a single
    ``observe(context: dict)`` call, not scoped snapshot/baseline/policy
    refs) that would leak into SAT-SA if inherited directly.
    """

    name: str = "base-worker"
    version: str = "0.0.0"

    @abstractmethod
    def evaluate(
        self,
        snapshot: SnapshotRef,
        dataset: "CanonicalDataset",
        baselines: list[BaselineRef],
        policy: Optional[PolicyRef],
        run_context: RunContext,
    ) -> ObservationBatch: ...


class EchoWorker(AnalyticalWorker):
    """Trivial no-op worker: always returns ``not_applicable`` with no
    findings. Exists solely to prove the orchestration skeleton
    (satsa.contracts.orchestration.Orchestrator) can register, execute, and
    collect results from a real AnalyticalWorker end to end — it is not,
    and must never become, a stand-in for a real detector."""

    name = "echo-worker"
    version = "0.1.0"

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        return ObservationBatch(
            worker_name=self.name,
            detector_version=self.version,
            scope={"entity_id": run_context.entity_id, "assessment_id": run_context.assessment_id},
            state="not_applicable",
            processing_metrics={
                "note": "echo worker — proves orchestration plumbing only",
                "records": {
                    "alerts": len(dataset.alerts), "cases": len(dataset.cases),
                    "assets": len(dataset.assets),
                },
            },
        )


class CrashingWorker(AnalyticalWorker):
    """Deliberately raises — used only by orchestration tests to verify a
    crashed worker produces a failed Job and withheld conclusions, never a
    crashed orchestrator (Part M: "A crashed worker leaves an error and
    withheld dependent conclusions")."""

    name = "crashing-worker"
    version = "0.1.0"

    def evaluate(self, snapshot, dataset, baselines, policy, run_context) -> ObservationBatch:
        raise RuntimeError("simulated worker crash")
