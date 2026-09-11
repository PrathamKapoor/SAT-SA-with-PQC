"""The SupervisorContext — what every SAT-SA agent receives when
called via ``observe(context)``.

The roadmap specifies the common contract: every observation
must support a structured shape with

* agent_id
* agent_version
* observation_type
* severity
* confidence
* scope
* subjects
* evidence_refs
* rationale
* statistics
* threshold
* limitations
* recommended_action
* analysis_period
* provenance

This module provides a typed container that wraps a snapshot ref,
a baseline ref, a policy ref, and the run context — exactly the
inputs the worker contract already accepts. The supervisor engine
threads a ``SupervisorContext`` through every ``observe()`` call.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from satsa.contracts.worker import (
    BaselineRef,
    PolicyRef,
    RunContext,
    SnapshotRef,
)
from satsa.store.dataset import CanonicalDataset


@dataclass
class SupervisorContext:
    """What every SAT-SA agent observes over.

    The supervisor engine never gives an agent the raw database
    handle, signing secrets, or any mutating service. It gives
    the agent a typed snapshot, optional baseline refs, an
    optional policy ref, and the run context — and lets the
    agent emit an Observation (in the worker contract sense).
    """

    snapshot: SnapshotRef
    dataset: "CanonicalDataset"
    run_context: RunContext
    baselines: list[BaselineRef] = field(default_factory=list)
    policy: Optional[PolicyRef] = None
    # Optional cross-scope inputs the supervisor hands to specific
    # agents only when needed (previous period snapshot for drift,
    # full entity finding aggregate for cross-entity insights, etc.).
    extras: dict = field(default_factory=dict)

    @property
    def entity_id(self) -> str:
        return self.run_context.entity_id

    @property
    def assessment_id(self) -> str:
        return self.run_context.assessment_id