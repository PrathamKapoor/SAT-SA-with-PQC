"""SAT-SA supervisor agent registry — the canonical 32-agent roster.

The roadmap identifies 32 agents (grown from 26 in phase P25 by
adding genuine new analytical responsibility, then to 32 in phase P26
by splitting correlation/signal-fusion out from entity risk scoring
as its own distinct agent — see ``docs/AGENT_INVENTORY.md``):

* **9 retained MLOps agents** — the agents the existing
  ``qsmlops`` supervisor orchestrates (Data, Performance, Security,
  QuantumSecurity, RedTeam, Governance, IncidentResponse,
  Optimization, TrainingOptimization).
* **23 SAT-SA supervisory agents** — one per distinct
  analytical responsibility, mapped below to a real worker
  implementation that exists in ``satsa.analysis.workers`` or to
  a real synthesis / risk / review / recommendation engine that
  exists in ``satsa.analysis``.

The 23 SAT-SA agents are:

 1. EntityAssetResolutionAgent — EntityAssetResolutionWorker (Phase P25)
 2. IngestionAgent          — satsa.ingest.service
 3. NormalizationAgent      — satsa.ingest.normalize
 4. ExecutionGapAgent       — analytical worker (synthesises the
                                six SIH-EG detectors into one
                                supervisory observation stream)
 5. NegativeSpaceAgent      — NegativeSpaceWorker
 6. WorkflowReconstructionAgent — WorkflowReconstructionWorker (Phase P25)
 7. AnomalyAgent            — AnomalyWorker
 8. PeerBenchmarkAgent      — PeerBenchmarkWorker
 9. CoverageGapAgent        — CoverageGapWorker (Phase P12)
10. DriftAgent              — DriftWorker (Phase P12)
11. CrossEntityInsightsAgent — CrossEntityInsightsWorker (Phase P12)
12. CaseSimilarityAgent     — CaseSimilarityWorker (Phase P12)
13. EvidenceCompletenessAgent — EvidenceCompletenessWorker (Phase P12)
14. CorrelationSignalFusionAgent — satsa.analysis.correlation (Phase P26)
15. FusionAgent (Entity Risk Scoring) — RiskAggregator (satsa.analysis.risk)
16. PrioritizationAgent     — satsa.analysis.prioritize
17. RecommendationAgent     — satsa.analysis.recommend
18. ReviewWorkflowAgent     — satsa.analysis.review
19. TrustProvenanceAgent    — satsa.analysis.trust
20. EvidenceAssemblyAgent   — satsa.analysis.evidence_assembly (Phase P25)
21. MetaAuditAgent          — satsa.analysis.meta_audit (Phase P25)
22. ReportGenerationAgent   — satsa.analysis.report (Phase P25, newly registered)
23. ValidationAgent         — satsa.analysis.validate (Phase P13)

This module does not implement the analytical logic itself — it
only registers the agents and exposes their declared inputs /
outputs / evidence / version so the UI's agent explorer and the
supervisor engine can address them uniformly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class AgentSpec:
    """Static declaration of one agent. The supervisor engine uses
    this to route ``observe(context)`` calls and to render the
    agent-explorer UI without having to instantiate the underlying
    worker on every page load."""

    agent_id: str
    name: str
    family: str   # "mlops" or "satsa"
    purpose: str
    inputs: tuple = ()
    outputs: tuple = ()
    evidence_types: tuple = ()
    implementation_ref: str = ""
    version: str = "0.1.0"
    status: str = "implemented"
    notes: str = ""


# ---------------------------------------------------------------------------
# 9 retained MLOps agents (the agents already implemented in qsmlops/)
# ---------------------------------------------------------------------------

RETAINED_MLOPS_AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        agent_id="mlops.data",
        name="Data Agent",
        family="mlops",
        purpose="Dataset integrity, preprocessing, artifact hashing",
        inputs=("artifact_store", "bom", "dataset_ref", "preprocessing_ref"),
        outputs=("integrity_finding", "missing_data_finding"),
        evidence_types=("artifact_digest", "bom_entry"),
        implementation_ref="qsmlops.agents.data_agent",
    ),
    AgentSpec(
        agent_id="mlops.performance",
        name="Performance Agent",
        family="mlops",
        purpose="ML metric evaluation against rolling baseline",
        inputs=("metrics", "rolling_window", "drift_report"),
        outputs=("performance_finding", "retrain_recommendation"),
        evidence_types=("metric_value", "drift_score"),
        implementation_ref="qsmlops.agents.performance_agent",
    ),
    AgentSpec(
        agent_id="mlops.security",
        name="Security Agent",
        family="mlops",
        purpose="Dependency CVE scanning, artifact integrity",
        inputs=("bom", "artifacts", "advisory_map"),
        outputs=("vulnerability_finding", "block_finding"),
        evidence_types=("advisory_id", "artifact_digest"),
        implementation_ref="qsmlops.agents.security_agent",
    ),
    AgentSpec(
        agent_id="mlops.quantum",
        name="Quantum Security Agent",
        family="mlops",
        purpose="Cryptographic posture (signatures, suites, key lifecycle)",
        inputs=("passport", "keystore", "agility_policy", "age_policy"),
        outputs=("signature_finding", "quarantine_finding"),
        evidence_types=("passport_signature", "key_record"),
        implementation_ref="qsmlops.agents.quantum_agent",
    ),
    AgentSpec(
        agent_id="mlops.redteam",
        name="Red Team Agent",
        family="mlops",
        purpose="Byte-tamper tripwire, provenance, regression perturbation",
        inputs=("artifacts", "passport", "dataset_callback"),
        outputs=("tamper_finding", "regression_finding"),
        evidence_types=("byte_diff", "perturbation_score"),
        implementation_ref="qsmlops.agents.redteam",
    ),
    AgentSpec(
        agent_id="mlops.training_optimization",
        name="Training Optimization Agent",
        family="mlops",
        purpose="Sample / feature / seed adequacy heuristics",
        inputs=("training_samples", "features", "drift_hints"),
        outputs=("optimization_finding", "monitor_recommendation"),
        evidence_types=("sample_count", "feature_count"),
        implementation_ref="qsmlops.agents.training_optimization_agent",
    ),
    AgentSpec(
        agent_id="mlops.incident_response",
        name="Incident Response Agent",
        family="mlops",
        purpose="Model-state denial/critical/repetition analysis",
        inputs=("ledger_tail", "model_state", "drift_status"),
        outputs=("incident_finding", "escalation_advice"),
        evidence_types=("ledger_event", "model_state"),
        implementation_ref="qsmlops.agents.incident_response_agent",
    ),
    AgentSpec(
        agent_id="mlops.governance",
        name="Governance Agent",
        family="mlops",
        purpose="Model-state compliance and registry hygiene",
        inputs=("registry", "passport", "bom", "trust_metadata"),
        outputs=("governance_finding", "review_finding"),
        evidence_types=("registry_record", "passport_record"),
        implementation_ref="qsmlops.agents.governance_agent",
    ),
    AgentSpec(
        agent_id="mlops.optimization",
        name="Optimization Agent",
        family="mlops",
        purpose="Storage/registry hygiene, stale-version detection",
        inputs=("registry", "artifacts"),
        outputs=("stale_version_finding", "registry_finding"),
        evidence_types=("registry_record", "artifact_age"),
        implementation_ref="qsmlops.agents.optimization_agent",
    ),
)


# ---------------------------------------------------------------------------
# 17 new SAT-SA supervisory agents
# ---------------------------------------------------------------------------

SATSA_AGENTS: tuple[AgentSpec, ...] = (
    AgentSpec(
        agent_id="satsa.entity_asset_resolution",
        name="Entity & Asset Resolution Agent",
        family="satsa",
        purpose="Maintains a cross-period asset-inventory view per entity; "
                "flags assets present in the prior assessment that vanished "
                "from the current one (decommission vs. silent reporting gap)",
        inputs=("canonical_dataset", "previous_period_assets"),
        outputs=("vanished_asset_finding_set",),
        evidence_types=("asset_native_id",),
        implementation_ref="satsa.analysis.workers.entity_asset_resolution",
    ),
    AgentSpec(
        agent_id="satsa.ingest",
        name="Ingestion Agent",
        family="satsa",
        purpose="Parse CSE submissions (CSV/JSON/JSONL/SQLite), "
                "canonical normalization, atomic persistence, source provenance",
        inputs=("submission_root", "source_system"),
        outputs=("submission_record", "source_record_set", "snapshot"),
        evidence_types=("file_digest", "source_locator"),
        implementation_ref="satsa.ingest.service.IngestionService",
    ),
    AgentSpec(
        agent_id="satsa.normalize",
        name="Normalization Agent",
        family="satsa",
        purpose="Resolve cross-references (alert → case → step → escalation), "
                "emit a frozen CanonicalDataset for downstream workers",
        inputs=("submission_records", "category_mapping"),
        outputs=("canonical_dataset", "coverage_report"),
        evidence_types=("canonical_id", "coverage_field"),
        implementation_ref="satsa.ingest.normalize",
    ),
    AgentSpec(
        agent_id="satsa.execution_gap",
        name="Execution Gap Agent",
        family="satsa",
        purpose="Six SIH-EG detectors — fast closure, ack-without-investigation, "
                "critical-without-escalation, repeated investigations, "
                "recurring-without-remediation, metric gaming",
        inputs=("canonical_dataset", "policy_ref"),
        outputs=("execution_gap_finding_set",),
        evidence_types=("alert_id", "case_id", "duration", "policy_clause"),
        implementation_ref="satsa.analysis.workers (6 workers)",
    ),
    AgentSpec(
        agent_id="satsa.negative_space",
        name="Negative Space Agent",
        family="satsa",
        purpose="Detect absence of expected evidence — missing file, "
                "missing investigation, missing escalation, missing "
                "disposition, missing monitoring, unexpectedly low activity",
        inputs=("canonical_dataset", "expectation_graph"),
        outputs=("absence_finding_set",),
        evidence_types=("expected_evidence_id", "coverage_gap"),
        implementation_ref="satsa.analysis.workers.negative_space",
    ),
    AgentSpec(
        agent_id="satsa.workflow_reconstruction",
        name="Workflow Reconstruction Agent",
        family="satsa",
        purpose="Reconstructs the ordered event timeline per case from raw "
                "timestamped records and flags temporal-sequence violations: "
                "escalation after closure, disposition before investigation, "
                "declared-sequence-vs-chronology mismatch",
        inputs=("canonical_dataset",),
        outputs=("workflow_sequence_finding_set",),
        evidence_types=("case_id", "escalation_id", "disposition_id", "step_id"),
        implementation_ref="satsa.analysis.workers.workflow_reconstruction",
    ),
    AgentSpec(
        agent_id="satsa.anomaly",
        name="Anomaly Agent",
        family="satsa",
        purpose="Robust statistical anomalies (median/MAD/percentile) on "
                "per-entity rate distributions",
        inputs=("canonical_dataset",),
        outputs=("anomaly_finding_set",),
        evidence_types=("rate", "baseline", "effect_size"),
        implementation_ref="satsa.analysis.workers.anomaly",
    ),
    AgentSpec(
        agent_id="satsa.peer_benchmark",
        name="Peer Benchmark Agent",
        family="satsa",
        purpose="Cohort-based robust baseline + 7 peer metrics with "
                "trimmed-mean / MAD confidence and limitations",
        inputs=("canonical_dataset", "cohort_manifest"),
        outputs=("peer_finding_set",),
        evidence_types=("cohort_id", "metric_value", "baseline", "effect"),
        implementation_ref="satsa.analysis.workers.peer_benchmark",
    ),
    AgentSpec(
        agent_id="satsa.coverage_gap",
        name="Coverage Gap Agent",
        family="satsa",
        purpose="SIH-EG-05 / SIH-NS-06 — controls deployed but not "
                "monitored; monitoring blind spots vs expected intervals",
        inputs=("canonical_dataset", "control_expectation_graph"),
        outputs=("coverage_gap_finding_set",),
        evidence_types=("asset_id", "control_id", "expected_interval"),
        implementation_ref="satsa.analysis.workers.coverage_gap",
    ),
    AgentSpec(
        agent_id="satsa.drift",
        name="Drift Agent",
        family="satsa",
        purpose="Longitudinal KPI drift with matched-period baselines "
                "and robust change-point detection (cross-period intelligence)",
        inputs=("canonical_dataset", "previous_run_snapshot"),
        outputs=("drift_finding_set",),
        evidence_types=("period", "kpi", "change_point", "effect"),
        implementation_ref="satsa.analysis.workers.drift",
    ),
    AgentSpec(
        agent_id="satsa.cross_entity_insights",
        name="Cross-Entity Insights Agent",
        family="satsa",
        purpose="SIH-ADD-05 — common weaknesses / repeated patterns / "
                "outliers across the entity roster",
        inputs=("entity_findings_aggregate", "cohort_manifest"),
        outputs=("cross_entity_insight_set",),
        evidence_types=("finding_pattern_id", "prevalence", "effect"),
        implementation_ref="satsa.analysis.workers.cross_entity_insights",
    ),
    AgentSpec(
        agent_id="satsa.case_similarity",
        name="Case Similarity Agent",
        family="satsa",
        purpose="SIH-ADD-03 — deterministic edit-distance on investigation "
                "sequences; flags template / suspiciously identical patterns",
        inputs=("canonical_dataset",),
        outputs=("similarity_finding_set",),
        evidence_types=("case_id", "similar_case_id", "distance"),
        implementation_ref="satsa.analysis.workers.case_similarity",
    ),
    AgentSpec(
        agent_id="satsa.evidence_completeness",
        name="Evidence Completeness Agent",
        family="satsa",
        purpose="SIH-ADD-06 — counts / linkage / field coverage / temporal "
                "coverage / manifest reconciliation",
        inputs=("canonical_dataset", "manifest"),
        outputs=("completeness_finding_set",),
        evidence_types=("coverage_field", "missing_count"),
        implementation_ref="satsa.analysis.workers.evidence_completeness",
    ),
    AgentSpec(
        agent_id="satsa.correlation_fusion",
        name="Correlation & Signal Fusion Agent",
        family="satsa",
        purpose="Cross-finding corroboration: clusters signal findings "
                "sharing a scoped subject and flags cross-detector-"
                "family corroboration, ahead of and independent from "
                "risk scoring (Phase P26)",
        inputs=("entity_finding_set",),
        outputs=("correlation_clusters",),
        evidence_types=("subject", "rule_families", "corroborated"),
        implementation_ref="satsa.analysis.correlation.correlate_findings",
    ),
    AgentSpec(
        agent_id="satsa.fusion",
        name="Entity Risk Scoring Agent",
        family="satsa",
        purpose="SIH-AN-01..07 — risk fusion: 7-dimension decomposable "
                "entity risk profile, explainable aggregation, "
                "consuming the correlation clusters from "
                "satsa.correlation_fusion as supporting evidence",
        inputs=("entity_finding_set", "policy_ref"),
        outputs=("entity_risk_profile",),
        evidence_types=("dimension", "score", "rationale"),
        implementation_ref="satsa.analysis.risk.compute_entity_risk",
    ),
    AgentSpec(
        agent_id="satsa.prioritization",
        name="Prioritization Agent",
        family="satsa",
        purpose="SIH-AN-08 — explainable entity + finding priority "
                "(lexicographic: high-impact → evidence-backed → "
                "materially-affected → repeated → aging)",
        inputs=("entity_risk_profiles", "entity_finding_set"),
        outputs=("entity_priority", "finding_priority"),
        evidence_types=("priority_score", "rationale"),
        implementation_ref="satsa.analysis.prioritize",
    ),
    AgentSpec(
        agent_id="satsa.recommendation",
        name="Recommendation Agent",
        family="satsa",
        purpose="SAT-SA decision vocabulary — bounded, evidence-backed "
                "human-action hints (INSPECT_INVESTIGATION, "
                "REQUEST_EVIDENCE, REVIEW_ESCALATION, REVIEW_MONITORING, "
                "REVIEW_CONTROL, COMPARE_PEERS, REVIEW_TREND)",
        inputs=("finding", "context"),
        outputs=("recommendation",),
        evidence_types=("recommendation_action", "reason"),
        implementation_ref="satsa.analysis.recommend.recommend",
    ),
    AgentSpec(
        agent_id="satsa.review_workflow",
        name="Review Workflow Agent",
        family="satsa",
        purpose="SIH-ADD-08 — human review capture (confirm / reject / "
                "defer / escalate / annotate); append-only decision audit "
                "bound to the finding's content digest at decision time",
        inputs=("finding", "principal", "action", "rationale"),
        outputs=("review_record",),
        evidence_types=("finding_content_digest", "previous_revision_id"),
        implementation_ref="satsa.analysis.review.ReviewService",
    ),
    AgentSpec(
        agent_id="satsa.trust_provenance",
        name="Trust-Provenance Agent",
        family="satsa",
        purpose="PQC (ML-DSA-65) sign + verify every run and every "
                "finding; hash-chain evidence ledger; deterministic "
                "content digests; integrity of source → record → "
                "observation → finding → risk → recommendation → decision",
        inputs=("run", "finding_set", "key_dir"),
        outputs=("trust_receipt_set", "verification_report"),
        evidence_types=("signature", "content_digest", "ledger_event"),
        implementation_ref="satsa.analysis.trust",
    ),
    AgentSpec(
        agent_id="satsa.evidence_assembly",
        name="Evidence & Explainability Assembly Agent",
        family="satsa",
        purpose="Assembles the uniform WHAT/WHY/EVIDENCE/CONFIDENCE/"
                "LIMITATIONS/RECOMMENDATION decomposition every finding "
                "renders through, plus drill-down linking — a single "
                "source of truth the UI now actually calls, replacing "
                "logic that was duplicated inline",
        inputs=("finding", "evidence_records", "observation"),
        outputs=("explanation_bundle",),
        evidence_types=("finding_id", "source_record_id"),
        implementation_ref="satsa.analysis.evidence_assembly.assemble_explanation",
    ),
    AgentSpec(
        agent_id="satsa.meta_audit",
        name="Supervisory Audit & Compliance (Meta-Audit) Agent",
        family="satsa",
        purpose="Sweeps every run, every signal finding, and every review "
                "decision in the database and verifies trust-receipt and "
                "provenance-binding coverage — a database-wide compliance "
                "check, not the single-run verify_run() check",
        inputs=("satsa_runs", "satsa_findings", "satsa_review_decisions"),
        outputs=("meta_audit_report",),
        evidence_types=("run_id", "finding_id", "review_id"),
        implementation_ref="satsa.analysis.meta_audit.run_meta_audit",
    ),
    AgentSpec(
        agent_id="satsa.report_generation",
        name="Supervisory Report Generation Agent",
        family="satsa",
        purpose="Assembles a supervisory report (entity risk decomposition, "
                "findings, evidence, drill-down links) as printable/exportable "
                "HTML — was real, working code that had never been formally "
                "registered as one of the roster's agents",
        inputs=("entity", "assessments", "risk_profile", "finding_set"),
        outputs=("html_report",),
        evidence_types=("finding_id", "assessment_id"),
        implementation_ref="satsa.analysis.report.render_report",
    ),
    AgentSpec(
        agent_id="satsa.validation",
        name="Validation Agent",
        family="satsa",
        purpose="Per-layer + composition validation; expert labels; "
                "synthetic ground truth; performance benchmark; "
                "offline guarantee; extended in Phase P26 with a "
                "governed threshold-calibration workflow (propose -> "
                "test against labeled data -> supervisor approval -> "
                "versioned deployment, satsa.analysis.calibration)",
        inputs=("run", "ground_truth", "expert_labels",
                "calibration_proposal"),
        outputs=("layer_metrics", "composition_metrics",
                 "calibration_decision"),
        evidence_types=("layer", "metric", "ground_truth_id",
                        "calibration_proposal_id"),
        implementation_ref="satsa.analysis.validate, satsa.analysis.calibration",
    ),
)


# 9 + 17 = 26 — the canonical roster the roadmap requires.
AGENT_REGISTRY: dict[str, AgentSpec] = {a.agent_id: a for a in
                                        (*RETAINED_MLOPS_AGENTS, *SATSA_AGENTS)}


def list_agents(*, family: Optional[str] = None) -> list[AgentSpec]:
    """Return every registered agent spec, optionally filtered by
    family ("mlops" or "satsa"). The order is the canonical one
    declared above (retained MLOps first, then SAT-SA in the
    order the roadmap introduces them)."""
    if family is None:
        return [*RETAINED_MLOPS_AGENTS, *SATSA_AGENTS]
    if family == "mlops":
        return [*RETAINED_MLOPS_AGENTS]
    if family == "satsa":
        return [*SATSA_AGENTS]
    raise ValueError(f"unknown family {family!r}; expected 'mlops' or 'satsa'")


def get_agent(agent_id: str) -> AgentSpec:
    """Look up an agent spec by id. Raises KeyError for unknown ids
    so callers can tell apart 'agent not registered' from 'agent
    registered but missing spec fields'."""
    return AGENT_REGISTRY[agent_id]