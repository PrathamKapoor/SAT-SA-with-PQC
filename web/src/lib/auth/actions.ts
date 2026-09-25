"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { exchangeCredential } from "./adapters/backend";
import { writeDevelopmentSession } from "./adapters/development";
import { authAdapterKind } from "./config";
import { DEV_SESSION_COOKIE, SESSION_COOKIE } from "./constants";
import { devIdentity } from "./identities";

export interface SignInState {
  error: string | null;
}

/** Every role, development or backend, enters the same Workbench. */
const HOME = "/workbench";

/** Backend adapter only: exchange an issued credential for a session. */
export async function signInWithCredential(_prev: SignInState, form: FormData): Promise<SignInState> {
  if (authAdapterKind() !== "backend") {
    return { error: "Backend sign-in is not enabled here. Choose a development identity below." };
  }
  const credential = String(form.get("credential") ?? "").trim();
  if (!credential) return { error: "Enter your issued credential." };
  const result = await exchangeCredential(credential);
  if (!result.ok) return { error: result.error };
  (await cookies()).set(SESSION_COOKIE, credential, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: process.env.NODE_ENV === "production",
  });
  redirect(HOME);
}

/** Development adapter only: enter the application as a fixed development principal. */
export async function startDevelopmentSession(form: FormData): Promise<void> {
  if (authAdapterKind() !== "development") redirect("/login");
  const id = devIdentity(form.get("principal"));
  if (!id) redirect("/login");
  const jar = await cookies();
  jar.delete(SESSION_COOKIE);
  writeDevelopmentSession(jar, id);
  redirect(HOME);
}

/** Ends either kind of session. */
export async function signOut(): Promise<void> {
  const jar = await cookies();
  jar.delete(SESSION_COOKIE);
  jar.delete(DEV_SESSION_COOKIE);
  redirect("/login");
}
