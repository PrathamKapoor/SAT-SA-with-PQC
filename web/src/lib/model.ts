import "server-only";

import { cache } from "react";
import type { ReviewStatus, TrustState } from "@/components/ui/badges";
import { getSource } from "@/lib/api";
import { prose } from "@/lib/domain/format";
import { STATUS_FOR_ACTION } from "@/lib/domain/review";
import { familyOf, type FindingFamily } from "@/lib/domain/labels";
import {
  EVIDENCE_CATEGORIES,
  type AnalysisRun,
  type Assessment,
  type Entity,
  type EntityPriority,
  type EntityRiskProfile,
  type Finding,
  type ReviewDecision,
  type RunVerification,
  type Submission,
} from "@/lib/types/domain";

/**
 * View models assembled from the data source. Pure joins over backend
 * records: nothing here computes a score, a severity or a verdict the
 * backend did not produce.
 */

export interface FindingView extends Finding {
  entityName: string;
  family: FindingFamily;
  trust: TrustState;
  trustReason: string;
  reviewStatus: ReviewStatus;
  latestDecision: ReviewDecision | null;
  evidenceCount: number;
}

export interface EntityView {
  entity: Entity;
  assessment: Assessment | null;
  submission: Submission | null;
  run: AnalysisRun | null;
  risk: EntityRiskProfile | null;
  priority: EntityPriority | null;
  priorityRank: number | null;
  findings: FindingView[];
  /** evidence categories present / expected (six SIH categories) */
  completeness: { present: string[]; missing: string[] };
  trust: TrustState;
}

function trustFor(findingId: string, runId: string, verifications: Map<string, RunVerification | null>): [TrustState, string] {
  const v = verifications.get(runId);
  if (!v) return ["unknown", "No verification result for this run"];
  const f = v.findings.find((x) => x.finding_id === findingId);
  if (!f) return ["unsigned", "No trust receipt for this finding"];
  return f.ok ? ["verified", "Signature and live digest match"] : ["failed", f.reason];
}

export const loadCore = cache(async () => {
  const src = getSource();
  const [entities, findings, decisions, runs, assessments, submissions, priorities] = await Promise.all([
    src.listEntities(),
    src.listFindings(),
    src.listReviewDecisions(),
    src.listRuns(),
    src.listAssessments(),
    src.listSubmissions(),
    src.listEntityPriorities(),
  ]);
  const verifications = new Map<string, RunVerification | null>(
    await Promise.all(runs.map(async (r) => [r.id, await src.getRunVerification(r.id)] as const)),
  );
  return { entities, findings, decisions, runs, assessments, submissions, priorities, verifications };
});

export const loadFindingViews = cache(async (): Promise<FindingView[]> => {
  const { entities, findings, decisions, verifications } = await loadCore();
  const names = new Map(entities.map((e) => [e.id, e.displayName]));
  return findings.map((f) => {
    const [trust, trustReason] = trustFor(f.id, f.runId, verifications);
    const latest = decisions.filter((d) => d.findingId === f.id).sort((a, b) => b.occurredAt - a.occurredAt)[0] ?? null;
    return {
      ...f,
      rationale: prose(f.rationale),
      limitations: prose(f.limitations),
      recommendation: f.recommendation
        ? { ...f.recommendation, reason: prose(f.recommendation.reason), limitations: prose(f.recommendation.limitations) }
        : null,
      entityName: names.get(f.entityId) ?? f.entityId,
      family: familyOf(f.ruleOrCategory),
      trust,
      trustReason,
      reviewStatus: latest ? STATUS_FOR_ACTION[latest.action] : "awaiting",
      latestDecision: latest,
      evidenceCount: f.evidenceRefs.length,
    };
  });
});

/** Findings ordered the way the backend prioritizes them: priority score, then confidence. */
export function byPriority(a: FindingView, b: FindingView) {
  return (b.priorityScore ?? 0) - (a.priorityScore ?? 0) || (b.confidence?.overall ?? 0) - (a.confidence?.overall ?? 0);
}

export const loadEntityViews = cache(async (): Promise<EntityView[]> => {
  const core = await loadCore();
  const src = getSource();
  const findingViews = await loadFindingViews();
  const risks = new Map(await Promise.all(core.entities.map(async (e) => [e.id, await src.getRiskProfile(e.id)] as const)));
  const rank = new Map(core.priorities.map((p, i) => [p.entity_id, i + 1]));

  return core.entities
    .map((entity) => {
      const risk = risks.get(entity.id) ?? null;
      const runs = core.runs.filter((r) => r.entityId === entity.id).sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0));
      const run = (risk?.run_id && runs.find((r) => r.id === risk.run_id)) || runs[0] || null;
      const assessment = core.assessments.find((a) => a.id === run?.assessmentId) ?? core.assessments.find((a) => a.entityId === entity.id) ?? null;
      const submission = core.submissions.find((s) => s.assessmentId === assessment?.id) ?? null;
      const findings = findingViews.filter((f) => f.entityId === entity.id && (!run || f.runId === run.id)).sort(byPriority);
      const counts = submission?.declaredCounts ?? {};
      const present = EVIDENCE_CATEGORIES.filter((c) => (counts[c] ?? 0) > 0);
      const v = run ? core.verifications.get(run.id) : null;
      const trust: TrustState = !v || !v.run ? "unknown" : v.run.ok && v.findings.every((f) => f.ok) ? "verified" : "failed";
      return {
        entity,
        assessment,
        submission,
        run,
        risk,
        priority: core.priorities.find((p) => p.entity_id === entity.id) ?? null,
        priorityRank: rank.get(entity.id) ?? null,
        findings,
        completeness: { present, missing: EVIDENCE_CATEGORIES.filter((c) => !present.includes(c)) },
        trust,
      };
    })
    .sort((a, b) => (a.priorityRank ?? 99) - (b.priorityRank ?? 99));
});
