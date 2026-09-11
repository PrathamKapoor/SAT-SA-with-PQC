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
evidence_completeness) so the platform exposes all 17 original SAT-SA
supervisory workers — combined with the 9 retained MLOps agents
they reached the 26-agent target the roadmap required at the time.

Phase P25 adds two more workers to the default pipeline
(``workflow_reconstruction``, ``entity_asset_resolution``, taking the
default worker set from 14 to 16) plus three more SAT-SA agents
registered outside the default worker set (evidence_assembly,
meta_audit, and the newly-registered report generator), bringing the
roster to 31 total (9 + 22).

Phase P26 adds one further SAT-SA agent (correlation_fusion, in
``satsa.analysis.correlation`` — not a ``workers/`` module, since it
runs as a pre-scoring step inside ``compute_entity_risk`` rather than
as its own ``AnalyticalWorker`` in the default pipeline), bringing the
roster to 32 total (9 + 23). The default worker set here stays at 16.
See ``docs/AGENT_INVENTORY.md``.
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
from satsa.analysis.workers.entity_asset_resolution import (
    DEFAULT_ENTITY_ASSET_RESOLUTION_POLICY,
    EntityAssetResolutionThresholds,
    EntityAssetResolutionWorker,
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
from satsa.analysis.workers.workflow_reconstruction import (
    DEFAULT_WORKFLOW_RECONSTRUCTION_POLICY,
    WorkflowReconstructionThresholds,
    WorkflowReconstructionWorker,
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
    "WorkflowReconstructionWorker", "WorkflowReconstructionThresholds",
    "DEFAULT_WORKFLOW_RECONSTRUCTION_POLICY",
    "EntityAssetResolutionWorker", "EntityAssetResolutionThresholds",
    "DEFAULT_ENTITY_ASSET_RESOLUTION_POLICY",
]
