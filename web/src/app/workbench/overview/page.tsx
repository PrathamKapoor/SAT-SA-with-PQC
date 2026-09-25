import type { Metadata } from "next";
import Link from "next/link";
import { Metric, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { fmtNum } from "@/lib/domain/format";
import { DIMENSION_LABEL, DIMENSION_ORDER, FAMILY_LABEL, type FindingFamily } from "@/lib/domain/labels";
import { loadCore, loadEntityViews } from "@/lib/model";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Overview" };

/** Cell tint by share of the dimension's weight used. Paired with the printed score. */
function shade(ratio: number) {
  if (ratio <= 0) return "bg-paper text-faint";
  if (ratio < 0.33) return "bg-brand-tint text-ink";
  if (ratio < 0.66) return "bg-brand-tint-2 text-ink";
  return "bg-attention-tint text-attention-strong font-semibold";
}

export default async function OverviewPage() {
  const [entities, core] = await Promise.all([loadEntityViews(), loadCore()]);
  const signal = core.findings.filter((f) => f.state === "signal");
  const families = [...new Set(entities.flatMap((e) => e.findings.map((f) => f.family)))] as FindingFamily[];
  const mean = entities.length ? entities.reduce((n, e) => n + (e.risk?.total_score ?? 0), 0) / entities.length : 0;
  const incomplete = entities.filter((e) => e.completeness.missing.length).length;

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader eyebrow="Command" title="Period overview" description="Where risk sits across entities and dimensions for the current assessment period." />

      <Panel className="px-5 py-5">
        <dl className="grid grid-cols-2 gap-6 md:grid-cols-5">
          <Metric label="Entities" value={entities.length} />
          <Metric label="Signal findings" value={signal.length} />
          <Metric label="Mean risk" value={fmtNum(mean, 1)} unit="/100" />
          <Metric label="Highest risk" value={fmtNum(entities[0]?.risk?.total_score ?? null, 1)} detail={entities[0]?.entity.displayName} />
          <Metric label="Incomplete submissions" value={incomplete} tone={incomplete ? "attention" : "ink"} />
        </dl>
      </Panel>

      <section aria-labelledby="hm-h" className="mt-10">
        <SectionHeader id="hm-h" title="Risk by entity and dimension" aside="score of weight; darker uses more of the weight" />
        <Panel className="overflow-x-auto px-5 py-4">
          <table className="w-full min-w-[46rem] border-separate border-spacing-[3px] text-left">
            <caption className="sr-only">Risk score per entity per dimension</caption>
            <thead>
              <tr>
                <th scope="col" className="label pb-1 font-normal">
                  Entity
                </th>
                {DIMENSION_ORDER.map((d) => (
                  <th key={d} scope="col" className="pb-1 align-bottom text-[11.5px] leading-tight font-normal text-muted">
                    {DIMENSION_LABEL[d]}
                  </th>
                ))}
                <th scope="col" className="pb-1 text-right text-[11.5px] font-normal text-muted">
                  Total
                </th>
              </tr>
            </thead>
            <tbody>
              {entities.map((e) => (
                <tr key={e.entity.id}>
                  <th scope="row" className="pr-3 text-[13px] font-medium whitespace-nowrap">
                    <Link href={`/workbench/entities/${e.entity.id}`} className="text-ink hover:text-brand">
                      {e.entity.displayName}
                    </Link>
                  </th>
                  {DIMENSION_ORDER.map((d) => {
                    const x = e.risk?.dimensions.find((y) => y.name === d);
                    const ratio = x && x.weight ? x.score / x.weight : 0;
                    return (
                      <td key={d} className={cn("h-10 rounded-[3px] border border-line/60 px-2 text-center font-mono text-[12px]", shade(ratio))}>
                        {x?.score ? fmtNum(x.score, 1) : "0"}
                      </td>
                    );
                  })}
                  <td className="num pl-2 text-right text-[14px] font-semibold text-ink">{fmtNum(e.risk?.total_score ?? null, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </section>

      <section aria-labelledby="fam-h" className="mt-10">
        <SectionHeader id="fam-h" title="Findings by entity and family" />
        <Panel className="overflow-x-auto px-5 py-4">
          <table className="w-full min-w-[40rem] text-left text-[13px]">
            <caption className="sr-only">Signal findings per entity per detector family</caption>
            <thead>
              <tr className="border-b border-line">
                <th scope="col" className="label py-2 font-normal">
                  Entity
                </th>
                {families.map((f) => (
                  <th key={f} scope="col" className="py-2 text-right text-[11.5px] font-normal text-muted">
                    {FAMILY_LABEL[f]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entities.map((e) => (
                <tr key={e.entity.id} className="border-b border-line/70 last:border-0">
                  <th scope="row" className="py-2 font-medium text-ink">
                    {e.entity.displayName}
                  </th>
                  {families.map((f) => {
                    const n = e.findings.filter((x) => x.family === f).length;
                    return (
                      <td key={f} className={cn("num py-2 text-right", n ? "font-medium text-ink" : "text-line-2")}>
                        {n || "0"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </section>
    </div>
  );
}
