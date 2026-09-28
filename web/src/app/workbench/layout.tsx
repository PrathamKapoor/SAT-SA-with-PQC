import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Sidebar, type SidebarProps } from "@/components/shell/sidebar";
import { TopBar } from "@/components/shell/topbar";
import { api, apiBase } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { can, ROLE_LABEL } from "@/lib/auth/permissions";
import { NAV } from "@/lib/nav";

export const metadata: Metadata = {
  title: { template: "%s · SAT-SA", default: "Workbench · SAT-SA" },
  robots: { index: false, follow: false },
};

export default async function WorkbenchLayout({ children }: { children: ReactNode }) {
  const ctx = await requireContext();
  const awaiting = await api.runs({ status: "awaiting_review", limit: 200 }).catch(() => null);

  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => !i.requires || can(ctx.role, i.requires)) })).filter((g) => g.items.length);
  const roleLabel = ROLE_LABEL[ctx.role] ?? ctx.role;
  const nav: SidebarProps = {
    groups,
    awaitingReview: awaiting ? awaiting.items.length : 0,
    user: { displayName: ctx.session.name, roleLabel, organization: ctx.organization.name },
  };

  return (
    <>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className="relative flex h-dvh overflow-hidden bg-canvas">
        <Sidebar {...nav} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar
            nav={nav}
            context={{
              organization: ctx.organization.name,
              canSwitch: ctx.organizations.length > 1,
              displayName: ctx.session.name,
              roleLabel,
              apiBase: apiBase() ?? "",
            }}
          />
          <main id="main" tabIndex={-1} className="relative min-h-0 flex-1 overflow-y-auto focus:outline-none">
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
