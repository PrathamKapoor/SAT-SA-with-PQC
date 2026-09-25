import type { Entity, NciipcDimensionScore } from "../data/entities";
import type { QueueItem } from "../data/reviewQueue";
import type { AuditLedgerEntry } from "../data/governance";
import { governanceConfig } from "../data/governance";
import { findings } from "../data/findings";
import { submissions } from "../data/submissions";

export const ALL_COHORTS = "All Cohorts";

export function entitiesInCohort(entities: Entity[], cohort: string): Entity[] {
  return cohort === ALL_COHORTS ? entities : entities.filter((e) => e.cohort === cohort);
}

export function dimensionStatus(score: number): NciipcDimensionScore["status"] {
  if (score < 50) return "critical_gap";
  if (score < 70) return "attention";
  return "satisfactory";
}

export function averageDimensions(entities: Entity[]): NciipcDimensionScore[] {
  if (entities.length === 0) return [];
  return entities[0].nciipcDimensions.map((dim, idx) => {
    const total = entities.reduce((sum, e) => sum + (e.nciipcDimensions[idx]?.score ?? 0), 0);
    const findingCount = entities.reduce((sum, e) => sum + (e.nciipcDimensions[idx]?.findingCount ?? 0), 0);
    const score = Math.round(total / entities.length);
    return { ...dim, score, findingCount, status: dimensionStatus(score) };
  });
}

export function submissionHasGap(s: (typeof submissions)[number]): boolean {
  return s.schemaValidationStatus !== "passed" || s.assetInventoryStatus === "stale" || s.recordsQuarantined > 0;
}

export interface WorkbenchSummary {
  entities: number;
  attentionEntities: number;
  findings: number;
  severeFindings: number;
  queueTotal: number;
  queueOpen: number;
  queueReviewed: number;
  nextQueueItem: QueueItem | null;
  submissions: number;
  submissionGaps: number;
  cohortsCompared: number;
  ledgerBlocks: number;
  ledgerVerified: boolean;
}

export function summarizeWorkbench(
  entities: Entity[],
  queueItems: QueueItem[],
  auditEntries: AuditLedgerEntry[],
  cohort: string,
): WorkbenchSummary {
  const scoped = entitiesInCohort(entities, cohort);
  const slugs = new Set(scoped.map((e) => e.slug));
  const inScope = (slug: string) => slugs.has(slug);

  const scopedFindings = findings.filter((f) => inScope(f.entitySlug));
  const scopedQueue = queueItems.filter((q) => inScope(q.entitySlug));
  const openQueue = scopedQueue.filter((q) => q.currentDisposition === "open");
  const scopedSubmissions = submissions.filter((s) => inScope(s.entitySlug));

  return {
    entities: scoped.length,
    attentionEntities: scoped.filter((e) => e.band === "high" || e.band === "critical").length,
    findings: scopedFindings.length,
    severeFindings: scopedFindings.filter((f) => f.severity === "critical" || f.severity === "high").length,
    queueTotal: scopedQueue.length,
    queueOpen: openQueue.length,
    queueReviewed: scopedQueue.length - openQueue.length,
    nextQueueItem: [...openQueue].sort((a, b) => a.rank - b.rank)[0] ?? null,
    submissions: scopedSubmissions.length,
    submissionGaps: scopedSubmissions.filter(submissionHasGap).length,
    cohortsCompared: new Set(scoped.map((e) => e.cohort)).size,
    ledgerBlocks: auditEntries.length,
    ledgerVerified:
      governanceConfig.ledgerIntegrityStatus === "intact_verified" &&
      governanceConfig.tamperCount === 0 &&
      auditEntries.every((e) => e.pqcSignatureVerified),
  };
}
