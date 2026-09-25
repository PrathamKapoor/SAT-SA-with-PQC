import "server-only";

import { toRowData, type FindingRowData } from "@/components/domain/finding-row";
import { getSource } from "@/lib/api";
import { CATEGORY_LABEL } from "@/lib/domain/labels";
import { byPriority, loadCore, loadEntityViews, loadFindingViews, type EntityView, type FindingView } from "@/lib/model";
import { EVIDENCE_CATEGORIES, type MetaAudit, type RiskDimensionName } from "@/lib/types/domain";
import type { OverviewKind } from "./profile";

/**
 * Everything the Workbench can show, computed once per request from the data
 * source for the selected period and cohort. Joins and counts only: no score
 * is derived here that the backend did not produce.
 */
export interface WorkbenchData {
  scoped: EntityView[];
  signal: FindingView[];
  rows: FindingRowData[];
  high: number;
  highEntities: number;
  submissions: number;
  submissionsAccepted: number;
  incomplete: EntityView[];
  categoriesPresent: number;
  families: number;
  verified: number;
  failed: number;
  withEvidence: number;
  receipts: number;
  decided: number;
  runs: number;
  runsCompleted: number;
  runsVerified: number;
  jobs: number;
  jobsCompleted: number;
  observations: number;
  abstained: number;
  audit: MetaAudit | null;
  originKind: "fixture" | "api";
}

export const DETECTOR_FAMILY_COUNT = 11; // families emitted by the 16 default workers

export async function loadWorkbenchData(filter: { cohort?: string; period?: string }): Promise<WorkbenchData> {
  const src = getSource();
  const [core, findings, entities, receipts, jobs, observations, audit] = await Promise.all([
    loadCore(),
    loadFindingViews(),
    loadEntityViews(),
    src.listTrustReceipts(),
    src.listJobs(),
    src.listObservations(),
    src.getMetaAudit(),
  ]);
  const inPeriod = (id: string) => {
    if (!filter.period) return true;
    const a = core.assessments.find((x) => x.id === id);
    return a ? `${a.periodStart}-${a.periodEnd}` === filter.period : false;
  };
  const scoped = entities.filter((e) => (!filter.cohort || e.entity.sector === filter.cohort) && (!e.assessment || inPeriod(e.assessment.id)));
  const ids = new Set(scoped.map((e) => e.entity.id));
  const runIds = new Set(scoped.map((e) => e.run?.id).filter(Boolean));
  const signal = findings.filter((f) => f.state === "signal" && ids.has(f.entityId)).sort(byPriority);
  const signalIds = new Set(signal.map((f) => f.id));
  const runs = core.runs.filter((r) => runIds.has(r.id));
  const scopedJobs = jobs.filter((j) => runIds.has(j.runId));
  const scopedObs = observations.filter((o) => runIds.has(o.runId));

  return {
    scoped,
    signal,
    rows: signal.map(toRowData),
    high: signal.filter((f) => f.severity === "high").length,
    highEntities: scoped.filter((e) => e.findings.some((f) => f.severity === "high")).length,
    submissions: scoped.filter((e) => e.submission).length,
    submissionsAccepted: scoped.filter((e) => e.submission?.ingestStatus === "accepted").length,
    incomplete: scoped.filter((e) => e.completeness.missing.length),
    categoriesPresent: scoped.reduce((n, e) => n + e.completeness.present.length, 0),
    families: new Set(signal.map((f) => f.family)).size,
    verified: signal.filter((f) => f.trust === "verified").length,
    failed: signal.filter((f) => f.trust === "failed").length,
    withEvidence: signal.filter((f) => f.evidenceCount > 0).length,
    receipts: receipts.filter((r) => signalIds.has(r.subjectId) || runIds.has(r.subjectId)).length,
    decided: new Set(core.decisions.filter((d) => signalIds.has(d.findingId)).map((d) => d.findingId)).size,
    runs: runs.length,
    runsCompleted: runs.filter((r) => r.status === "completed").length,
    runsVerified: runs.filter((r) => core.verifications.get(r.id)?.run?.ok).length,
    jobs: scopedJobs.length,
    jobsCompleted: scopedJobs.filter((j) => j.status === "completed").length,
    observations: scopedObs.length,
    abstained: scopedObs.filter((o) => o.state === "insufficient_data").length,
    audit,
    originKind: src.origin().kind,
  };
}

/** One overview row: a ratio drawn as a bar, or a plain state. */
export interface OverviewRow {
  label: string;
  value: number | null;
  max: number | null;
  text?: string;
  /** "risk": higher is worse (orange); "coverage": higher is better (purple) */
  sense: "risk" | "coverage" | "neutral";
  muted?: boolean;
}

export interface Overview {
  title: string;
  caption: string;
  footnote: string;
  rows: OverviewRow[];
}

const CAPABILITIES: Array<{ label: string; dimension: RiskDimensionName | null }> = [
  { label: "Threat Detection", dimension: "detection_gap" },
  { label: "Investigation Depth", dimension: "investigation_quality" },
  { label: "Escalation Discipline", dimension: "escalation_discipline" },
  { label: "Incident Response", dimension: null },
  { label: "Security Operations", dimension: null },
  { label: "Governance and Oversight", dimension: null },
  { label: "Operational Discipline", dimension: null },
  { label: "Cyber Resilience", dimension: null },
];

const ratio = (label: string, value: number, max: number, sense: OverviewRow["sense"] = "coverage"): OverviewRow => ({ label, value, max, sense });
const state = (label: string, text: string, muted = false): OverviewRow => ({ label, value: null, max: null, text, sense: "neutral", muted });

export function buildOverview(kind: OverviewKind, d: WorkbenchData): Overview {
  const n = d.scoped.length;
  switch (kind) {
    case "capability":
      return {
        title: "Capability overview",
        caption: "Observed risk, lower is better",
        footnote: `Mean of the backend risk dimension of the same name across ${n} entities.`,
        rows: CAPABILITIES.map((c) => {
          if (!c.dimension) return state(c.label, "Not assessed", true);
          const ds = d.scoped.map((e) => e.risk?.dimensions.find((x) => x.name === c.dimension)).filter((x) => x !== undefined);
          if (!ds.length) return state(c.label, "No data for this period", true);
          return ratio(c.label, ds.reduce((s, x) => s + x.score, 0) / ds.length, ds[0].weight, "risk");
        }),
      };
    case "analytical":
      return {
        title: "Analytical coverage",
        caption: "Coverage, higher is better",
        footnote: "Worker jobs, runs and submissions for the selected period.",
        rows: [
          ratio("Worker jobs completed", d.jobsCompleted, d.jobs),
          ratio("Analysis runs completed", d.runsCompleted, d.runs),
          ratio("Detector families signalled", d.families, DETECTOR_FAMILY_COUNT, "neutral"),
          ratio("Evidence categories submitted", d.categoriesPresent, n * EVIDENCE_CATEGORIES.length),
          ratio("Findings with source records", d.withEvidence, d.signal.length),
          d.observations ? ratio("Worker abstentions", d.abstained, d.observations, "neutral") : state("Worker abstentions", "No data for this period", true),
        ],
      };
    case "traceability":
      return {
        title: "Trust and traceability",
        caption: "Verified from the stored records",
        footnote: "ML-DSA-65 over SHA3-256; verification detects tampering when it runs.",
        rows: [
          ratio("Findings verified", d.verified, d.signal.length),
          ratio("Runs verified", d.runsVerified, d.runs),
          ratio("Records with a receipt", d.receipts, d.signal.length + d.runs),
          ratio("Findings with source records", d.withEvidence, d.signal.length),
          d.audit && d.audit.reviews_checked ? ratio("Decisions bound to digest", d.audit.reviews_ok, d.audit.reviews_checked) : state("Decisions bound to digest", "No decisions yet", true),
          d.audit?.ledger_integrity ? state("Decision ledger", d.audit.ledger_integrity.chain_ok ? "Chain intact" : "Chain broken") : state("Decision ledger", "Not available", true),
        ],
      };
    case "platform":
      return {
        title: "Platform posture",
        caption: "Portfolio, trust and access",
        footnote: `Data source: ${d.originKind === "fixture" ? "development fixture" : "live backend"}.`,
        rows: [
          ratio("Entities with a completed run", d.scoped.filter((e) => e.run?.status === "completed").length, n),
          ratio("Submissions accepted", d.submissionsAccepted, d.submissions),
          ratio("Evidence categories submitted", d.categoriesPresent, n * EVIDENCE_CATEGORIES.length),
          ratio("Runs verified", d.runsVerified, d.runs),
          d.audit ? state("Trust audit", d.audit.fully_compliant ? "Compliant" : "Exceptions found") : state("Trust audit", "Not available", true),
          state("Identity management", "Not connected", true),
        ],
      };
  }
}

export function missingCategories(e: EntityView): string {
  return e.completeness.missing.map((c) => CATEGORY_LABEL[c].toLowerCase()).join(", ");
}
