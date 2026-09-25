/**
 * SAT-SA domain types for the web UI.
 *
 * These mirror the Python backend's own records (satsa/domain/*,
 * satsa/analysis/*) field for field, in camelCase. Where a backend
 * record serializes snake_case keys verbatim (risk profile, entity
 * priority, agent spec, supervisor decision, meta-audit, validation)
 * the type keeps snake_case so an API response can be passed through
 * unchanged. See docs/API_CONTRACT.md for the endpoint shapes.
 */

export type Timestamp = number; // seconds since epoch, as the backend stores it

/* ---------- entities, assessments, submissions ---------- */

export interface Entity {
  id: string;
  displayName: string;
  sector: string;
  environmentClass: string;
  cohortAttributes: Record<string, unknown>;
  accessScope: string;
  contentDigest: string;
}

export type AssessmentStatus = "draft" | "open" | "closed" | "superseded";

export interface Assessment {
  id: string;
  entityId: string;
  periodStart: Timestamp;
  periodEnd: Timestamp;
  timezone: string;
  policyVersion: string;
  status: AssessmentStatus;
  contentDigest: string;
}

export const EVIDENCE_CATEGORIES = [
  "alerts",
  "cases",
  "investigation_steps",
  "escalations",
  "dispositions",
  "assets",
] as const;
export type EvidenceCategory = (typeof EVIDENCE_CATEGORIES)[number];

export interface IngestCategoryReport {
  received: number;
  accepted: number;
  rejected: number;
  warnings?: unknown[];
  errors?: unknown[];
}

export interface Submission {
  id: string;
  assessmentId: string;
  entityId: string;
  sourceSystem: string;
  declaredPeriodStart: Timestamp;
  declaredPeriodEnd: Timestamp;
  /** filename -> SHA3-256 hex */
  fileDigests: Record<string, string>;
  declaredCounts: Partial<Record<EvidenceCategory, number>>;
  schemaName: string;
  receivedAt: Timestamp | null;
  signatureStatus: "unsigned" | "signed" | "verified" | "verification_failed";
  ingestStatus: string;
  ingestReport: Record<string, unknown>;
  snapshotDigest: string;
  contentDigest: string;
}

/* ---------- analysis runs ---------- */

export type RunStatus = "pending" | "running" | "completed" | "failed" | "partial" | "cancelled";

export interface RunTrustSummary {
  algorithm_id?: string;
  signed_findings?: number;
  [key: string]: unknown;
}

export interface AnalysisRun {
  id: string;
  entityId: string;
  assessmentId: string;
  snapshotDigest: string;
  codeVersion: string;
  analyticsVersion: string;
  status: RunStatus;
  startedAt: Timestamp | null;
  finishedAt: Timestamp | null;
  summary: {
    workers?: string[];
    observations?: number;
    findings?: number;
    failed_jobs?: string[];
    trust?: RunTrustSummary;
  };
  error: string;
  contentDigest: string;
}

export interface WorkerJob {
  id: string;
  runId: string;
  workerName: string;
  status: string;
  startedAt: Timestamp | null;
  finishedAt: Timestamp | null;
  error: string;
}

export type ObservationState = "signal" | "no_signal" | "insufficient_data" | "not_applicable" | "error";

export interface Observation {
  id: string;
  runId: string;
  workerName: string;
  detectorVersion: string;
  entityId: string;
  assessmentId: string;
  scope: Record<string, unknown>;
  state: ObservationState;
}

/* ---------- findings ---------- */

export interface ConfidenceVector {
  analytical_support: number;
  evidence_completeness: number;
  /** null = not applicable (no peer cohort), never zero */
  peer_confidence: number | null;
  overall: number;
}

/** satsa.analysis.recommend: bounded human-action hint, never a decision. */
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
  action: RecommendationAction;
  reason: string;
  finding_id: string;
  rule_or_category: string;
  evidence_refs: string[];
  limitations: string;
}

/** satsa.analysis.prioritize._severity_of: coarse bucket derived from the rule family. */
export type Severity = "high" | "medium" | "low";

export type RiskDimensionName =
  | "execution_gap"
  | "peer_deviation"
  | "detection_gap"
  | "negative_space"
  | "anomaly"
  | "investigation_quality"
  | "escalation_discipline";

export interface Finding {
  id: string;
  observationId: string;
  runId: string;
  entityId: string;
  assessmentId: string;
  workerName: string;
  detectorVersion: string;
  ruleOrCategory: string;
  state: ObservationState;
  rationale: string;
  /** alert / case / asset / investigation-step / entity ids the finding is about */
  scopedSubjects: string[];
  statistic: number | null;
  effect: number | null;
  threshold: number | null;
  confidence: ConfidenceVector | null;
  /** SourceRecord ids */
  evidenceRefs: string[];
  limitations: string;
  createdAt: Timestamp;
  contentDigest: string;
  riskDimension: RiskDimensionName;
  severity: Severity | null;
  priorityScore: number | null;
  recommendation: Recommendation | null;
}

/* ---------- risk and prioritization (snake_case: backend to_dict) ---------- */

export interface RiskDimension {
  name: RiskDimensionName;
  weight: number;
  score: number;
  finding_ids: string[];
  rationale: string;
}

export type ConfidenceBucket = "very_low" | "low" | "medium" | "high";

export interface EntityRiskProfile {
  entity_id: string;
  run_id: string | null;
  total_score: number;
  confidence_bucket: ConfidenceBucket;
  dimensions: RiskDimension[];
  weights: Record<RiskDimensionName, number>;
  [key: string]: unknown;
}

export interface EntityPriority {
  entity_id: string;
  priority_score: number;
  risk_score: number;
  confidence_bucket: ConfidenceBucket;
  run_id: string | null;
  rationale: string;
  top_dimensions: RiskDimensionName[];
  high_signal_count: number;
}

/* ---------- human review ---------- */

/** Actions the backend ReviewService accepts today (satsa/domain/evidence.py REVIEW_ACTIONS, UI allow-list). */
export type BackendReviewAction = "confirm" | "dismiss" | "escalate" | "request_review" | "annotate";

export interface ReviewDecision {
  id: string;
  findingId: string;
  principalIdentityId: string;
  action: BackendReviewAction;
  reason: string;
  occurredAt: Timestamp;
  previousRevisionId: string | null;
  findingContentDigest: string;
}

/* ---------- trust ---------- */

export interface TrustReceipt {
  id: string;
  subjectType: "run" | "finding";
  subjectId: string;
  algorithmId: string;
  contentDigest: string;
  publicKeyBytes: number;
  signatureBytes: number;
  createdAt: Timestamp;
}

export interface SubjectVerification {
  ok: boolean;
  reason: string;
}

export interface RunVerification {
  verifiedAt: Timestamp;
  run: SubjectVerification | null;
  findings: Array<{ finding_id: string; rule: string; ok: boolean; reason: string }>;
  reviews: Array<{ finding_id: string; decisions: Array<Record<string, unknown>> }>;
}

export interface MetaAudit {
  findings_checked: number;
  findings_ok: number;
  findings_failed: Array<{ finding_id: string; reason: string }>;
  finding_coverage: number | null;
  reviews_checked: number;
  reviews_ok: number;
  reviews_failed: Array<Record<string, unknown>>;
  review_coverage: number | null;
  runs_checked: number;
  runs_ok: number;
  runs_failed: Array<{ run_id: string; reason: string }>;
  run_coverage: number | null;
  ledger_integrity: {
    chain_ok: boolean;
    chain_error: string;
    ledger_entries: number;
    db_rows: number;
    missing_from_db: string[];
    missing_from_ledger: string[];
    fully_consistent: boolean;
  } | null;
  fully_compliant: boolean;
}

/* ---------- source evidence ---------- */

export interface SourceRecord {
  id: string;
  submissionId: string;
  fileDigest: string;
  format: string;
  locator: string;
  originalRecordDigest: string;
}

export interface AlertRecord {
  id: string;
  entityId: string;
  assessmentId: string;
  submissionId: string;
  nativeId: string;
  createdAt: Timestamp;
  nativeSeverity: string;
  mappedSeverity: string;
  mappedCategory: string;
  assetRefs: string[];
  caseRefs: string[];
  acknowledgedAt: Timestamp | null;
  closedAt: Timestamp | null;
  dispositionId: string | null;
  sourceRecordRef: string;
}

export interface CaseRecord {
  id: string;
  entityId: string;
  assessmentId: string;
  nativeId: string;
  openedAt: Timestamp;
  alertRefs: string[];
  ownerPseudonym: string;
  status: string;
  closedAt: Timestamp | null;
  closureReason: string;
  investigationRefs: string[];
  sourceRecordRef: string;
}

export interface InvestigationStepRecord {
  id: string;
  caseId: string;
  actionType: string;
  performedAt: Timestamp;
  sequence: number;
  analystPseudonym: string;
  noteText: string;
}

export interface EscalationRecord {
  id: string;
  entityId: string;
  assessmentId: string;
  occurredAt: Timestamp;
  alertId: string | null;
  caseId: string | null;
  destinationRole: string;
  trigger: string;
  outcome: string;
}

export interface DispositionRecord {
  id: string;
  entityId: string;
  assessmentId: string;
  occurredAt: Timestamp;
  alertId: string | null;
  caseId: string | null;
  mappedCategory: string;
  reason: string;
  approverRole: string;
}

export interface AssetRecord {
  id: string;
  entityId: string;
  assessmentId: string;
  nativeId: string;
  criticality: string;
  environment: string;
  controls: string[];
}

export interface SecurityData {
  alerts: AlertRecord[];
  cases: CaseRecord[];
  investigationSteps: InvestigationStepRecord[];
  escalations: EscalationRecord[];
  dispositions: DispositionRecord[];
  assets: AssetRecord[];
}

/* ---------- agents and supervision (snake_case: backend AgentSpec / Decision) ---------- */

export interface AgentSpec {
  agent_id: string;
  name: string;
  family: "mlops" | "satsa";
  purpose: string;
  inputs: string[];
  outputs: string[];
  evidence_types: string[];
  implementation_ref: string;
  version: string;
  status: string;
  notes: string;
}

export type SupervisorAction =
  | "SATSA_SURFACE"
  | "SATSA_INSPECT"
  | "SATSA_REQUEST_EVIDENCE"
  | "SATSA_ESCALATE_FOR_REVIEW"
  | "SATSA_DEFER"
  | "SATSA_ACCEPT"
  | "SATSA_CLOSE_REVIEW";

export interface SupervisorDecision {
  decision_id: string;
  vocabulary: "satsa" | "mlops";
  action: SupervisorAction | string;
  rationale: string;
  target_ids: string[];
  evidence_refs: string[];
  requires_human: boolean;
  [key: string]: unknown;
}

/* ---------- validation ---------- */

export interface CompositionCase {
  case_id: string;
  scenario: string;
  expected_signals: string[];
  emitted_signals: string[];
  expected_action: string;
  emitted_action: string;
  signals_ok: boolean;
  action_ok: boolean;
  [key: string]: unknown;
}

export interface ValidationReport {
  layers: Array<Record<string, unknown>>;
  composition: CompositionCase[];
  summary: Record<string, unknown>;
  error?: string;
}

/* ---------- identity ---------- */

export type SatsaRole = "satsa_viewer" | "satsa_analyst" | "satsa_supervisor" | "satsa_auditor" | "satsa_admin";

export interface SessionUser {
  identityId: string;
  displayName: string;
  role: SatsaRole;
}
