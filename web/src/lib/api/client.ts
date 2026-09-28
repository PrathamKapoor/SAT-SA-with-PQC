import "server-only";

import { cookies } from "next/headers";
import { ApiError, type ApiErrorInfo } from "./errors";
import { requestOrganization } from "./org-scope";
import type {
  Artifact,
  Assessment,
  AuditEvent,
  CanonicalRecord,
  Decision,
  DecisionAction,
  Entity,
  EntityPriority,
  ErrorEnvelope,
  Evidence,
  EvidenceCategory,
  Finding,
  Invitation,
  Member,
  MembershipRole,
  Organization,
  Page,
  Receipt,
  Recommendation,
  Risk,
  Run,
  RunStatus,
  Session,
  Step,
  Submission,
  Validation,
  Verification,
  Version,
} from "./types";

/**
 * Server-side client for the SAT-SA API (docs/API_CONTRACT.md). Every call is
 * made from Next.js server code with `Authorization: Bearer <session token>`;
 * tenant calls add `X-Organization-ID`. The browser never holds a token.
 */

/** HttpOnly cookie holding the backend session token (never the credential). */
export const SESSION_COOKIE = "satsa_session";
/** HttpOnly cookie holding the selected organization id. */
export const ORG_COOKIE = "satsa_org";
/** The backend's session cookie, read once from the login response. */
const BACKEND_SESSION_COOKIE = "satsa_api_session";

export function apiBase(): string | null {
  const base = process.env.SATSA_API_BASE_URL?.trim();
  return base ? base.replace(/\/$/, "") : null;
}

interface CallOptions {
  method?: "GET" | "POST" | "DELETE";
  token?: string | null;
  organization?: string | null;
  json?: unknown;
  form?: FormData;
  idempotencyKey?: string;
  query?: Record<string, string | number | undefined | null>;
}

function url(path: string, query?: CallOptions["query"]): string {
  const base = apiBase();
  if (!base) throw new ApiError({ status: 0, code: "NETWORK_ERROR", message: "SATSA_API_BASE_URL is not configured", requestId: "", details: [] });
  const params = Object.entries(query ?? {}).filter((e): e is [string, string | number] => e[1] !== undefined && e[1] !== null && e[1] !== "");
  return `${base}${path}${params.length ? `?${new URLSearchParams(params.map(([k, v]) => [k, String(v)]))}` : ""}`;
}

async function raw(path: string, options: CallOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  if (options.organization) headers["X-Organization-ID"] = options.organization;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;
  let body: BodyInit | undefined;
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.json);
  } else if (options.form) {
    body = options.form;
  }
  try {
    return await fetch(url(path, options.query), { method: options.method ?? "GET", headers, body, cache: "no-store" });
  } catch (cause) {
    if (cause instanceof ApiError) throw cause;
    throw new ApiError({ status: 0, code: "NETWORK_ERROR", message: "The SAT-SA service could not be reached", requestId: "", details: [] });
  }
}

async function errorFrom(res: Response): Promise<ApiErrorInfo> {
  const requestId = res.headers.get("X-Request-ID") ?? "";
  try {
    const body = (await res.json()) as Partial<ErrorEnvelope>;
    if (body.error) {
      return {
        status: res.status,
        code: body.error.code,
        message: body.error.message,
        requestId: body.error.request_id || requestId,
        details: Array.isArray(body.error.details) ? body.error.details : [],
      };
    }
  } catch {
    /* not an error envelope */
  }
  return { status: res.status, code: res.status >= 500 ? "INTERNAL_ERROR" : `HTTP_${res.status}`, message: res.statusText, requestId, details: [] };
}

async function call<T>(path: string, options: CallOptions = {}): Promise<T> {
  const res = await raw(path, options);
  if (!res.ok) throw new ApiError(await errorFrom(res));
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/* ---------- session (no organization) ---------- */

/** Exchange a credential for a backend session. The session token comes only from Set-Cookie. */
export async function createSession(credential: string): Promise<{ token: string; session: Session }> {
  const res = await raw("/api/v1/session", { method: "POST", json: { credential } });
  if (!res.ok) throw new ApiError(await errorFrom(res));
  const session = (await res.json()) as Session;
  const token = res.headers
    .getSetCookie()
    .map((c) => c.split(";")[0])
    .find((c) => c.startsWith(`${BACKEND_SESSION_COOKIE}=`))
    ?.slice(BACKEND_SESSION_COOKIE.length + 1);
  if (!token) throw new ApiError({ status: 502, code: "INTERNAL_ERROR", message: "The SAT-SA service did not issue a session", requestId: res.headers.get("X-Request-ID") ?? "", details: [] });
  return { token: decodeURIComponent(token), session };
}

export const readSession = (token: string) => call<Session>("/api/v1/session", { token });
/** Revokes the session token only. Never call with a raw credential. */
export const deleteSession = (token: string) => call<void>("/api/v1/session", { method: "DELETE", token });
export const listOrganizations = (token: string, offset = 0) =>
  call<Page<Organization>>("/api/v1/organizations", { token, query: { limit: 200, offset } });
export const health = async () => {
  const [live, ready] = await Promise.all([raw("/health/live", {}), raw("/health/ready", {})]);
  return { live: live.ok, ready: ready.ok, readyStatus: ready.status };
};

/* ---------- tenant calls ---------- */

async function tenantAuth(): Promise<{ token: string | null; organization: string | null }> {
  const jar = await cookies();
  return { token: jar.get(SESSION_COOKIE)?.value ?? null, organization: requestOrganization().id ?? jar.get(ORG_COOKIE)?.value ?? null };
}

async function tget<T>(path: string, query?: CallOptions["query"]): Promise<T> {
  return call<T>(path, { ...(await tenantAuth()), query });
}

async function tpost<T>(path: string, options: Omit<CallOptions, "method" | "token" | "organization"> = {}): Promise<T> {
  return call<T>(path, { ...(await tenantAuth()), ...options, method: "POST" });
}

export interface PageQuery {
  limit?: number;
  offset?: number;
}

const pq = (q: PageQuery = {}) => ({ limit: q.limit ?? 50, offset: q.offset ?? 0 });
const id = encodeURIComponent;

/** Fetch every page of a bounded collection. `max` caps the rows read. */
export async function all<T>(fetchPage: (q: PageQuery) => Promise<Page<T>>, max = 2000): Promise<T[]> {
  const rows: T[] = [];
  for (let offset = 0; offset < max; offset += 200) {
    const page = await fetchPage({ limit: 200, offset });
    rows.push(...page.items);
    if (!page.has_more) break;
  }
  return rows;
}

/** A 404 read of something not produced yet (risk, decision, receipt) is `null`, not an error. */
export async function orNull<T>(promise: Promise<T>): Promise<T | null> {
  try {
    return await promise;
  } catch (error) {
    if (error instanceof ApiError && error.info.status === 404) return null;
    throw error;
  }
}

export const api = {
  members: (q?: PageQuery) => tget<Page<Member>>("/api/v1/members", pq(q)),
  inviteMember: (body: { name: string; email: string; role: MembershipRole }) => tpost<Invitation>("/api/v1/members", { json: body }),
  revokeMember: async (userId: string) => call<void>(`/api/v1/members/${id(userId)}`, { ...(await tenantAuth()), method: "DELETE" }),

  entities: (q?: PageQuery) => tget<Page<Entity>>("/api/v1/entities", pq(q)),
  entity: (entityId: string) => tget<Entity>(`/api/v1/entities/${id(entityId)}`),
  createEntity: (body: { display_name: string; sector?: string; environment_class?: string }) => tpost<Entity>("/api/v1/entities", { json: body }),

  assessments: (q?: PageQuery & { entity_id?: string }) => tget<Page<Assessment>>("/api/v1/assessments", { ...pq(q), entity_id: q?.entity_id }),
  assessment: (assessmentId: string) => tget<Assessment>(`/api/v1/assessments/${id(assessmentId)}`),
  createAssessment: (body: { entity_id: string; period_start: number; period_end: number }) => tpost<Assessment>("/api/v1/assessments", { json: body }),

  submissions: (q?: PageQuery & { entity_id?: string }) => tget<Page<Submission>>("/api/v1/submissions", { ...pq(q), entity_id: q?.entity_id }),
  submission: (submissionId: string) => tget<Submission>(`/api/v1/submissions/${id(submissionId)}`),
  createSubmission: (assessmentId: string, key: string) => tpost<Submission>("/api/v1/submissions", { json: { assessment_id: assessmentId }, idempotencyKey: key }),
  versions: (submissionId: string, q?: PageQuery) => tget<Page<Version>>(`/api/v1/submissions/${id(submissionId)}/versions`, pq(q)),
  createVersion: (submissionId: string, key: string) => tpost<Version>(`/api/v1/submissions/${id(submissionId)}/versions`, { idempotencyKey: key }),
  version: (versionId: string) => tget<Version>(`/api/v1/versions/${id(versionId)}`),
  artifacts: (versionId: string, q?: PageQuery) => tget<Page<Artifact>>(`/api/v1/versions/${id(versionId)}/artifacts`, pq(q)),
  uploadArtifact: (versionId: string, category: EvidenceCategory, file: File, key: string) => {
    const form = new FormData();
    form.append("file", file, file.name);
    return tpost<Artifact>(`/api/v1/versions/${id(versionId)}/artifacts`, { form, idempotencyKey: key, query: { category } });
  },
  completeVersion: (versionId: string) => tpost<Version>(`/api/v1/versions/${id(versionId)}/complete`),
  validateVersion: (versionId: string) => tpost<Validation>(`/api/v1/versions/${id(versionId)}/validate`),
  validation: (versionId: string) => tget<Validation>(`/api/v1/versions/${id(versionId)}/validation`),
  summary: (versionId: string) => tget<{ version_id: string; counts: Partial<Record<EvidenceCategory, number>> }>(`/api/v1/versions/${id(versionId)}/summary`),
  records: (versionId: string, q?: PageQuery & { category?: EvidenceCategory }) =>
    tget<Page<CanonicalRecord>>(`/api/v1/versions/${id(versionId)}/records`, { ...pq(q), category: q?.category }),

  startRun: (versionId: string, mode: "graph" | "standard", key: string) =>
    tpost<Run>("/api/v1/runs", { json: { submission_version_id: versionId, execution_mode: mode }, idempotencyKey: key }),
  runs: (q?: PageQuery & { entity_id?: string; status?: RunStatus }) => tget<Page<Run>>("/api/v1/runs", { ...pq(q), entity_id: q?.entity_id, status: q?.status }),
  run: (runId: string) => tget<Run>(`/api/v1/runs/${id(runId)}`),
  cancelRun: (runId: string) => tpost<Run>(`/api/v1/runs/${id(runId)}/cancel`),
  steps: (runId: string, q?: PageQuery) => tget<Page<Step>>(`/api/v1/runs/${id(runId)}/steps`, pq(q)),
  findings: (runId: string, q?: PageQuery) => tget<Page<Finding>>(`/api/v1/runs/${id(runId)}/findings`, pq(q)),
  finding: (findingId: string) => tget<Finding>(`/api/v1/findings/${id(findingId)}`),
  evidence: (runId: string, q?: PageQuery) => tget<Page<Evidence>>(`/api/v1/runs/${id(runId)}/evidence`, pq(q)),
  risk: (runId: string) => tget<Risk>(`/api/v1/runs/${id(runId)}/risk`),
  priorities: (q?: PageQuery) => tget<Page<EntityPriority>>("/api/v1/priorities", pq(q)),
  recommendations: (runId: string, q?: PageQuery) => tget<Page<Recommendation>>(`/api/v1/runs/${id(runId)}/recommendations`, pq(q)),
  decision: (runId: string) => tget<Decision>(`/api/v1/runs/${id(runId)}/decision`),
  decide: (runId: string, action: DecisionAction, reason: string) => tpost<Decision>(`/api/v1/runs/${id(runId)}/decision`, { json: { action, reason } }),
  receipt: (runId: string) => tget<Receipt>(`/api/v1/runs/${id(runId)}/receipt`),
  verify: (runId: string) => tpost<Verification>(`/api/v1/runs/${id(runId)}/verify`),
  auditEvents: (q?: PageQuery & { run_id?: string }) => tget<Page<AuditEvent>>("/api/v1/audit/events", { ...pq(q), run_id: q?.run_id }),
};
