"""satsa.analysis — the analysis-run engine, observation/finding/job
persistence, and the registry of analytical workers (satsa.analysis.workers).

Phase 4 scope: a ``RunService`` that turns a (entity, assessment) into
an ``AnalysisRun`` record by loading the frozen ``CanonicalDataset``,
invoking every registered worker through the existing ``Orchestrator``
contract, and persisting the resulting observations/findings/jobs in a
single transaction. Subsequent phases add the rest of the worker
catalogue and the trust/peer benchmarking layers; the contract and
persistence path stay exactly as built here.
"""
from __future__ import annotations

from satsa import __version__ as _SATSA_VERSION  # noqa: F401  (re-exported)

ANALYTICS_VERSION = "satsa-analytics/1.0.0"
