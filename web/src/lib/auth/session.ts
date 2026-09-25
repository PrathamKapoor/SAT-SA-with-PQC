import "server-only";

import { cookies } from "next/headers";
import type { SessionUser } from "@/lib/types/domain";
import { readBackendSession } from "./adapters/backend";
import { readDevelopmentSession } from "./adapters/development";
import { authAdapterKind } from "./config";

/**
 * Session provider. Exactly one adapter is active (see ./config.ts):
 *
 *   backend adapter      production: backend-issued credential, verified by SAT-SA
 *   development adapter  local preview: a fixed development principal, verified by nothing
 *
 * Pages and components only ever call getSession(); they never know which
 * adapter produced the session except through `mode`, which the UI shows.
 */
export type SessionMode = "development" | "backend";

export interface Session {
  mode: SessionMode;
  user: SessionUser;
}

export function sessionMode(): SessionMode {
  return authAdapterKind();
}

export async function getSession(): Promise<Session | null> {
  const jar = await cookies();
  return authAdapterKind() === "development" ? readDevelopmentSession(jar) : readBackendSession(jar);
}
