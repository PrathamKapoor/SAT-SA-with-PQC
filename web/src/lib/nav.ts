import type { Permission } from "@/lib/auth/permissions";

export type NavIcon =
  | "workbench"
  | "overview"
  | "entities"
  | "findings"
  | "queue"
  | "decisions"
  | "analytics"
  | "benchmarks"
  | "pipeline"
  | "submissions"
  | "ingest"
  | "securityData"
  | "agents"
  | "architecture"
  | "reports"
  | "trust"
  | "audit"
  | "admin"
  | "system"
  | "models";

export interface NavItem {
  href: string;
  label: string;
  icon: NavIcon;
  /** Hidden unless the session role holds this permission (UI only; backend enforces). */
  requires?: Permission;
  /** Key into the live counts passed to the sidebar (runs awaiting review). */
  countKey?: "awaitingReview";
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV: NavGroup[] = [
  {
    label: "Command",
    items: [
      { href: "/workbench", label: "Workbench", icon: "workbench" },
    ],
  },
  {
    label: "Supervision",
    items: [
      { href: "/workbench/entities", label: "Entities", icon: "entities" },
      { href: "/workbench/findings", label: "Findings", icon: "findings" },
      { href: "/workbench/review-queue", label: "Review queue", icon: "queue", countKey: "awaitingReview" },
      { href: "/workbench/decisions", label: "Decisions", icon: "decisions" },
    ],
  },
  {
    label: "Analytics",
    items: [
      { href: "/workbench/analytics", label: "Analytics", icon: "analytics" },
      { href: "/workbench/benchmarks", label: "Benchmarks", icon: "benchmarks" },
      { href: "/workbench/runs", label: "Analysis runs", icon: "pipeline" },
      { href: "/workbench/models", label: "Models", icon: "models", requires: "model.read" },
    ],
  },
  {
    label: "Data",
    items: [
      { href: "/workbench/submissions", label: "Submissions", icon: "submissions" },
      { href: "/workbench/ingest", label: "Ingest", icon: "ingest", requires: "analysis.run" },
      { href: "/workbench/security-data", label: "Security data", icon: "securityData", requires: "evidence.view" },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/workbench/agents", label: "Agents", icon: "agents" },
      { href: "/workbench/architecture", label: "Architecture", icon: "architecture" },
      { href: "/workbench/reports", label: "Reports", icon: "reports" },
    ],
  },
  {
    label: "Trust",
    items: [
      { href: "/workbench/trust", label: "TRUST-SAT", icon: "trust", requires: "trust.verify" },
      { href: "/workbench/audit", label: "Audit", icon: "audit", requires: "audit.read" },
    ],
  },
  {
    label: "Admin",
    items: [
      { href: "/workbench/admin", label: "Members", icon: "admin", requires: "identity.manage" },
      { href: "/workbench/system", label: "System", icon: "system" },
    ],
  },
];

/** Page title for the top bar, derived from the navigation (longest matching prefix). */
export function titleFor(pathname: string): string {
  let best: NavItem | undefined;
  for (const g of NAV)
    for (const i of g.items)
      if ((pathname === i.href || pathname.startsWith(`${i.href}/`)) && (!best || i.href.length > best.href.length)) best = i;
  return best?.label ?? "Workbench";
}
