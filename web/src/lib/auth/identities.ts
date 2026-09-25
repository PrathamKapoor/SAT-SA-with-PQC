import type { SatsaRole } from "@/lib/types/domain";

/**
 * DEVELOPMENT PRINCIPALS. They exist only in this frontend, so that each
 * role can be previewed before backend authentication is connected. They do
 * not exist in the SAT-SA backend, carry no credential, and are never sent
 * to a backend API. Roles and permissions are the existing ones mirrored
 * from the backend (see ./permissions.ts); nothing new is defined here.
 */
export interface DevIdentity {
  principal: string;
  role: SatsaRole;
  displayName: string;
  summary: string;
}

export const DEV_IDENTITIES: DevIdentity[] = [
  { principal: "dev-admin", role: "satsa_admin", displayName: "Development administrator", summary: "Full development access" },
  { principal: "dev-supervisor", role: "satsa_supervisor", displayName: "Development supervisor", summary: "Findings, evidence, review and decisions" },
  { principal: "dev-analyst", role: "satsa_analyst", displayName: "Development analyst", summary: "Ingestion, analytics and findings" },
  { principal: "dev-auditor", role: "satsa_auditor", displayName: "Development auditor", summary: "Audit log and read access" },
  { principal: "dev-viewer", role: "satsa_viewer", displayName: "Development viewer", summary: "Read-only access" },
];

export function devIdentity(principal: unknown): DevIdentity | undefined {
  return DEV_IDENTITIES.find((d) => d.principal === principal);
}
