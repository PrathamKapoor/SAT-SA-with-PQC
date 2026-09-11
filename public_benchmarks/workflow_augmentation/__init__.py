"""Controlled workflow augmentation: generates cases, investigation
steps, escalations, and dispositions on top of source-derived alerts
(from ``public_benchmarks.cicids2017`` or ``public_benchmarks.bots``),
according to the explicit, versioned scenarios declared in
``policy.yaml``.

Every record this package produces is tagged
``provenance_type="derived_synthetic_workflow"`` (see
``public_benchmarks.provenance``) and is NEVER real SOC behavior —
these are controlled validation fixtures, deliberately engineered so
each scenario exercises one (or, for ``multi_signal``, several) named
SAT-SA detector family, the same "generator defines truth
independently of the detector" discipline ``satsa/analysis/synth.py``
already uses for fully synthetic data.
"""
from __future__ import annotations

from public_benchmarks.workflow_augmentation.generator import (
    WorkflowBundle,
    generate_peer_entity_workflow,
    generate_workflow,
    get_scenario,
    list_scenarios,
    load_policy,
)
from public_benchmarks.workflow_augmentation.serialize import (
    provenance_manifest,
    write_submission,
)

__all__ = [
    "WorkflowBundle", "generate_peer_entity_workflow", "generate_workflow",
    "get_scenario", "list_scenarios", "load_policy",
    "provenance_manifest", "write_submission",
]
