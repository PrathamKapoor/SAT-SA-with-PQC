import type { RecommendationAction, RiskDimensionName } from "@/lib/api/types";

/** Coarse rule-family bucket (satsa.analysis.prioritize._severity_of); the hosted API does not serve it per finding. */
export type Severity = "high" | "medium" | "low";

/** Finding families = the first segment of rule_or_category (satsa/analysis/workers). */
export type FindingFamily =
  | "execution_gap"
  | "negative_space"
  | "anomaly"
  | "peer_benchmark"
  | "coverage_gap"
  | "drift"
  | "cross_entity"
  | "case_similarity"
  | "evidence_completeness"
  | "workflow_reconstruction"
  | "entity_asset_resolution"
  | "other";

export const FAMILY_LABEL: Record<FindingFamily, string> = {
  execution_gap: "Execution gap",
  negative_space: "Negative space",
  anomaly: "Anomaly",
  peer_benchmark: "Peer deviation",
  coverage_gap: "Coverage gap",
  drift: "Drift",
  cross_entity: "Cross-entity",
  case_similarity: "Case similarity",
  evidence_completeness: "Evidence completeness",
  workflow_reconstruction: "Workflow reconstruction",
  entity_asset_resolution: "Asset resolution",
  other: "Other",
};

export const FAMILY_DESCRIPTION: Record<FindingFamily, string> = {
  execution_gap: "Process steps that were skipped, rushed or bypassed",
  negative_space: "Evidence that should exist but was never submitted",
  anomaly: "Robust statistical outliers within the entity's own data",
  peer_benchmark: "Deviation from a trimmed cohort of comparable entities",
  coverage_gap: "Critical assets with little or no monitoring signal",
  drift: "Change against the entity's previous assessment period",
  cross_entity: "Patterns shared across entities in the same period",
  case_similarity: "Cases closed with templated, near-identical records",
  evidence_completeness: "Expected evidence categories missing from a submission",
  workflow_reconstruction: "Out-of-order or impossible workflow sequences",
  entity_asset_resolution: "Assets that vanished between assessment periods",
  other: "Unclassified signal",
};

export function familyOf(rule: string): FindingFamily {
  const head = rule.split(".")[0];
  if (head === "cross_entity_insights") return "cross_entity";
  return head in FAMILY_LABEL ? (head as FindingFamily) : "other";
}

/** Human titles for the rules the 16 workers emit. Unknown rules fall back to a readable form. */
const RULE_TITLE: Record<string, string> = {
  "execution_gap.fast_closure": "Alerts closed faster than the severity SLA",
  "execution_gap.ack_without_investigation": "Acknowledged and closed without investigation",
  "execution_gap.critical_without_escalation": "Critical alerts without escalation",
  "execution_gap.repeated_investigation_pattern": "Repeated, identical investigation steps",
  "execution_gap.recurring_without_remediation": "Recurring issue without remediation",
  "execution_gap.potential_metric_gaming": "Closure pattern consistent with metric gaming",
  "negative_space.missing_investigation": "Cases with no recorded investigation",
  "negative_space.missing_disposition": "Closed alerts with no disposition",
  "negative_space.missing_escalation": "Critical alerts with no escalation record",
  "negative_space.missing_monitoring": "Critical assets that produced no alerts",
  "negative_space.unexpectedly_low_activity": "Unexpectedly low alert activity",
  "coverage_gap.missing_monitoring": "Critical assets below the monitoring floor",
  "evidence_completeness.missing_categories": "Evidence categories missing from submission",
  "case_similarity.template_cluster": "Cases closed with templated records",
};

const METRIC_TITLE: Record<string, string> = {
  closure_time: "closure time",
  investigation_duration: "investigation duration",
  escalation_rate: "escalation rate",
  investigation_depth: "investigation depth",
  investigation_depth_median: "median investigation depth",
  alerts_per_critical_asset: "alerts per critical asset",
};

export function ruleTitle(rule: string): string {
  if (RULE_TITLE[rule]) return RULE_TITLE[rule];
  const parts = rule.split(".");
  const family = familyOf(rule);
  if (family === "anomaly" && parts.length >= 3) {
    const metric = METRIC_TITLE[parts[1]] ?? parts[1].replaceAll("_", " ");
    return `Unusually ${parts[2]} ${metric}`;
  }
  if (family === "peer_benchmark" && parts.length >= 2) {
    const metric = METRIC_TITLE[parts[1]] ?? parts[1].replaceAll("_", " ");
    return `${metric.charAt(0).toUpperCase()}${metric.slice(1)} deviates from peers`;
  }
  const tail = parts.slice(1).join(" ").replaceAll("_", " ");
  return tail ? tail.charAt(0).toUpperCase() + tail.slice(1) : rule;
}

export const DIMENSION_LABEL: Record<RiskDimensionName, string> = {
  execution_gap: "Execution gap",
  peer_deviation: "Peer deviation",
  detection_gap: "Detection gap",
  negative_space: "Negative space",
  anomaly: "Anomaly",
  investigation_quality: "Investigation quality",
  escalation_discipline: "Escalation discipline",
};

export const DIMENSION_ORDER: RiskDimensionName[] = [
  "execution_gap",
  "peer_deviation",
  "detection_gap",
  "negative_space",
  "anomaly",
  "investigation_quality",
  "escalation_discipline",
];

export const RECOMMENDATION_LABEL: Record<RecommendationAction, string> = {
  INSPECT_INVESTIGATION: "Inspect the investigation",
  CHECK_ESCALATION_PATH: "Check the escalation path",
  VERIFY_MONITORING_COVERAGE: "Verify monitoring coverage",
  COMPARE_WITH_PEERS: "Compare with peers",
  REQUEST_MISSING_EVIDENCE: "Request the missing evidence",
  REVIEW_METRIC_DEFINITION: "Review the metric definition",
  INSPECT_ROOT_CAUSE_REMEDIATION: "Inspect root-cause remediation",
  REVIEW: "Review",
};

export const SUPERVISOR_ACTION_LABEL: Record<string, string> = {
  SATSA_SURFACE: "Surface for review",
  SATSA_INSPECT: "Inspect",
  SATSA_REQUEST_EVIDENCE: "Request evidence",
  SATSA_ESCALATE_FOR_REVIEW: "Escalate for review",
  SATSA_DEFER: "Defer",
  SATSA_ACCEPT: "Accept",
  SATSA_CLOSE_REVIEW: "Close review",
};

export const SEVERITY_LABEL: Record<Severity, string> = { high: "High", medium: "Medium", low: "Low" };

export const CONFIDENCE_BUCKET_LABEL: Record<string, string> = {
  very_low: "Very low",
  low: "Low",
  medium: "Medium",
  high: "High",
};

export const CATEGORY_LABEL: Record<string, string> = {
  alerts: "Alerts",
  cases: "Cases",
  investigation_steps: "Investigation steps",
  escalations: "Escalations",
  dispositions: "Dispositions",
  assets: "Assets",
};

export function subjectKind(id: string): "alert" | "case" | "asset" | "invstep" | "entity" | "other" {
  const head = id.split("_")[0];
  return head === "alert" || head === "case" || head === "asset" || head === "invstep" || head === "entity"
    ? head
    : "other";
}

export function workerLabel(name: string): string {
  return name
    .split("-")
    .map((w, i) => (i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w))
    .join(" ");
}
