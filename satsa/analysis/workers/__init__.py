"""satsa.analysis.workers — analytical worker implementations for the
supervisory analytics run. Each worker is an ``AnalyticalWorker`` that
reads the frozen ``CanonicalDataset`` and emits ``ObservationBatch``-es
of typed ``Finding``-s; the rest of the run pipeline is shared.

Phase 4 ships ``fast_closure`` (the first execution-gap detector).
Subsequent phases add the rest of the execution-gap, negative-space,
anomaly, peer and prioritisation catalogue here, each as its own
module so failures are isolated and reruns only re-execute the changed
worker (not the whole run).

Phases P12–P13 add the eight remaining SAT-SA supervisory agents
(coverage_gap, drift, cross_entity_insights, case_similarity,
evidence_completeness) so the platform exposes all 17 SAT-SA
supervisory workers — combined with the 9 retained MLOps agents
they reach the 26-agent target the roadmap requires.
"""
from __future__ import annotations

from satsa.analysis.workers.ack_without_investigation import (
    AckWithoutInvestigationThresholds,
    AckWithoutInvestigationWorker,
    DEFAULT_ACK_WITHOUT_INVESTIGATION_POLICY,
)
from satsa.analysis.workers.anomaly import (
    DEFAULT_ANOMALY_POLICY,
    AnomalyThresholds,
    AnomalyWorker,
)
from satsa.analysis.workers.case_similarity import (
    DEFAULT_CASE_SIMILARITY_POLICY,
    CaseSimilarityThresholds,
    CaseSimilarityWorker,
)
from satsa.analysis.workers.coverage_gap import (
    CoverageGapThresholds,
    CoverageGapWorker,
    DEFAULT_COVERAGE_GAP_POLICY,
)
from satsa.analysis.workers.critical_without_escalation import (
    CriticalWithoutEscalationThresholds,
    CriticalWithoutEscalationWorker,
    DEFAULT_CRITICAL_WITHOUT_ESCALATION_POLICY,
)
from satsa.analysis.workers.cross_entity_insights import (
    CrossEntityInsightsThresholds,
    CrossEntityInsightsWorker,
    DEFAULT_CROSS_ENTITY_INSIGHTS_POLICY,
)
from satsa.analysis.workers.drift import (
    DEFAULT_DRIFT_POLICY,
    DriftThresholds,
    DriftWorker,
)
from satsa.analysis.workers.evidence_completeness import (
    DEFAULT_EVIDENCE_COMPLETENESS_POLICY,
    EvidenceCompletenessThresholds,
    EvidenceCompletenessWorker,
)
from satsa.analysis.workers.fast_closure import (
    DEFAULT_FAST_CLOSURE_POLICY,
    FastClosureThresholds,
    FastClosureWorker,
)
from satsa.analysis.workers.metric_gaming import (
    DEFAULT_METRIC_GAMING_POLICY,
    MetricGamingThresholds,
    MetricGamingWorker,
)
from satsa.analysis.workers.negative_space import (
    DEFAULT_NEGATIVE_SPACE_POLICY,
    NegativeSpaceThresholds,
    NegativeSpaceWorker,
)
from satsa.analysis.workers.peer_benchmark import (
    DEFAULT_PEER_BENCHMARK_POLICY,
    PeerBaseline,
    PeerBenchmarkThresholds,
    PeerBenchmarkWorker,
    attach_baseline,
    compute_peer_baseline,
)
from satsa.analysis.workers.recurring_without_remediation import (
    DEFAULT_RECURRING_WITHOUT_REMEDIATION_POLICY,
    RecurringWithoutRemediationThresholds,
    RecurringWithoutRemediationWorker,
)
from satsa.analysis.workers.repeated_investigation_pattern import (
    DEFAULT_REPEATED_INVESTIGATION_POLICY,
    RepeatedInvestigationThresholds,
    RepeatedInvestigationWorker,
)

__all__ = [
    "FastClosureWorker", "FastClosureThresholds", "DEFAULT_FAST_CLOSURE_POLICY",
    "AckWithoutInvestigationWorker", "AckWithoutInvestigationThresholds",
    "DEFAULT_ACK_WITHOUT_INVESTIGATION_POLICY",
    "CriticalWithoutEscalationWorker", "CriticalWithoutEscalationThresholds",
    "DEFAULT_CRITICAL_WITHOUT_ESCALATION_POLICY",
    "RepeatedInvestigationWorker", "RepeatedInvestigationThresholds",
    "DEFAULT_REPEATED_INVESTIGATION_POLICY",
    "RecurringWithoutRemediationWorker", "RecurringWithoutRemediationThresholds",
    "DEFAULT_RECURRING_WITHOUT_REMEDIATION_POLICY",
    "MetricGamingWorker", "MetricGamingThresholds", "DEFAULT_METRIC_GAMING_POLICY",
    "NegativeSpaceWorker", "NegativeSpaceThresholds", "DEFAULT_NEGATIVE_SPACE_POLICY",
    "AnomalyWorker", "AnomalyThresholds", "DEFAULT_ANOMALY_POLICY",
    "PeerBenchmarkWorker", "PeerBenchmarkThresholds", "DEFAULT_PEER_BENCHMARK_POLICY",
    "PeerBaseline", "compute_peer_baseline", "attach_baseline",
    "CoverageGapWorker", "CoverageGapThresholds", "DEFAULT_COVERAGE_GAP_POLICY",
    "DriftWorker", "DriftThresholds", "DEFAULT_DRIFT_POLICY",
    "CrossEntityInsightsWorker", "CrossEntityInsightsThresholds",
    "DEFAULT_CROSS_ENTITY_INSIGHTS_POLICY",
    "CaseSimilarityWorker", "CaseSimilarityThresholds",
    "DEFAULT_CASE_SIMILARITY_POLICY",
    "EvidenceCompletenessWorker", "EvidenceCompletenessThresholds",
    "DEFAULT_EVIDENCE_COMPLETENESS_POLICY",
]
