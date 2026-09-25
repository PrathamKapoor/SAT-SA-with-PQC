import type { Metadata } from "next";
import { toRowData } from "@/components/domain/finding-row";
import { AwaitingValue, NextReviewCard, SopCard, WorkbenchTile } from "@/components/domain/workbench-home";
import { getSource } from "@/lib/api";
import { can } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { fmtDate, fmtNum } from "@/lib/domain/format";
import { byPriority, loadCore, loadEntityViews, loadFindingViews } from "@/lib/model";
import type { RiskDimensionName } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Workbench" };

/**
 * Capabilities named in the supervisory review cycle. Only three map to a
 * risk dimension the backend actually scores; the rest are shown as not
 * assessed rather than given a number.
 */
const CAPABILITIES: Array<{ label: string; dimension: RiskDimensionName | null }> = [
  { label: "Threat Detection", dimension: "detection_gap" },
  { label: "Investigation Depth", dimension: "investigation_quality" },
  { label: "Escalation Discipline", dimension: "escalation_discipline" },
  { label: "Incident Response", dimension: null },
  { label: "Security Operations", dimension: null },
  { label: "Governance and Oversight", dimension: null },
  { label: "Operational Discipline", dimension: null },
  { label: "Cyber Resilience", dimension: null },
];

const MONTH = new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" });

export default async function WorkbenchPage({ searchParams }: { searchParams: Promise<{ cohort?: string; period?: string }> }) {
  const { cohort, period } = await searchParams;
  const session = (await getSession())!;
  const src = getSource();
  const [core, findings, entities, receipts] = await Promise.all([loadCore(), loadFindingViews(), loadEntityViews(), src.listTrustReceipts()]);

  const inPeriod = (assessmentId: string) => {
    if (!period) return true;
    const a = core.assessments.find((x) => x.id === assessmentId);
    return a ? `${a.periodStart}-${a.periodEnd}` === period : false;
  };
  const scoped = entities.filter((e) => (!cohort || e.entity.sector === cohort) && (!e.assessment || inPeriod(e.assessment.id)));
  const ids = new Set(scoped.map((e) => e.entity.id));
  const signal = findings.filter((f) => f.state === "signal" && ids.has(f.entityId)).sort(byPriority);
  const rows = signal.map(toRowData);
  const high = signal.filter((f) => f.severity === "high");
  const submissions = scoped.map((e) => e.submission).filter((s) => s !== null);
  const incomplete = scoped.filter((e) => e.completeness.missing.length).length;
  const highEntities = scoped.filter((e) => e.findings.some((f) => f.severity === "high")).length;
  const families = new Set(signal.map((f) => f.family)).size;
  const verified = signal.filter((f) => f.trust === "verified").length;
  const failed = signal.filter((f) => f.trust === "failed").length;
  const decided = new Set(core.decisions.filter((d) => ids.has(signal.find((f) => f.id === d.findingId)?.entityId ?? "")).map((d) => d.findingId)).size;

  const a0 = scoped[0]?.assessment;
  const periodLabel = a0
    ? MONTH.format(a0.periodStart * 1000) === MONTH.format(a0.periodEnd * 1000)
      ? MONTH.format(a0.periodStart * 1000)
      : `${MONTH.format(a0.periodStart * 1000)} to ${MONTH.format(a0.periodEnd * 1000)}`
    : "No period";

  const capability = CAPABILITIES.map((c) => {
    if (!c.dimension) return { ...c, value: null as number | null, weight: 0 };
    const ds = scoped.map((e) => e.risk?.dimensions.find((d) => d.name === c.dimension)).filter((d) => d !== undefined);
    return { ...c, value: ds.length ? ds.reduce((n, d) => n + d.score, 0) / ds.length : null, weight: ds[0]?.weight ?? 0 };
  });

  const canIngest = can(session.user.role, "analysis.run");

  return (
    <div className="flex flex-col gap-4 p-4 md:p-6 lg:grid lg:h-full lg:min-h-0 lg:grid-rows-[auto_minmax(0,1.2fr)_minmax(0,1fr)] lg:overflow-hidden xl:gap-5 [@media(min-width:1024px)_and_(max-height:820px)]:gap-3 [@media(min-width:1024px)_and_(max-height:820px)]:py-4">
      <header className="flex flex-wrap items-end justify-between gap-x-8 gap-y-4">
        <div>
          <p className="font-mono text-[11.5px] tracking-[0.14em] uppercase">
            <span className="font-semibold text-brand">Supervisory workbench</span>
            <span className="text-faint"> / {periodLabel}</span>
          </p>
          <h1 className="mt-2 text-[32px] leading-none font-semibold tracking-[-0.035em] text-ink xl:text-[38px] [@media(min-width:1024px)_and_(max-height:820px)]:mt-1.5 [@media(min-width:1024px)_and_(max-height:820px)]:text-[30px]">Supervisory intelligence.</h1>
          <p className="mt-2 text-[15px] text-muted [@media(min-width:1024px)_and_(max-height:820px)]:mt-1 [@media(min-width:1024px)_and_(max-height:820px)]:text-[14px]">Analyse. Prioritise. Review. Decide.</p>
        </div>
        <NextReviewCard findings={rows} />
      </header>

      <section aria-label="Primary destinations" className="grid gap-3 sm:grid-cols-2 lg:min-h-0 lg:grid-cols-3 lg:grid-rows-2 xl:gap-4 [@media(min-width:1024px)_and_(max-height:820px)]:gap-3">
        <WorkbenchTile
          href={canIngest ? "/workbench/ingest" : "/workbench/submissions"}
          icon={canIngest ? "ingest" : "submissions"}
          title={canIngest ? "Ingest data" : "Submissions"}
          description={canIngest ? "Validate CSE submissions" : "Review CSE submissions"}
          value={submissions.length}
          flag={incomplete ? { label: `${incomplete} incomplete`, tone: "attention" } : undefined}
        />
        <WorkbenchTile
          href="/workbench/entities"
          icon="entities"
          title="Entities"
          description="Rank CSEs by supervisory risk"
          value={scoped.length}
          flag={highEntities ? { label: `${highEntities} high`, tone: "attention" } : undefined}
        />
        <WorkbenchTile
          href="/workbench/findings"
          icon="findings"
          title="Findings"
          description="Inspect evidence-backed signals"
          value={signal.length}
          flag={high.length ? { label: `${high.length} high`, tone: "attention" } : undefined}
        />
        <WorkbenchTile
          href="/workbench/review-queue"
          icon="queue"
          title="Review queue"
          description={can(session.user.role, "decision.record") ? "Record supervisory decisions" : "Findings awaiting a decision"}
          value={<AwaitingValue findings={rows} />}
          valueTone="brand"
        />
        <WorkbenchTile href="/workbench/analytics" icon="analytics" title="Analytics" description="Detector families that signalled" value={families} />
        <WorkbenchTile
          href="/workbench/trust"
          icon="trust"
          title="TRUST-SAT"
          description="Verified findings and receipts"
          value={verified}
          flag={failed ? { label: `${failed} failed`, tone: "critical" } : { label: `${receipts.length} receipts`, tone: "brand", icon: "shield" }}
        />
      </section>

      <div className="grid grid-cols-1 gap-4 lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] xl:gap-5">
        <section aria-labelledby="sop-h" className="flex min-h-0 min-w-0 flex-col rounded-md border border-line bg-paper px-5 pt-4 pb-2">
          <div className="flex items-baseline justify-between">
            <h2 id="sop-h" className="text-[15px] font-semibold text-ink">
              SOP
            </h2>
            <span className="label">Review cycle</span>
          </div>
          <SopCard findings={rows} backendDecided={decided} verifyHref="/workbench/trust" />
        </section>

        <section aria-labelledby="cap-h" className="flex min-h-0 min-w-0 flex-col rounded-md border border-line bg-paper px-5 pt-4 pb-3">
          <div className="flex items-baseline justify-between gap-4">
            <h2 id="cap-h" className="text-[15px] font-semibold text-ink">
              Capability overview
            </h2>
            <span className="label" title="Mean of the backend risk dimension of the same name across the entities in scope">Observed risk, lower is better</span>
          </div>
          <ul className="mt-2 flex min-h-0 flex-1 flex-col justify-between" aria-label="Capabilities">
            {capability.map((c) => (
              <li key={c.label} className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)_4rem] items-center gap-4">
                <span className={cn("truncate text-[13.5px]", c.dimension ? "text-ink" : "text-muted")}>{c.label}</span>
                {c.value == null ? (
                  <span className="truncate text-[12px] text-faint">Not assessed</span>
                ) : (
                  <span className="h-1.5 rounded-[1px] bg-sunken" role="meter" aria-label={`${c.label} observed risk`} aria-valuemin={0} aria-valuemax={c.weight} aria-valuenow={c.value}>
                    <span className="block h-full rounded-[1px] bg-attention" style={{ width: `${c.weight ? (c.value / c.weight) * 100 : 0}%` }} />
                  </span>
                )}
                <span className="num text-right text-[13px] font-semibold text-ink">
                  {c.value == null ? <span className="font-normal text-faint">n/a</span> : `${fmtNum(c.value, 1)}/${c.weight}`}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-2 truncate text-[11.5px] text-muted [@media(min-width:1024px)_and_(max-height:820px)]:sr-only">
            Mean of the backend risk dimension across {scoped.length} entities{a0 ? `, ${fmtDate(a0.periodStart)} to ${fmtDate(a0.periodEnd)}` : ""}.
          </p>
        </section>
      </div>
    </div>
  );
}
