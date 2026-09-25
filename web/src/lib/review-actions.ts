"use server";

import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";
import { isFixtureMode } from "@/lib/api";
import { SESSION_COOKIE } from "@/lib/auth/constants";
import type { BackendReviewAction } from "@/lib/types/domain";

export interface RecordReviewResult {
  ok: boolean;
  error?: string;
}

/**
 * Backend mode: record a supervisory decision.
 * Contract: POST /api/v1/findings/{id}/reviews
 *   {action, reason, finding_content_digest} -> 201 ReviewDecision | 401 | 403 | 409 (digest changed)
 * The backend binds the decision to the finding's live content digest and
 * mirrors it into the hash-chained decision ledger (ReviewService.record).
 */
export async function recordReview(input: {
  findingId: string;
  action: BackendReviewAction;
  reason: string;
  findingContentDigest: string;
}): Promise<RecordReviewResult> {
  if (isFixtureMode()) return { ok: false, error: "No backend is connected; development decisions stay in this browser." };
  if (!input.reason.trim()) return { ok: false, error: "A rationale is required." };

  const base = process.env.SATSA_API_BASE_URL?.replace(/\/$/, "");
  const credential = (await cookies()).get(SESSION_COOKIE)?.value;
  const res = await fetch(`${base}/api/v1/findings/${encodeURIComponent(input.findingId)}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(credential ? { Authorization: `Bearer ${credential}` } : {}) },
    body: JSON.stringify({ action: input.action, reason: input.reason, finding_content_digest: input.findingContentDigest }),
    cache: "no-store",
  }).catch(() => null);

  if (!res) return { ok: false, error: "The SAT-SA service could not be reached." };
  if (res.status === 403) return { ok: false, error: "Your role cannot record decisions." };
  if (res.status === 409) return { ok: false, error: "The finding changed since you opened it. Reload and review again." };
  if (!res.ok) return { ok: false, error: `The decision was not recorded (${res.status}).` };
  revalidatePath(`/workbench/findings/${input.findingId}`);
  return { ok: true };
}
