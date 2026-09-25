/**
 * Backend adapter: calls the SAT-SA HTTP API described in docs/API_CONTRACT.md.
 *
 * Those endpoints are a CONTRACT for the backend to implement; as of this
 * commit the FastAPI app only serves /api/entities and
 * /api/entities/{id}/risk. Until the rest exist, run the UI with
 * SATSA_DATA_SOURCE=fixture (the default).
 *
 * Server-only: the session credential is forwarded from the incoming
 * request's cookie and never exposed to client JavaScript.
 */
import "server-only";

import { cookies } from "next/headers";
import type { FindingQuery, SatsaDataSource } from "@/lib/api/source";
import { SESSION_COOKIE } from "@/lib/auth/constants";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
  ) {
    super(`SAT-SA API ${path} responded ${status}`);
  }
}

export function createHttpSource(baseUrl: string): SatsaDataSource {
  const base = baseUrl.replace(/\/$/, "");

  async function get<T>(path: string, { nullOn404 = false } = {}): Promise<T> {
    const jar = await cookies();
    const credential = jar.get(SESSION_COOKIE)?.value;
    const res = await fetch(`${base}${path}`, {
      headers: {
        Accept: "application/json",
        ...(credential ? { Authorization: `Bearer ${credential}` } : {}),
      },
      cache: "no-store",
    });
    if (nullOn404 && res.status === 404) return null as T;
    if (!res.ok) throw new ApiError(res.status, path);
    return (await res.json()) as T;
  }

  const qs = (params: Record<string, string | undefined>) => {
    const entries = Object.entries(params).filter((e): e is [string, string] => Boolean(e[1]));
    return entries.length ? `?${new URLSearchParams(entries)}` : "";
  };

  return {
    origin: () => ({ kind: "api", baseUrl: base }),

    listEntities: () => get("/api/v1/entities"),
    getEntity: (id) => get(`/api/v1/entities/${encodeURIComponent(id)}`, { nullOn404: true }),
    listAssessments: (entityId) => get(`/api/v1/assessments${qs({ entity_id: entityId })}`),
    listSubmissions: (entityId) => get(`/api/v1/submissions${qs({ entity_id: entityId })}`),

    listRuns: (entityId) => get(`/api/v1/runs${qs({ entity_id: entityId })}`),
    listJobs: (runId) => get(`/api/v1/jobs${qs({ run_id: runId })}`),
    listObservations: (runId) => get(`/api/v1/observations${qs({ run_id: runId })}`),

    listFindings: (q?: FindingQuery) =>
      get(`/api/v1/findings${qs({ entity_id: q?.entityId, run_id: q?.runId, state: q?.state })}`),
    getFinding: (id) => get(`/api/v1/findings/${encodeURIComponent(id)}`, { nullOn404: true }),

    getRiskProfile: (entityId) => get(`/api/v1/entities/${encodeURIComponent(entityId)}/risk`, { nullOn404: true }),
    listEntityPriorities: () => get("/api/v1/priorities/entities"),
    getRiskWeights: () => get("/api/v1/risk/weights"),

    listReviewDecisions: (findingId) => get(`/api/v1/reviews${qs({ finding_id: findingId })}`),

    listTrustReceipts: (subjectId) => get(`/api/v1/trust/receipts${qs({ subject_id: subjectId })}`),
    getRunVerification: (runId) => get(`/api/v1/runs/${encodeURIComponent(runId)}/verification`, { nullOn404: true }),
    getMetaAudit: () => get("/api/v1/trust/audit", { nullOn404: true }),

    listSourceRecords: (ids) => get(`/api/v1/source-records${qs({ ids: ids?.join(",") })}`),
    getSecurityData: (entityId) => get(`/api/v1/security-data${qs({ entity_id: entityId })}`),

    listAgents: () => get("/api/v1/agents"),
    getSupervisorDecision: (runId) => get(`/api/v1/runs/${encodeURIComponent(runId)}/supervisor-decision`, { nullOn404: true }),
    getValidation: () => get("/api/v1/validation", { nullOn404: true }),
  };
}
