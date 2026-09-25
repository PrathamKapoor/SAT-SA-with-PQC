import "server-only";

import { cookies } from "next/headers";
import { isFixtureMode } from "@/lib/api";
import type { SessionUser } from "@/lib/types/domain";
import { DEV_SESSION_COOKIE, SESSION_COOKIE } from "./constants";
import { ROLE_LABEL, isRole } from "./permissions";

/**
 * Session abstraction.
 *
 * - fixture mode: a DEVELOPMENT session. The visitor picks a role on /login;
 *   nothing is verified and the UI says so on every page. It exists only so
 *   role-dependent screens can be explored before the backend is connected.
 * - api mode: the backend-issued credential (HttpOnly cookie) is resolved by
 *   GET /api/v1/session (docs/API_CONTRACT.md). The backend enforces access.
 */
export type SessionMode = "development" | "backend";

export interface Session {
  mode: SessionMode;
  user: SessionUser;
}

export function sessionMode(): SessionMode {
  return isFixtureMode() ? "development" : "backend";
}

export async function getSession(): Promise<Session | null> {
  const jar = await cookies();

  if (sessionMode() === "development") {
    const role = jar.get(DEV_SESSION_COOKIE)?.value;
    if (!isRole(role)) return null;
    return {
      mode: "development",
      user: { identityId: `development-${role}`, displayName: `${ROLE_LABEL[role]} (development)`, role },
    };
  }

  const credential = jar.get(SESSION_COOKIE)?.value;
  if (!credential) return null;
  const base = process.env.SATSA_API_BASE_URL?.replace(/\/$/, "");
  if (!base) return null;
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
