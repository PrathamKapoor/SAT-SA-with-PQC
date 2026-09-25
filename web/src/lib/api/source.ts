import type {
  AgentSpec,
  AnalysisRun,
  Assessment,
  Entity,
  EntityPriority,
  EntityRiskProfile,
  Finding,
  MetaAudit,
  Observation,
  ReviewDecision,
  RunVerification,
  SecurityData,
  SourceRecord,
  Submission,
  SupervisorDecision,
  TrustReceipt,
  ValidationReport,
  WorkerJob,
} from "@/lib/types/domain";

/**
 * Where a page's data came from. Every page renders this so real backend
 * data, the development fixture, and empty states are never mixed silently.
 */
export type DataOrigin =
  | { kind: "api"; baseUrl: string }
  | { kind: "fixture"; generatedAt: number; notice: string; satsaVersion: string };

/** Filters the backend is expected to support on GET /findings (see docs/API_CONTRACT.md). */
export interface FindingQuery {
  entityId?: string;
  runId?: string;
  state?: Finding["state"];
}

/**
 * The single seam between the UI and SAT-SA. Pages call these methods only;
 * they never import the fixture or call fetch directly. Sol 6 wires the
 * backend by implementing the endpoints in docs/API_CONTRACT.md, which the
 * `api` adapter (./http.ts) already calls.
 */
export interface SatsaDataSource {
  origin(): DataOrigin;

  listEntities(): Promise<Entity[]>;
  getEntity(id: string): Promise<Entity | null>;
  listAssessments(entityId?: string): Promise<Assessment[]>;
  listSubmissions(entityId?: string): Promise<Submission[]>;

  listRuns(entityId?: string): Promise<AnalysisRun[]>;
  listJobs(runId?: string): Promise<WorkerJob[]>;
  listObservations(runId?: string): Promise<Observation[]>;

  listFindings(query?: FindingQuery): Promise<Finding[]>;
  getFinding(id: string): Promise<Finding | null>;

  getRiskProfile(entityId: string): Promise<EntityRiskProfile | null>;
  listEntityPriorities(): Promise<EntityPriority[]>;
  getRiskWeights(): Promise<Record<string, number>>;

  listReviewDecisions(findingId?: string): Promise<ReviewDecision[]>;

  listTrustReceipts(subjectId?: string): Promise<TrustReceipt[]>;
  getRunVerification(runId: string): Promise<RunVerification | null>;
  getMetaAudit(): Promise<MetaAudit | null>;

  listSourceRecords(ids?: string[]): Promise<SourceRecord[]>;
  getSecurityData(entityId?: string): Promise<SecurityData>;

  listAgents(): Promise<AgentSpec[]>;
  getSupervisorDecision(runId: string): Promise<SupervisorDecision | null>;
  getValidation(): Promise<ValidationReport | null>;
}
