import type { AgentSpec, Finding, Observation } from "@/lib/types/domain";

/**
 * How each registered agent (satsa/supervisor/agents.py) shows up in a real
 * run. SAT-SA agents are deterministic analytical components and pipeline
 * services, not language models. Worker agents are observed through their
 * observations and findings; stage agents through the records they produce.
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

export interface WorkerActivity {
  observations: number;
  signal: number;
  noSignal: number;
  insufficient: number;
  findings: number;
  evidenceRefs: number;
  meanConfidence: number | null;
}

export function workerActivity(workers: string[], observations: Observation[], findings: Finding[]): WorkerActivity {
  const obs = observations.filter((o) => workers.includes(o.workerName));
  const fs = findings.filter((f) => workers.includes(f.workerName));
  const confs = fs.map((f) => f.confidence?.overall).filter((c): c is number => c != null);
  return {
    observations: obs.length,
    signal: obs.filter((o) => o.state === "signal").length,
    noSignal: obs.filter((o) => o.state === "no_signal").length,
    insufficient: obs.filter((o) => o.state === "insufficient_data").length,
    findings: fs.length,
    evidenceRefs: fs.reduce((n, f) => n + f.evidenceRefs.length, 0),
    meanConfidence: confs.length ? confs.reduce((a, b) => a + b, 0) / confs.length : null,
  };
}

export function agentKind(a: AgentSpec): "worker" | "stage" | "platform" {
  if (a.family === "mlops") return "platform";
  return AGENT_WORKERS[a.agent_id] ? "worker" : "stage";
}
