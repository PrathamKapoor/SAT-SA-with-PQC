"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { isFixtureMode } from "@/lib/api";
import { DEV_SESSION_COOKIE, SESSION_COOKIE } from "./constants";
import { isRole } from "./permissions";

export interface SignInState {
  error: string | null;
}

const COOKIE_OPTS = { httpOnly: true, sameSite: "lax" as const, path: "/", secure: process.env.NODE_ENV === "production" };

function safeNext(value: FormDataEntryValue | null): string {
  const next = typeof value === "string" ? value : "";
  return next.startsWith("/workbench") ? next : "/workbench";
}

/**
 * Backend mode: exchange an issued credential for a session.
 * Contract: POST /api/v1/session {credential} -> 200 {identity_id, name, role} | 401 | 429.
 */
export async function signInWithCredential(_prev: SignInState, form: FormData): Promise<SignInState> {
  if (isFixtureMode()) {
    return { error: "Backend authentication is not connected in this environment. Use a development session." };
  }
  const credential = String(form.get("credential") ?? "").trim();
  if (!credential) return { error: "Enter your issued credential." };

  const base = process.env.SATSA_API_BASE_URL?.replace(/\/$/, "");
  let res: Response;
  try {
    res = await fetch(`${base}/api/v1/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ credential }),
      cache: "no-store",
    });
  } catch {
    return { error: "The SAT-SA service could not be reached." };
  }
  if (res.status === 429) return { error: "Too many attempts. Wait a moment and try again." };
  if (!res.ok) return { error: "Credential not recognised." };

  (await cookies()).set(SESSION_COOKIE, credential, COOKIE_OPTS);
  redirect(safeNext(form.get("next")));
}

/** Fixture mode only: choose a role to explore the interface. Verifies nothing. */
export async function startDevelopmentSession(form: FormData): Promise<void> {
  if (!isFixtureMode()) redirect("/login");
  const role = form.get("role");
  if (!isRole(role)) redirect("/login");
  (await cookies()).set(DEV_SESSION_COOKIE, role, COOKIE_OPTS);
  redirect(safeNext(form.get("next")));
}

export async function signOut(): Promise<void> {
  const jar = await cookies();
  jar.delete(SESSION_COOKIE);
  jar.delete(DEV_SESSION_COOKIE);
  redirect("/login");
}
