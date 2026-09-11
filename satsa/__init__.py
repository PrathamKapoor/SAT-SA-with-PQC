"""SAT-SA: Supervisory Analytics Tool for SOC Assessment.

A new bounded context, introduced in Phase 2, that sits beside the existing
``qsmlops`` MLOps trust platform and reuses its foundation layer (crypto,
evidence, logging, errors) without repurposing its MLOps-specific domain
logic (agents, registry, supervisor). See
docs/phase1/target-architecture.md for the layering this package follows,
and docs/phase2/domain-foundation.md for what is and is not implemented yet.

Phase 2 scope, explicitly: domain types and validation (``satsa.domain``)
and a worker/orchestration contract skeleton (``satsa.contracts``) — no
ingestion parsing, no detectors, no persistence, no API, no UI. Those are
later-phase work; building them now would be exactly the "premature
analytics" this phase's rules warn against.

Phase 3 adds the periodic CSE submission ingestion path
(``satsa.ingest`` + ``satsa.store`` + SatsaService facade) — CSV/JSON
parsing, canonical normalization, cross-reference resolution, atomic
persistence, source-record provenance and a frozen per-scope
``CanonicalDataset`` that subsequent analytics phases read.
"""
from __future__ import annotations

__version__ = "0.16.0-phase52-ui"
