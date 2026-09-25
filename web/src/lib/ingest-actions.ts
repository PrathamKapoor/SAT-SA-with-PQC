"use server";

import { cookies } from "next/headers";
import { isFixtureMode } from "@/lib/api";
import { SESSION_COOKIE } from "@/lib/auth/constants";

export type IngestOutcome =
  | { ok: true; submissionId: string; entityId?: string; runId?: string }
  | { ok: false; error: string };

/**
 * Backend mode: forward a submission.
 * Contract: POST /api/v1/submissions (multipart: entity, sector, environment,
 *   periodStart, periodEnd, sourceSystem, one file part per category)
 *   -> 201 {submission_id, entity_id, assessment_id, ingest_status, counts, snapshot_digest}
 * Mirrors the existing FastAPI /ingest form handler (satsa/ui/__init__.py).
 */
export async function submitIngestion(form: FormData): Promise<IngestOutcome> {
  if (isFixtureMode()) return { ok: false, error: "No backend is connected; nothing was ingested." };
  const base = process.env.SATSA_API_BASE_URL?.replace(/\/$/, "");
  const credential = (await cookies()).get(SESSION_COOKIE)?.value;
  const res = await fetch(`${base}/api/v1/submissions`, {
    method: "POST",
    headers: credential ? { Authorization: `Bearer ${credential}` } : {},
    body: form,
    cache: "no-store",
  }).catch(() => null);
  if (!res) return { ok: false, error: "The SAT-SA service could not be reached." };
  if (res.status === 403) return { ok: false, error: "Your role cannot ingest submissions." };
  if (!res.ok) return { ok: false, error: `Ingestion was rejected (${res.status}).` };
  const body = (await res.json()) as { submission_id: string; entity_id?: string; run_id?: string };
  return { ok: true, submissionId: body.submission_id, entityId: body.entity_id, runId: body.run_id };
}
