import type { Metadata } from "next";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import { Sidebar, type SidebarProps } from "@/components/shell/sidebar";
import { TopBar, type OriginInfo } from "@/components/shell/topbar";
import { getSource } from "@/lib/api";
import { can, ROLE_LABEL } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { fmtDate, fmtPeriod } from "@/lib/domain/format";
import { NAV } from "@/lib/nav";
import { ReviewStoreProvider } from "@/lib/review-store";

export const metadata: Metadata = {
  title: { template: "%s · SAT-SA", default: "Workbench · SAT-SA" },
  robots: { index: false, follow: false },
};

export default async function WorkbenchLayout({ children }: { children: ReactNode }) {
  const session = await getSession();
  if (!session) redirect("/login");

  const source = getSource();
  const [findings, decisions, assessments] = await Promise.all([
    source.listFindings({ state: "signal" }),
    source.listReviewDecisions(),
    source.listAssessments(),
  ]);

  const role = session.user.role;
  const groups = NAV.map((g) => ({ ...g, items: g.items.filter((i) => !i.requires || can(role, i.requires)) })).filter((g) => g.items.length);

  const nav: SidebarProps = {
    groups,
    signalFindingIds: findings.map((f) => f.id),
    decidedFindingIds: [...new Set(decisions.map((d) => d.findingId))],
    user: { displayName: session.user.displayName, roleLabel: ROLE_LABEL[role] },
    sessionMode: session.mode,
  };

  const periods = new Set(assessments.map((a) => `${a.periodStart}-${a.periodEnd}`));
  const period =
    assessments.length && periods.size === 1 ? fmtPeriod(assessments[0].periodStart, assessments[0].periodEnd) : assessments.length ? `${periods.size} periods` : null;

  const o = source.origin();
  const origin: OriginInfo =
    o.kind === "fixture"
      ? {
          kind: "fixture",
          label: "Development fixture",
          detail: `${o.notice} Generated ${fmtDate(o.generatedAt)} by SAT-SA ${o.satsaVersion}. ${session.mode === "development" ? "Session is a development role, not an authenticated identity." : ""}`,
        }
      : { kind: "api", label: "Live backend", detail: `Data from the SAT-SA API at ${o.baseUrl}.` };

  return (
    <ReviewStoreProvider>
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <div className="relative flex h-dvh overflow-hidden bg-canvas">
        <Sidebar {...nav} />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar nav={nav} period={period} origin={origin} />
          <main id="main" tabIndex={-1} className="relative min-h-0 flex-1 overflow-y-auto focus:outline-none">
            {children}
          </main>
        </div>
      </div>
    </ReviewStoreProvider>
  );
}
