import "server-only";

import { redirect } from "next/navigation";
import { requireContext } from "./context";
import { ApiError, type ApiErrorInfo } from "./errors";

export type Loaded<T> = { ok: true; data: T } | { ok: false; error: ApiErrorInfo };

/**
 * Run a page's API reads. An expired or revoked session goes back to sign-in;
 * a missing organization goes to organization selection; every other backend
 * error is returned so the page can render an honest error state (with the
 * request ID) instead of a blank or invented view.
 */
export async function load<T>(read: () => Promise<T>): Promise<Loaded<T>> {
  try {
    return { ok: true, data: await read() };
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (error.info.status === 401) redirect("/logout?reason=expired");
    if (error.info.code === "ORGANIZATION_REQUIRED") redirect("/organization");
    return { ok: false, error: error.info };
  }
}

/**
 * Same handling for server actions: resolve the session and organization
 * first (so the call carries X-Organization-ID), and never redirect mid-action
 * except for an ended session.
 */
export async function act<T>(write: () => Promise<T>): Promise<{ ok: true; data: T } | { ok: false; error: ApiErrorInfo }> {
  await requireContext();
  try {
    return { ok: true, data: await write() };
  } catch (error) {
    if (!(error instanceof ApiError)) throw error;
    if (error.info.status === 401) redirect("/logout?reason=expired");
    return { ok: false, error: error.info };
  }
}
