/**
 * Static description of the registered SAT-SA agents (satsa/supervisor/agents.py):
 * which default analytical workers each analytical agent groups, and the
 * supervision layer of each agent. SAT-SA agents are deterministic analytical
 * components and pipeline services, not language models. The hosted API
 * serves no agent registry; live activity is read from a run's worker steps.
 */
export const AGENT_WORKERS: Record<string, string[]> = {
  "satsa.execution_gap": [
    "fast-closure",
    "ack-without-investigation",
    "critical-without-escalation",
    "repeated-investigation-pattern",
    "recurring-without-remediation",
    "potential-metric-gaming",
  ],
  "satsa.negative_space": ["negative-space"],
  "satsa.anomaly": ["anomaly"],
  "satsa.peer_benchmark": ["peer-benchmark"],
  "satsa.coverage_gap": ["coverage-gap"],
  "satsa.drift": ["drift"],
  "satsa.cross_entity_insights": ["cross-entity-insights"],
  "satsa.case_similarity": ["case-similarity"],
  "satsa.evidence_completeness": ["evidence-completeness"],
  "satsa.workflow_reconstruction": ["workflow-reconstruction"],
  "satsa.entity_asset_resolution": ["entity-asset-resolution"],
};

/** Supervision layer each SAT-SA agent belongs to (docs/SATSA_SYSTEM_ARCHITECTURE.md). */
export const AGENT_LAYER: Record<string, "Ingestion" | "Detection" | "Assessment" | "Trust" | "Human authority"> = {
  "satsa.ingest": "Ingestion",
  "satsa.normalize": "Ingestion",
  "satsa.entity_asset_resolution": "Detection",
  "satsa.execution_gap": "Detection",
  "satsa.negative_space": "Detection",
  "satsa.workflow_reconstruction": "Detection",
  "satsa.anomaly": "Detection",
  "satsa.peer_benchmark": "Detection",
  "satsa.coverage_gap": "Detection",
  "satsa.drift": "Detection",
  "satsa.cross_entity_insights": "Detection",
  "satsa.case_similarity": "Detection",
  "satsa.evidence_completeness": "Detection",
  "satsa.correlation_fusion": "Assessment",
  "satsa.fusion": "Assessment",
  "satsa.prioritization": "Assessment",
  "satsa.recommendation": "Assessment",
  "satsa.trust_provenance": "Trust",
  "satsa.meta_audit": "Trust",
  "satsa.evidence_assembly": "Trust",
  "satsa.validation": "Trust",
  "satsa.review_workflow": "Human authority",
  "satsa.report_generation": "Human authority",
};
