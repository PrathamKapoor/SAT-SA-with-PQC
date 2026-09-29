/**
 * Types of the SAT-SA backend API, version 1, exactly as served
 * (docs/API_CONTRACT.md, section 6; OpenAPI at /openapi.json). snake_case,
 * epoch-second timestamps. These are wire types: the UI reads them as
 * returned and never recomputes an analytical value from them.
 */

export type Timestamp = number;

export interface Page<T> {
  items: T[];
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface ErrorEnvelope {
  error: { code: string; message: string; request_id: string; details: ErrorDetail[] };
}

export interface ErrorDetail {
  location?: Array<string | number>;
  code?: string;
  message?: string;
  [key: string]: unknown;
}

export type MembershipRole = "satsa_viewer" | "satsa_analyst" | "satsa_supervisor" | "satsa_auditor" | "satsa_admin";

export interface Session {
  identity_id: string;
  name: string;
  role: string;
  user_id: string;
  expires_at: Timestamp | null;
  csrf_token: string | null;
}

export interface Organization {
  id: string;
  name: string;
  status: string;
  role: MembershipRole;
}

export interface Member {
  id: string;
  identity_id: string;
  name: string;
  email: string;
  role: MembershipRole;
  status: string;
}

export interface Invitation extends Member {
  credential: string;
}

export interface Entity {
  id: string;
  organization_id: string;
  display_name: string;
  sector: string;
  environment_class: string;
  created_at: Timestamp;
}

export type AssessmentStatus = "open" | "closed";

export interface Assessment {
  id: string;
  organization_id: string;
  entity_id: string;
  period_start: Timestamp;
  period_end: Timestamp;
  status: AssessmentStatus;
  created_at: Timestamp;
}

export interface Submission {
  id: string;
  organization_id: string;
  entity_id: string;
  assessment_id: string;
  ingest_status: string;
  created_at: Timestamp;
}

export type VersionStatus = "created" | "uploading" | "uploaded" | "validating" | "valid" | "invalid" | "failed";

export interface Version {
  id: string;
  organization_id: string;
  submission_id: string;
  version: number;
  status: VersionStatus;
  created_at: Timestamp;
  snapshot_digest: string | null;
}

export const EVIDENCE_CATEGORIES = ["alerts", "cases", "investigation_steps", "escalations", "dispositions", "assets"] as const;
export type EvidenceCategory = (typeof EVIDENCE_CATEGORIES)[number];

export interface Artifact {
  id: string;
  submission_version_id: string;
  category: EvidenceCategory;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha3_256_digest: string;
  created_at: Timestamp;
  storage_status: "uploading" | "stored" | "failed";
}

export interface ValidationIssue {
  category?: string;
  message?: string;
  locator?: string;
  native_id?: string;
  reasons?: string[];
  [key: string]: unknown;
}

export interface Validation {
  status: "valid" | "invalid" | "failed";
  errors: ValidationIssue[];
  warnings: unknown[];
  version_id: string;
  categories: Record<string, Record<string, unknown>>;
  totals: Record<string, number>;
  artifact_digests: Record<string, string>;
  validator_version: string | null;
  created_at: Timestamp | null;
}

export interface CanonicalRecord {
  record_id: string;
  category: EvidenceCategory;
  payload: Record<string, unknown>;
  content_digest: string;
  source_record_id: string;
  artifact_id: string;
  locator: string;
  file_digest: string;
  original_record_digest: string;
}

export type RunStatus = "queued" | "running" | "awaiting_review" | "cancel_requested" | "cancelled" | "completed" | "partial" | "failed";
export const RUN_TERMINAL: RunStatus[] = ["completed", "partial", "failed", "cancelled"];

export interface Step {
  worker_name: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped" | string;
  attempt: number;
  started_at: Timestamp | null;
  finished_at: Timestamp | null;
  error: string;
}

export interface Run {
  id: string;
  organization_id: string;
  entity_id: string;
  assessment_id: string;
  submission_id: string;
  submission_version_id: string;
  status: RunStatus;
  requested_at: Timestamp;
  started_at: Timestamp | null;
  finished_at: Timestamp | null;
  execution_id: string;
  execution_mode: "graph" | "standard";
  review_required: boolean;
  current_stage: string;
  progress_total: number;
  progress_completed: number;
  retry_count: number;
  error: string;
  error_code: string;
  steps: Step[];
}

export type FindingState = "signal" | "no_signal" | "insufficient_data" | "not_applicable" | "error";

export interface ConfidenceVector {
  analytical_support: number;
  evidence_completeness: number;
  peer_confidence: number | null;
  overall: number;
  [key: string]: unknown;
}

export interface Finding {
  id: string;
  run_id: string;
  observation_id: string;
  rule_or_category: string;
  rationale: string;
  statistic: number | null;
  effect: number | null;
  threshold: number | null;
  limitations: string;
  state: FindingState;
  confidence: ConfidenceVector | null;
  evidence_refs: string[];
  scoped_subjects: unknown[];
  content_digest: string;
  created_at: Timestamp;
}

export interface Evidence {
  source_record_id: string;
  artifact_id: string;
  record_id: string;
  category: EvidenceCategory;
  locator: string;
  format: string;
  file_digest: string;
  original_record_digest: string;
  canonical_record_digest: string;
}

export type RiskDimensionName =
  | "execution_gap"
  | "peer_deviation"
  | "detection_gap"
  | "negative_space"
  | "anomaly"
  | "investigation_quality"
  | "escalation_discipline";

export interface RiskDimension {
  name: RiskDimensionName;
  weight: number;
  score: number;
  finding_ids: string[];
  rationale: string;
}

export type ConfidenceBucket = "very_low" | "low" | "medium" | "high";

export interface CorrelationCluster {
  subject: string;
  finding_ids: string[];
  rule_families: string[];
  corroborated: boolean;
  rationale: string;
}

export interface RiskProfile {
  entity_id: string;
  run_id: string | null;
  total_score: number;
  confidence_bucket: ConfidenceBucket;
  dimensions: RiskDimension[];
  weights: Partial<Record<RiskDimensionName, number>>;
  correlation_clusters?: CorrelationCluster[];
}

export interface Risk {
  profile: RiskProfile;
  content_digest: string;
  algorithm_version: string;
  created_at: Timestamp;
}

export interface EntityPriority {
  entity_id: string;
  run_id: string;
  run_status: "awaiting_review" | "completed" | "partial";
  priority_score: number;
  risk_score: number;
  confidence_bucket: ConfidenceBucket;
  rationale: string;
  top_dimensions: RiskDimensionName[];
  high_signal_count: number;
}

export type RecommendationAction =
  | "INSPECT_INVESTIGATION"
  | "CHECK_ESCALATION_PATH"
  | "VERIFY_MONITORING_COVERAGE"
  | "COMPARE_WITH_PEERS"
  | "REQUEST_MISSING_EVIDENCE"
  | "REVIEW_METRIC_DEFINITION"
  | "INSPECT_ROOT_CAUSE_REMEDIATION"
  | "REVIEW";

export interface Recommendation {
  id: string;
  finding_id: string;
  action: RecommendationAction | string;
  recommendation: {
    action?: string;
    reason?: string;
    finding_id?: string;
    rule_or_category?: string;
    evidence_refs?: string[];
    limitations?: string;
    [key: string]: unknown;
  };
  content_digest: string;
  created_at: Timestamp;
}

export type DecisionAction = "confirm" | "dismiss" | "escalate";

export interface Decision {
  id: string;
  run_id: string;
  finding_id: string | null;
  user_id: string;
  principal_identity_id: string;
  action: DecisionAction;
  reason: string;
  content_digest: string;
  review_context_digest: string | null;
  created_at: Timestamp;
}

export interface Receipt {
  id: string | number;
  organization_id: string;
  run_id: string;
  decision_id: string;
  schema_version: number;
  state: "prepared" | "recorded" | "verified" | string;
  key_id: string;
  algorithm_id: string;
  content_digest: string;
  created_at: Timestamp;
  ledger_entry_hash: string;
  signature_b64: string;
  public_key_b64: string;
}

export type VerificationStatus = "verified" | "inconsistent" | "not_finalized" | "unavailable";

export interface Verification {
  run_id: string;
  status: VerificationStatus;
  verified_at: Timestamp;
  code: string;
  message: string;
}

export interface AuditEvent {
  event_id: string;
  timestamp: Timestamp;
  actor: string;
  action: string;
  resource: string;
  result: string;
}

/* ---------- MLOps (Phase 21, docs/MLOPS.md) ---------- */

export type DataOrigin = "organizational" | "synthetic" | "controlled" | "external";
export type DatasetStatus = "created" | "validating" | "valid" | "invalid" | "archived";

export interface ValidationCheck {
  check: string;
  passed: boolean;
  detail: string;
}

export interface MLDataset {
  id: string;
  name: string;
  version: number;
  data_origin: DataOrigin;
  source: string;
  feature_version: string;
  schema_version: number;
  record_count: number;
  label_counts: Record<string, number>;
  content_digest: string;
  status: DatasetStatus;
  validation: { status: string; policy_version?: string; checks: ValidationCheck[] } | null;
  lineage: Record<string, unknown>;
  created_by: string;
  created_at: Timestamp;
  validated_at: Timestamp | null;
}

export type MLJobStatus = "queued" | "running" | "retry_wait" | "cancel_requested" | "completed" | "failed" | "cancelled";

export interface MLJob {
  id: string;
  kind: "validate_dataset" | "train" | "drift";
  subject_id: string;
  status: MLJobStatus;
  params: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: string;
  attempt_count: number;
  max_attempts: number;
  requested_by: string;
  created_at: Timestamp;
  updated_at: Timestamp;
  completed_at: Timestamp | null;
}

export interface MLTrainingRun {
  id: string;
  job_id: string;
  dataset_id: string;
  feature_version: string;
  model_family: string;
  hyperparameters: Record<string, unknown>;
  seed: number;
  environment: Record<string, string> | null;
  status: "running" | "completed" | "failed" | "cancelled";
  model_id: string | null;
  error: string;
  requested_by: string;
  started_at: Timestamp;
  finished_at: Timestamp | null;
}

export type ModelState = "registered" | "verified" | "quarantined" | "approved" | "retired";

export interface ModelEvaluation {
  supervised_metrics: "available" | "unavailable";
  reason?: string;
  holdout_rows: number;
  holdout_positive: number;
  training_rows?: number;
  threshold: number;
  confusion_matrix?: { tp: number; fp: number; fn: number; tn: number };
  precision?: number | null;
  recall?: number | null;
  f1?: number | null;
  roc_auc?: number;
  pr_auc?: number;
  brier?: number;
  calibration?: Array<{ range: [number, number]; count: number; mean_predicted: number; observed_rate: number }>;
}

export interface ModelPassport {
  model_id: string;
  model_name: string;
  model_version: number;
  training_run_id: string;
  dataset: { id: string; name: string; version: number; content_digest: string; data_origin: DataOrigin; record_count: number; label_counts: Record<string, number> };
  training_population: string;
  feature_version: string;
  feature_dependencies: Array<{ name: string; definition: string }>;
  algorithm: string;
  hyperparameters: Record<string, unknown>;
  random_seed: number;
  environment: Record<string, string>;
  artifact: { format: string; sha3_256: string; storage_key: string };
  evaluation: ModelEvaluation;
  verification: { passed: boolean; reason: string; policy: string };
  intended_use: string;
  known_limitations: string[];
  created_at: Timestamp;
}

export interface MLModel {
  id: string;
  name: string;
  version: number;
  state: ModelState;
  deployed: boolean;
  artifact_digest: string;
  passport_digest: string;
  feature_version: string;
  dataset_id: string;
  training_run_id: string;
  created_at: Timestamp;
  approval: { approved_by: string; justification: string; approved_at: Timestamp } | null;
  passport: ModelPassport;
  events: Array<{ from_state: string | null; to_state: string; actor_user_id: string; reason: string; created_at: Timestamp }>;
  deployments: Array<{ id: string; kind: string; active: number; deployed_by: string; reason: string; created_at: Timestamp; deactivated_at: Timestamp | null }>;
}

export interface MLDeployment {
  id: string;
  model_name: string;
  model_id: string;
  kind: "deploy" | "rollback";
  active: boolean;
  previous_deployment_id: string | null;
  deployed_by: string;
  reason: string;
  created_at: Timestamp;
  deactivated_at: Timestamp | null;
}

export type Quantiles = { p05: number; p25: number; p50: number; p75: number; p95: number };

export interface MLMonitoring {
  model_name: string;
  status: "no_deployed_model" | "no_observations" | "observed";
  active_deployment: MLDeployment | null;
  all_models: { inferences: number; abstentions_by_reason: Record<string, number> };
  active_model: {
    inferences: number;
    scored: number;
    abstained: number;
    missing_feature_rate: number;
    score_distribution: Quantiles | null;
    latency_ms: Quantiles;
    realized_performance: { status: "available" | "insufficient_labels"; labeled_inferences: number; minimum_required: number; roc_auc?: number };
  } | null;
}

export interface MLDriftReport {
  id: string;
  model_id: string;
  job_id: string;
  metric: string;
  threshold: number;
  baseline_count: number;
  current_count: number;
  window_start: Timestamp | null;
  window_end: Timestamp | null;
  result: "drift" | "no_drift" | "insufficient_data";
  details: { score_psi?: number; reason?: string; feature_psi?: Record<string, number> };
  policy_version: string;
  created_at: Timestamp;
}

export interface MLRetrainingRequest {
  id: string;
  model_name: string;
  model_id: string | null;
  trigger: "drift" | "performance" | "operator";
  status: "open" | "accepted" | "dismissed";
  evidence: Record<string, unknown>;
  requested_by: string;
  resolved_by: string | null;
  resolution: string;
  training_job_id: string | null;
  created_at: Timestamp;
  resolved_at: Timestamp | null;
}

export type AbstainReason =
  | "no_deployed_model"
  | "model_unavailable"
  | "feature_version_mismatch"
  | "missing_features"
  | "out_of_distribution"
  | "low_confidence"
  | "inference_error";

export interface MLInference {
  id: string;
  run_id: string;
  model_name: string;
  model_id: string | null;
  deployment_id: string | null;
  artifact_digest: string | null;
  feature_version: string;
  features: number[] | null;
  status: "scored" | "abstained";
  abstain_reason: AbstainReason | null;
  score: number | null;
  latency_ms: number;
  content_digest: string;
  created_at: Timestamp;
}
