import type { Metadata } from "next";
import Link from "next/link";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { FamilyLabel } from "@/components/ui/badges";
import { PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { api, orNull } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import { fmtNum } from "@/lib/domain/format";
import { DIMENSION_LABEL, DIMENSION_ORDER, FAMILY_DESCRIPTION, familyOf, type FindingFamily } from "@/lib/domain/labels";
import { entityName, loadCurrentFindings, loadPortfolio } from "@/lib/workbench/data";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Analytics" };

export default async function AnalyticsPage() {
  const loaded = await load(async () => {
    const [portfolio, current] = await Promise.all([loadPortfolio(), loadCurrentFindings()]);
    const risks = await Promise.all(portfolio.priorities.map(async (p) => ({ priority: p, risk: await orNull(api.risk(p.run_id)) })));
    return { portfolio, current, risks };
  });

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Analytics"
        title="Analytics"
        description="The seven weighted risk dimensions across each entity's current run, and what each detector family reported. Scores are the backend's persisted risk profiles; nothing is recomputed here."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Analytics" />
      ) : loaded.data.risks.length === 0 ? (
        <EmptyState title="No analysed runs yet">Analytics appear once runs finish their analytical stages.</EmptyState>
      ) : (
        (() => {
          const { portfolio, current, risks } = loaded.data;
          const weights = risks.find((r) => r.risk)?.risk?.profile.weights ?? {};
          const families = new Map<FindingFamily, { signal: number; other: number }>();
          for (const { finding } of current) {
            const fam = familyOf(finding.rule_or_category);
            const row = families.get(fam) ?? { signal: 0, other: 0 };
            if (finding.state === "signal") row.signal += 1;
            else row.other += 1;
            families.set(fam, row);
          }
          return (
            <div className="space-y-10">
              <section aria-labelledby="dims-h">
                <SectionHeader id="dims-h" title="Dimension landscape" aside="score / weight, current run per entity" />
                <Panel className="overflow-x-auto">
                  <table className="w-full border-collapse text-left text-[13px]">
                    <caption className="sr-only">Risk dimension scores by entity</caption>
                    <thead>
                      <tr className="border-b border-line">
                        <th scope="col" className="label px-4 py-2 font-normal">
                          Entity
                        </th>
                        {DIMENSION_ORDER.map((d) => (
                          <th key={d} scope="col" className="label px-2 py-2 text-right font-normal whitespace-nowrap">
                            {DIMENSION_LABEL[d]}
                            <span className="block text-[10px] text-faint">weight {weights[d] ?? "n/a"}</span>
                          </th>
                        ))}
                        <th scope="col" className="label px-4 py-2 text-right font-normal">
                          Total
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {risks.map(({ priority, risk }) => {
                        const by = new Map((risk?.profile.dimensions ?? []).map((d) => [d.name, d]));
                        return (
                          <tr key={priority.entity_id} className="border-b border-line/70 last:border-0">
                            <th scope="row" className="px-4 py-2 font-medium text-ink">
                              <Link href={`/workbench/runs/${priority.run_id}`} className="hover:text-brand-strong">
                                {entityName(portfolio, priority.entity_id)}
                              </Link>
                            </th>
                            {DIMENSION_ORDER.map((name) => {
                              const d = by.get(name);
                              const ratio = d && d.weight ? d.score / d.weight : 0;
                              return (
                                <td key={name} className={cn("num px-2 py-2 text-right", ratio > 0.66 ? "text-attention-strong" : d && d.score > 0 ? "text-ink" : "text-faint")}>
                                  {d ? fmtNum(d.score, 1) : "n/a"}
                                </td>
                              );
                            })}
                            <td className="num px-4 py-2 text-right font-semibold text-ink">{risk ? fmtNum(risk.profile.total_score, 1) : "n/a"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </Panel>
              </section>

              <section aria-labelledby="families-h">
                <SectionHeader id="families-h" title="Detector families" aside="current runs" />
                <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {[...families.entries()]
                    .sort((a, b) => b[1].signal - a[1].signal)
                    .map(([family, counts]) => (
                      <li key={family} className="rounded-md border border-line bg-paper px-4 py-3">
                        <FamilyLabel family={family} />
                        <p className="mt-1 text-[12.5px] text-muted">{FAMILY_DESCRIPTION[family]}</p>
                        <p className="mt-2 text-[13px] text-ink-2">
                          <span className="num font-semibold text-ink">{counts.signal}</span> signal{counts.signal === 1 ? "" : "s"} ·{" "}
                          <span className="num">{counts.other}</span> without signal
                        </p>
                      </li>
                    ))}
                </ul>
              </section>
            </div>
          );
        })()
      )}
    </div>
  );
}
