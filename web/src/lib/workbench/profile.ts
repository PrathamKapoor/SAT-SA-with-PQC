import type { SatsaRole } from "@/lib/types/domain";

/**
 * Workbench profiles. There is one Workbench; a profile only decides what it
 * emphasises for the active role: tile order and copy, the contextual card in
 * the header, the workflow guide, and which overview metrics lead. Every value
 * shown is computed from the data source (see ./metrics.ts); a profile never
 * supplies numbers. Access is still decided by the permission model, and the
 * backend remains the authority for every action.
 */

export type TileKey = "ingest" | "submissions" | "entities" | "findings" | "queue" | "analytics" | "trust" | "reports";
export type ContextCard = "review" | "analysis" | "verification" | "platform" | "assessment";
export type OverviewKind = "capability" | "analytical" | "traceability" | "platform";

/** Real quantities a workflow step can show progress against. */
export type StepProgress = "decisions" | "completeSubmissions" | "verifiedFindings";

export interface WorkflowStep {
  title: string;
  detail: string;
  href: string;
  icon: "crosshair" | "search" | "gavel" | "shield" | "upload" | "chart" | "database" | "file" | "server" | "users" | "layers";
  progress?: StepProgress;
}

export interface WorkbenchProfile {
  viewLabel: string;
  tiles: [TileKey, TileKey, TileKey, TileKey, TileKey, TileKey];
  copy: Partial<Record<TileKey, string>>;
  context: ContextCard;
  workflowLabel: string;
  workflow: [WorkflowStep, WorkflowStep, WorkflowStep, WorkflowStep];
  overview: OverviewKind;
}

const SUPERVISOR: WorkbenchProfile = {
  viewLabel: "Supervisor view",
  tiles: ["findings", "queue", "entities", "trust", "analytics", "ingest"],
  copy: {
    findings: "Review evidence-backed supervisory signals",
    queue: "Findings awaiting your decision",
    entities: "CSEs ranked by supervisory risk",
    trust: "Check evidence before deciding",
    analytics: "Why each detector signalled",
    ingest: "Submissions behind this period",
  },
  context: "review",
  workflowLabel: "Supervision cycle",
  workflow: [
    { title: "Triage attention", detail: "Start with the highest-risk entities", href: "/workbench/entities", icon: "crosshair" },
    { title: "Inspect evidence", detail: "Read the signals behind each score", href: "/workbench/findings", icon: "search" },
    { title: "Record decision", detail: "Confirm, reject or escalate", href: "/workbench/review-queue", icon: "gavel", progress: "decisions" },
    { title: "Verify and report", detail: "Check the ledger, export the report", href: "/workbench/trust", icon: "shield" },
  ],
  overview: "capability",
};

const ANALYST: WorkbenchProfile = {
  viewLabel: "Analyst view",
  tiles: ["ingest", "submissions", "analytics", "findings", "entities", "trust"],
  copy: {
    ingest: "Validate and ingest CSE submissions",
    submissions: "Ingestion and validation status",
    analytics: "Detector coverage and abstentions",
    findings: "Signals produced by the analytical pipeline",
    entities: "Entities analysed this period",
    trust: "Signed outputs of each run",
  },
  context: "analysis",
  workflowLabel: "Analysis cycle",
  workflow: [
    { title: "Validate submission", detail: "Check categories and rejected rows", href: "/workbench/submissions", icon: "upload", progress: "completeSubmissions" },
    { title: "Inspect analytical coverage", detail: "Detector outcomes per run", href: "/workbench/pipeline", icon: "chart" },
    { title: "Inspect findings", detail: "Signals and their thresholds", href: "/workbench/findings", icon: "search" },
    { title: "Prepare evidence", detail: "Source records behind each signal", href: "/workbench/security-data", icon: "database" },
  ],
  overview: "analytical",
};

const AUDITOR: WorkbenchProfile = {
  viewLabel: "Auditor view",
  tiles: ["trust", "findings", "entities", "reports", "analytics", "ingest"],
  copy: {
    trust: "Signatures, digests and the decision ledger",
    findings: "Trace findings back to their evidence",
    entities: "Entities covered by the assessment",
    reports: "Supervisory deliverables per entity",
    analytics: "How each finding was produced",
    ingest: "Submissions and their file digests",
  },
  context: "verification",
  workflowLabel: "Audit trail",
  workflow: [
    { title: "Inspect provenance", detail: "Source to decision, link by link", href: "/workbench/trust", icon: "layers" },
    { title: "Verify evidence", detail: "Signed findings against live records", href: "/workbench/findings", icon: "shield", progress: "verifiedFindings" },
    { title: "Verify decisions", detail: "Digest-bound, append-only record", href: "/workbench/decisions", icon: "gavel" },
    { title: "Report", detail: "Printable report per entity", href: "/workbench/reports", icon: "file" },
  ],
  overview: "traceability",
};

const ADMIN: WorkbenchProfile = {
  viewLabel: "Administrator view",
  tiles: ["entities", "findings", "trust", "analytics", "ingest", "queue"],
  copy: {
    entities: "CSEs in the current assessment",
    findings: "Portfolio-level supervisory signals",
    trust: "Platform trust and audit state",
    analytics: "Detector activity across the portfolio",
    ingest: "Submission intake for the period",
    queue: "Decisions pending across entities",
  },
  context: "platform",
  workflowLabel: "Platform cycle",
  workflow: [
    { title: "Monitor platform", detail: "Data source, versions and session", href: "/workbench/system", icon: "server" },
    { title: "Review portfolio", detail: "Coverage across entities", href: "/workbench/entities", icon: "crosshair" },
    { title: "Verify security", detail: "Runs, findings and ledger", href: "/workbench/trust", icon: "shield", progress: "verifiedFindings" },
    { title: "Manage access", detail: "Roles and permissions", href: "/workbench/admin", icon: "users" },
  ],
  overview: "platform",
};

const VIEWER: WorkbenchProfile = {
  viewLabel: "Viewer view",
  tiles: ["entities", "findings", "analytics", "trust", "queue", "ingest"],
  copy: {
    entities: "Supervisory posture by entity",
    findings: "View evidence-backed supervisory findings",
    analytics: "How the analysis works",
    trust: "Whether results verify",
    queue: "Findings awaiting a decision",
    ingest: "Submissions in this period",
  },
  context: "assessment",
  workflowLabel: "Reading guide",
  workflow: [
    { title: "Review posture", detail: "Risk across entities and dimensions", href: "/workbench/overview", icon: "chart" },
    { title: "Inspect findings", detail: "What was found and why", href: "/workbench/findings", icon: "search" },
    { title: "Inspect evidence", detail: "The submitted records", href: "/workbench/security-data", icon: "database" },
    { title: "View reports", detail: "Per-entity supervisory reports", href: "/workbench/reports", icon: "file" },
  ],
  overview: "capability",
};

const PROFILES: Record<SatsaRole, WorkbenchProfile> = {
  satsa_supervisor: SUPERVISOR,
  satsa_analyst: ANALYST,
  satsa_auditor: AUDITOR,
  satsa_admin: ADMIN,
  satsa_viewer: VIEWER,
};

export function getWorkbenchProfile(role: SatsaRole): WorkbenchProfile {
  return PROFILES[role];
}
