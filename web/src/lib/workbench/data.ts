import "server-only";

import { cache } from "react";
import { all, api } from "@/lib/api/client";
import type { Entity, EntityPriority, Finding } from "@/lib/api/types";

/**
 * Joins over backend collections that several pages need. Pure lookups:
 * nothing here scores, ranks or classifies. Order and scores come from
 * GET /api/v1/priorities.
 */
export interface Portfolio {
  entities: Entity[];
  priorities: EntityPriority[];
  entity: Map<string, Entity>;
  priority: Map<string, EntityPriority>;
  rank: Map<string, number>;
}

export const loadPortfolio = cache(async (): Promise<Portfolio> => {
  const [entities, priorities] = await Promise.all([all((q) => api.entities(q)), all((q) => api.priorities(q))]);
  return {
    entities,
    priorities,
    entity: new Map(entities.map((e) => [e.id, e])),
    priority: new Map(priorities.map((p) => [p.entity_id, p])),
    rank: new Map(priorities.map((p, i) => [p.entity_id, i + 1])),
  };
});

export const entityName = (portfolio: Portfolio, id: string) => portfolio.entity.get(id)?.display_name ?? id;

/** All findings of one run (bounded by the run's worker output). */
export const loadRunFindings = cache(async (runId: string): Promise<Finding[]> => all((q) => api.findings(runId, q)));

/** Findings of each entity's current run: the run the priority ranking used. */
export const loadCurrentFindings = cache(async (): Promise<Array<{ finding: Finding; priority: EntityPriority }>> => {
  const portfolio = await loadPortfolio();
  const perRun = await Promise.all(portfolio.priorities.map(async (p) => (await loadRunFindings(p.run_id)).map((finding) => ({ finding, priority: p }))));
  return perRun.flat();
});

/** Signal findings first, then by the backend's overall confidence. */
export function bySignalThenConfidence(a: Finding, b: Finding): number {
  const s = Number(b.state === "signal") - Number(a.state === "signal");
  return s || (b.confidence?.overall ?? 0) - (a.confidence?.overall ?? 0);
}
