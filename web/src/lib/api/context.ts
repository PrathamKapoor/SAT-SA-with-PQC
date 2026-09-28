import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { all, listOrganizations, ORG_COOKIE, readSession, SESSION_COOKIE } from "./client";
import { ApiError } from "./errors";
import { requestOrganization } from "./org-scope";
import type { MembershipRole, Organization, Session } from "./types";

/**
 * Who is signed in and which organization the workbench is scoped to.
 * Resolved from the backend on every request: the session from
 * GET /api/v1/session, memberships from GET /api/v1/organizations. The
 * stored organization id is only a selection; the backend checks membership,
 * role and resource ownership on every call.
 */
export interface SignedIn {
  session: Session;
  organizations: Organization[];
}

export interface WorkbenchContext extends SignedIn {
  organization: Organization;
  role: MembershipRole;
}

/** The signed-in user, or a redirect to sign-in when there is no valid session. */
export const requireSignedIn = cache(async (): Promise<SignedIn> => {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) redirect("/login");
  try {
    const session = await readSession(token);
    const organizations = await all((q) => listOrganizations(token, q.offset));
    return { session, organizations: organizations.filter((o) => o.status === "active") };
  } catch (error) {
    if (error instanceof ApiError && error.info.status === 401) redirect("/logout?reason=expired");
    throw error;
  }
});

/** The signed-in user in a selected organization, or a redirect to select one. */
export const requireContext = cache(async (): Promise<WorkbenchContext> => {
  const signedIn = await requireSignedIn();
  const selected = (await cookies()).get(ORG_COOKIE)?.value;
  // A stored selection that is still an active membership, or else the only membership.
  const organization =
    signedIn.organizations.find((o) => o.id === selected) ?? (signedIn.organizations.length === 1 ? signedIn.organizations[0] : undefined);
  if (!organization) redirect(selected ? "/organization?reason=unavailable" : "/organization");
  requestOrganization().id = organization.id;
  return { ...signedIn, organization, role: organization.role };
});
