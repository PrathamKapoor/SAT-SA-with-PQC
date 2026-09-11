"""SAT-SA supervisor package — the generalized Observe → Reason → Act →
Verify → Learn orchestration engine.

The roadmap explicitly requires a single supervisor engine with two
pluggable decision vocabularies:

* **MLOps vocabulary** — the decisions the existing ``qsmlops.supervisor``
  already emits (``ACCEPT``, ``DEPLOY``, ``RETRAIN``, ``QUARANTINE``,
  ``ROTATE_KEYS``, ``BLOCK_DEPLOYMENT``, ``ESCALATE``).
* **SAT-SA vocabulary** — the decisions a supervisory analyst
  interface uses (``SURFACE``, ``INSPECT``, ``REQUEST_EVIDENCE``,
  ``ESCALATE_FOR_REVIEW``, ``DEFER``, ``ACCEPT``, ``CLOSE_REVIEW``).

Both pluggable vocabularies drive the same five-stage loop:

    OBSERVE  →  REASON  →  ACT  →  VERIFY  →  LEARN

This module also owns the SAT-SA agent registry: 17 supervisory
analytics agents, each implementing the common
``observe(context) → Observation`` contract from the roadmap. The
agents are individually constructed (not invented) — every one
maps to a real analytical responsibility and to a real worker
implementation that already exists in ``satsa.analysis.workers``.
"""
from __future__ import annotations

from satsa.supervisor.agents import (
    AGENT_REGISTRY,
    SATSA_AGENTS,
    RETAINED_MLOPS_AGENTS,
    list_agents,
    get_agent,
)
from satsa.supervisor.engine import (
    SupervisorEngine,
    Decision,
    DecisionContext,
    SATSA_VOCABULARY,
    MLOPS_VOCABULARY,
    observe,
    reason,
    act,
    verify,
    learn,
)
from satsa.supervisor.context import SupervisorContext

__all__ = [
    "AGENT_REGISTRY",
    "SATSA_AGENTS",
    "RETAINED_MLOPS_AGENTS",
    "list_agents",
    "get_agent",
    "SupervisorEngine",
    "Decision",
    "DecisionContext",
    "SATSA_VOCABULARY",
    "MLOPS_VOCABULARY",
    "SupervisorContext",
]