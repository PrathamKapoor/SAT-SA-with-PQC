import "server-only";

import type { cookies } from "next/headers";
import { DEV_SESSION_COOKIE } from "../constants";
import { devIdentity, type DevIdentity } from "../identities";
import type { Session } from "../session";

/**
 * DEVELOPMENT SESSION ADAPTER. Frontend only; never production authentication.
 *
 * The session is an HttpOnly cookie with no expiry, so it lasts for the
 * current browser session. It records the development principal, role,
 * display name and a marker. On every read it is checked against the fixed
 * development identity list, so an edited cookie cannot mint a new identity
 * or pair a principal with another role.
 *
 * This cookie is never forwarded to a backend: the API adapter only sends the
 * backend credential cookie (see src/lib/api/http.ts).
 */
const MARKER = "satsa-development-session/v1";

type Jar = Awaited<ReturnType<typeof cookies>>;

interface Payload {
  marker: string;
  principal: string;
  role: string;
  displayName: string;
  startedAt: number;
}

export function readDevelopmentSession(jar: Jar): Session | null {
  const raw = jar.get(DEV_SESSION_COOKIE)?.value;
  if (!raw) return null;
  let payload: Payload;
  try {
    payload = JSON.parse(Buffer.from(raw, "base64url").toString("utf8")) as Payload;
  } catch {
    return null;
  }
  const id = devIdentity(payload.principal);
  if (!id || payload.marker !== MARKER || payload.role !== id.role) return null;
  return { mode: "development", user: { identityId: id.principal, displayName: id.displayName, role: id.role } };
}

export function writeDevelopmentSession(jar: Jar, id: DevIdentity): void {
  const payload: Payload = { marker: MARKER, principal: id.principal, role: id.role, displayName: id.displayName, startedAt: Date.now() };
  jar.set(DEV_SESSION_COOKIE, Buffer.from(JSON.stringify(payload), "utf8").toString("base64url"), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    // no maxAge / expires: a browser-session cookie
  });
}
