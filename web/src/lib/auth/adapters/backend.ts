import "server-only";

import type { cookies } from "next/headers";
import { SESSION_COOKIE } from "../constants";
import { isRole } from "../permissions";
import type { Session } from "../session";

/**
 * BACKEND SESSION ADAPTER (production). The credential issued by a SAT-SA
 * administrator is held in an HttpOnly cookie and resolved by the backend:
 * GET /api/v1/session -> {identity_id, name, role}. See docs/API_CONTRACT.md.
 */
type Jar = Awaited<ReturnType<typeof cookies>>;

export async function readBackendSession(jar: Jar): Promise<Session | null> {
  const credential = jar.get(SESSION_COOKIE)?.value;
  const base = process.env.SATSA_API_BASE_URL?.replace(/\/$/, "");
  if (!credential || !base) return null;
  try {
    const res = await fetch(`${base}/api/v1/session`, {
      headers: { Authorization: `Bearer ${credential}`, Accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { identity_id: string; name: string; role: string };
    if (!isRole(body.role)) return null;
    return { mode: "backend", user: { identityId: body.identity_id, displayName: body.name, role: body.role } };
  } catch {
    return null;
  }
}

export type CredentialResult = { ok: true } | { ok: false; error: string };

/** POST /api/v1/session {credential} -> 200 | 401 | 429. */
export async function exchangeCredential(credential: string): Promise<CredentialResult> {
  const base = process.env.SATSA_API_BASE_URL?.replace(/\/$/, "");
  if (!base) return { ok: false, error: "Backend sign-in is not configured for this deployment." };
  let res: Response;
  try {
    res = await fetch(`${base}/api/v1/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ credential }),
      cache: "no-store",
    });
  } catch {
    return { ok: false, error: "The SAT-SA service could not be reached." };
  }
  if (res.status === 429) return { ok: false, error: "Too many attempts. Wait a moment and try again." };
  if (!res.ok) return { ok: false, error: "Credential not recognised." };
  return { ok: true };
}
