"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { all, apiBase, createSession, deleteSession, listOrganizations, ORG_COOKIE, SESSION_COOKIE } from "@/lib/api/client";
import { ApiError, present } from "@/lib/api/errors";

export interface SignInState {
  error: string | null;
}

const secure = () => process.env.NODE_ENV === "production" && process.env.SATSA_INSECURE_COOKIES !== "true";

/**
 * Exchange an issued credential for a backend session (POST /api/v1/session).
 * Only the session token is stored, in an HttpOnly cookie; the credential is
 * discarded after this request.
 */
export async function signInWithCredential(_prev: SignInState, form: FormData): Promise<SignInState> {
  if (!apiBase()) return { error: "This deployment has no SAT-SA service configured (SATSA_API_BASE_URL)." };
  const credential = String(form.get("credential") ?? "").trim();
  if (!credential) return { error: "Enter your issued credential." };
  try {
    const { token, session } = await createSession(credential);
    const jar = await cookies();
    jar.set(SESSION_COOKIE, token, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure: secure(),
      ...(session.expires_at ? { expires: new Date(session.expires_at * 1000) } : {}),
    });
    jar.delete(ORG_COOKIE);
    const memberships = (await all((q) => listOrganizations(token, q.offset))).filter((o) => o.status === "active");
    if (memberships.length === 1) jar.set(ORG_COOKIE, memberships[0].id, { httpOnly: true, sameSite: "lax", path: "/", secure: secure() });
  } catch (error) {
    if (error instanceof ApiError) {
      if (error.info.status === 401) return { error: "Credential not recognised." };
      return { error: present(error.info).title + (error.info.requestId ? ` (request ${error.info.requestId})` : "") };
    }
    throw error;
  }
  redirect("/workbench");
}

/** Revoke the backend session (DELETE /api/v1/session with the session token), then clear the cookies. */
export async function signOut(): Promise<void> {
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (token) {
    try {
      await deleteSession(token);
    } catch {
      /* already expired or unreachable: the local session is cleared either way */
    }
  }
  jar.delete(SESSION_COOKIE);
  jar.delete(ORG_COOKIE);
  redirect("/login");
}

/**
 * Switch the active organization after confirming an active membership in it
 * (GET /api/v1/organizations). The backend re-checks membership on every call.
 */
export async function selectOrganization(form: FormData): Promise<void> {
  const id = String(form.get("organization") ?? "");
  const jar = await cookies();
  const token = jar.get(SESSION_COOKIE)?.value;
  if (!token) redirect("/login");
  let allowed = false;
  try {
    allowed = (await all((q) => listOrganizations(token, q.offset))).some((o) => o.id === id && o.status === "active");
  } catch (error) {
    if (error instanceof ApiError && error.info.status === 401) redirect("/logout?reason=expired");
    redirect("/organization?reason=unreachable");
  }
  if (!allowed) redirect("/organization?reason=unavailable");
  jar.set(ORG_COOKIE, id, { httpOnly: true, sameSite: "lax", path: "/", secure: secure() });
  redirect("/workbench");
}
