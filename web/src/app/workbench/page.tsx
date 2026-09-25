import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AwaitingValue, ContextCard, NextReviewCard, WorkbenchTile, WorkflowCard, type TileFlag } from "@/components/domain/workbench-home";
import { can } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { fmtNum } from "@/lib/domain/format";
import { ruleTitle } from "@/lib/domain/labels";
import type { NavIcon } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { buildOverview, loadWorkbenchData, missingCategories, type WorkbenchData } from "@/lib/workbench/metrics";
import { getWorkbenchProfile, type TileKey, type WorkbenchProfile } from "@/lib/workbench/profile";

export const metadata: Metadata = { title: "Workbench" };

const MONTH = new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });
const S = "[@media(min-width:1024px)_and_(max-height:820px)]";

interface TileSpec {
  href: string;
  icon: NavIcon;
  title: string;
  value: ReactNode;
  flag?: TileFlag;
  valueTone?: "ink" | "brand" | "info";
  fallback: string;
}

/** The same six destinations for everyone; values are real, copy follows the role. */
function tileSpecs(d: WorkbenchData, canIngest: boolean, canDecide: boolean): Record<TileKey, TileSpec> {
  const incomplete = d.incomplete.length;
  const incompleteFlag: TileFlag | undefined = incomplete ? { label: `${incomplete} incomplete`, tone: "attention" } : undefined;
  return {
    ingest: canIngest
      ? { href: "/workbench/ingest", icon: "ingest", title: "Ingest data", value: d.submissions, flag: incompleteFlag, fallback: "Validate CSE submissions" }
      : { href: "/workbench/submissions", icon: "submissions", title: "Submissions", value: d.submissions, flag: incompleteFlag, fallback: "Review CSE submissions" },
    submissions: {
      href: "/workbench/submissions",
      icon: "submissions",
      title: "Submissions",
      value: `${d.submissionsAccepted}/${d.submissions}`,
      flag: incompleteFlag,
      fallback: "Ingestion and validation status",
    },
    entities: {
      href: "/workbench/entities",
      icon: "entities",
      title: "Entities",
      value: d.scoped.length,
      flag: d.highEntities ? { label: `${d.highEntities} high`, tone: "attention" } : undefined,
      fallback: "Rank CSEs by supervisory risk",
    },
    findings: {
      href: "/workbench/findings",
      icon: "findings",
      title: "Findings",
      value: d.signal.length,
      flag: d.high ? { label: `${d.high} high`, tone: "attention" } : undefined,
      fallback: "Inspect evidence-backed signals",
    },
    queue: {
      href: "/workbench/review-queue",
      icon: "queue",
      title: "Review queue",
      value: <AwaitingValue findings={d.rows} />,
      valueTone: "brand",
      fallback: canDecide ? "Record supervisory decisions" : "Findings awaiting a decision",
    },
    analytics: {
      href: "/workbench/analytics",
      icon: "analytics",
      title: "Analytics",
      value: d.families,
      flag: d.abstained ? { label: `${d.abstained} abstained`, tone: "info" } : undefined,
      fallback: "Detector families that signalled",
    },
    trust: {
      href: "/workbench/trust",
      icon: "trust",
      title: "TRUST-SAT",
      value: d.verified,
      flag: d.failed
        ? { label: `${d.failed} failed`, tone: "critical" }
        : d.signal.length && d.verified === d.signal.length
          ? { label: "All verified", tone: "brand", icon: "shield" }
          : { label: `${d.receipts} receipts`, tone: "brand", icon: "shield" },
      fallback: "Verified findings and receipts",
    },
    reports: {
      href: "/workbench/reports",
      icon: "reports",
      title: "Reports",
      value: d.scoped.length,
      fallback: "Supervisory reports per entity",
    },
  };
}

function RoleContext({ profile, d, periodLabel, cohortLabel, canDecide }: { profile: WorkbenchProfile; d: WorkbenchData; periodLabel: string; cohortLabel: string; canDecide: boolean }) {
  switch (profile.context) {
    case "review":
      return <NextReviewCard findings={d.rows} canDecide={canDecide} />;
    case "analysis": {
      const e = d.incomplete[0];
      return e ? (
        <ContextCard
          label="Next analysis"
          tag={{ text: "incomplete", tone: "attention" }}
          title={`${e.entity.displayName} submission`}
          detail={`Missing ${missingCategories(e)}`}
          href="/workbench/submissions"
          cta="Validate"
        />
      ) : (
        <ContextCard label="Next analysis" title="All submissions complete" detail={`${d.runsCompleted}/${d.runs} runs completed`} href="/workbench/pipeline" cta="Pipeline" />
      );
    }
    case "verification": {
      const f = d.signal.find((x) => x.trust === "failed") ?? d.signal[0];
      if (!f) return <ContextCard label="Next verification" title="No findings in scope" detail="Nothing to verify for this period" href="/workbench/trust" />;
      return (
        <ContextCard
          label="Next verification"
          tag={{ text: f.trust === "verified" ? "verified" : f.trust === "failed" ? "failed" : "unchecked", tone: f.trust === "failed" ? "critical" : f.trust === "verified" ? "brand" : "neutral" }}
          title={f.entityName}
          detail={`${ruleTitle(f.ruleOrCategory)} · ${f.evidenceCount} source records`}
          href={`/workbench/findings/${f.id}#s-trust`}
          cta="Trace"
        />
      );
    }
    case "platform":
      return (
        <ContextCard
          label="Next platform check"
          tag={{ text: d.originKind === "fixture" ? "fixture" : "live", tone: d.originKind === "fixture" ? "attention" : "brand" }}
          title={d.audit ? (d.audit.fully_compliant ? "Trust audit compliant" : "Trust audit exceptions") : "Trust audit not available"}
          detail={`${d.runsVerified}/${d.runs} runs verified · ${d.scoped.length} entities in scope`}
          href="/workbench/system"
          cta="System"
        />
      );
    case "assessment":
      return (
        <ContextCard
          label="Current assessment"
          title={periodLabel}
          detail={`${cohortLabel} · ${d.scoped.length} entities · ${d.signal.length} findings`}
          href="/workbench/overview"
          cta="Overview"
        />
      );
  }
}

export default async function WorkbenchPage({ searchParams }: { searchParams: Promise<{ cohort?: string; period?: string }> }) {
  const { cohort, period } = await searchParams;
  const session = (await getSession())!;
  const role = session.user.role;
  const profile = getWorkbenchProfile(role);
  const d = await loadWorkbenchData({ cohort, period });
  const canIngest = can(role, "analysis.run");
  const canDecide = can(role, "decision.record");
  const specs = tileSpecs(d, canIngest, canDecide);
  const overview = buildOverview(profile.overview, d);

  const a0 = d.scoped[0]?.assessment;
  const periodLabel = a0
    ? MONTH.format(a0.periodStart * 1000) === MONTH.format(a0.periodEnd * 1000)
      ? MONTH.format(a0.periodStart * 1000)
      : `${MONTH.format(a0.periodStart * 1000)} to ${MONTH.format(a0.periodEnd * 1000)}`
    : "No period";
  const cohortLabel = cohort ? `${cohort.charAt(0).toUpperCase()}${cohort.slice(1)} cohort` : "All cohorts";

  const progress = {
    decisions: { done: d.decided, total: d.signal.length },
    completeSubmissions: { done: d.submissions - d.incomplete.length, total: d.submissions },
    verifiedFindings: { done: d.verified, total: d.signal.length },
  };

  return (
    <div
      data-workbench-view={profile.viewLabel}
      className={cn("flex flex-col gap-4 p-4 md:p-6 lg:grid lg:h-full lg:min-h-0 lg:grid-rows-[auto_minmax(0,1.2fr)_minmax(0,1fr)] lg:overflow-hidden xl:gap-5", `${S}:gap-3 ${S}:py-4`)}
    >
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11.5px] tracking-[0.14em] uppercase">
            <span>
              <span className="font-semibold text-brand">Supervisory workbench</span>
              <span className="text-faint"> / {periodLabel}</span>
            </span>
            <span className="rounded-xs border border-line-2 px-1.5 py-px text-[10.5px] tracking-[0.08em] text-ink-2">{profile.viewLabel}</span>
          </p>
          <h1 className={cn("mt-2 text-[32px] leading-none font-semibold tracking-[-0.035em] text-ink xl:text-[38px]", `${S}:mt-1.5 ${S}:text-[30px]`)}>Supervisory intelligence.</h1>
          <p className={cn("mt-2 text-[15px] text-muted", `${S}:mt-1 ${S}:text-[14px]`)}>Analyse. Prioritise. Review. Decide.</p>
        </div>
        <RoleContext profile={profile} d={d} periodLabel={periodLabel} cohortLabel={cohortLabel} canDecide={canDecide} />
      </header>

      <section aria-label="Primary destinations" className={cn("grid gap-3 sm:grid-cols-2 lg:min-h-0 lg:grid-cols-3 lg:grid-rows-2 xl:gap-4", `${S}:gap-3`)}>
        {profile.tiles.map((key, i) => {
          const t = specs[key];
          const roleCopy = profile.copy[key];
          return (
            <WorkbenchTile
              key={key}
              href={t.href}
              icon={t.icon}
              title={t.title}
              description={roleCopy && (key !== "ingest" || canIngest) ? roleCopy : t.fallback}
              value={t.value}
              flag={t.flag}
              valueTone={t.valueTone}
              emphasis={i === 0}
            />
          );
        })}
      </section>

      <div className="grid grid-cols-1 gap-4 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:gap-5">
        <section aria-labelledby="flow-h" className="flex min-h-0 min-w-0 flex-col rounded-md border border-line bg-paper px-5 pt-4 pb-2">
          <div className="flex items-baseline justify-between">
            <h2 id="flow-h" className="text-[15px] font-semibold text-ink">
              Workflow
            </h2>
            <span className="label">{profile.workflowLabel}</span>
          </div>
          <WorkflowCard steps={profile.workflow} findings={d.rows} progress={progress} />
        </section>

        <section aria-labelledby="ov-h" className="flex min-h-0 min-w-0 flex-col rounded-md border border-line bg-paper px-5 pt-4 pb-3">
          <div className="flex items-baseline justify-between gap-4">
            <h2 id="ov-h" className="text-[15px] font-semibold text-ink">
              {overview.title}
            </h2>
            <span className="label truncate" title={overview.footnote}>
              {overview.caption}
            </span>
          </div>
          <ul className="mt-2 flex min-h-0 flex-1 flex-col justify-between" aria-label={overview.title}>
            {overview.rows.map((r) => (
              <li key={r.label} className="grid grid-cols-[minmax(0,12rem)_minmax(0,1fr)_4.5rem] items-center gap-4">
                <span className={cn("truncate text-[13.5px]", r.muted ? "text-muted" : "text-ink")}>{r.label}</span>
                {r.value != null && r.max ? (
                  <span className="h-1.5 rounded-[1px] bg-sunken" role="meter" aria-label={r.label} aria-valuemin={0} aria-valuemax={r.max} aria-valuenow={r.value}>
                    <span
                      className={cn("block h-full rounded-[1px]", r.sense === "risk" ? "bg-attention" : r.sense === "coverage" && r.value < r.max ? "bg-info" : "bg-brand")}
                      style={{ width: `${Math.min(100, (r.value / r.max) * 100)}%` }}
                    />
                  </span>
                ) : (
                  <span className={cn("truncate text-[12.5px]", r.muted ? "text-faint" : "font-medium text-brand-strong")}>{r.text ?? "Not available"}</span>
                )}
                <span className="num text-right text-[13px] font-semibold text-ink">
                  {r.value != null && r.max ? r.sense === "risk" ? `${fmtNum(r.value, 1)}/${r.max}` : `${fmtNum(r.value, 0)}/${r.max}` : <span className="font-normal text-faint">n/a</span>}
                </span>
              </li>
            ))}
          </ul>
          <p className={cn("mt-2 truncate text-[11.5px] text-muted", `${S}:sr-only`)}>{overview.footnote}</p>
        </section>
      </div>
    </div>
  );
}
