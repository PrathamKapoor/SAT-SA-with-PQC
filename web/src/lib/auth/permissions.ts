import type { MembershipRole as SatsaRole } from "@/lib/api/types";

/**
 * Mirror of the backend role model (qsmlops/security/permissions/model.py,
 * ROLES["satsa_*"]). The UI uses it only to decide what to SHOW; the
 * backend remains the only place a permission is enforced.
 */
export type Permission =
  | "finding.view"
  | "evidence.view"
  | "review.read"
  | "review.create"
  | "decision.record"
  | "analysis.run"
  | "validation.run"
  | "trust.verify"
  | "report.export"
  | "calibration.approve"
  | "audit.read"
  | "identity.manage"
  | "config.manage"
  | "model.read"
  | "model.train"
  | "model.approve"
  | "model.deploy"
  | "model.rollback";

const VIEWER: Permission[] = ["finding.view", "evidence.view", "review.read", "trust.verify", "model.read"];

export const ROLE_PERMISSIONS: Record<SatsaRole, ReadonlySet<Permission> | "all"> = {
  satsa_viewer: new Set(VIEWER),
  satsa_analyst: new Set([...VIEWER, "analysis.run", "validation.run", "report.export", "model.train"]),
  satsa_supervisor: new Set([
    ...VIEWER,
    "review.create",
    "decision.record",
    "analysis.run",
    "validation.run",
    "report.export",
    "calibration.approve",
    "model.train",
    "model.approve",
    "model.deploy",
    "model.rollback",
  ]),
  satsa_auditor: new Set([...VIEWER, "report.export", "audit.read"]),
  satsa_admin: "all",
};

export function can(role: SatsaRole | undefined | null, permission: Permission): boolean {
  if (!role) return false;
  const granted = ROLE_PERMISSIONS[role];
  return granted === "all" || granted.has(permission);
}

export const ROLE_LABEL: Record<SatsaRole, string> = {
  satsa_admin: "Administrator",
  satsa_supervisor: "Supervisor",
  satsa_analyst: "Analyst",
  satsa_auditor: "Auditor",
  satsa_viewer: "Viewer",
};

export const ROLE_SUMMARY: Record<SatsaRole, string> = {
  satsa_admin: "Full control, including identities and configuration",
  satsa_supervisor: "Records review decisions. Terminal authority",
  satsa_analyst: "Runs analysis, ingests submissions, exports reports",
  satsa_auditor: "Reads everything plus the platform audit log",
  satsa_viewer: "Read-only findings, evidence and trust status",
};

export const ROLES_IN_ORDER: SatsaRole[] = [
  "satsa_supervisor",
  "satsa_analyst",
  "satsa_admin",
  "satsa_auditor",
  "satsa_viewer",
];

export function isRole(value: unknown): value is SatsaRole {
  return typeof value === "string" && value in ROLE_PERMISSIONS;
}
