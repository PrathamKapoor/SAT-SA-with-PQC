import type { Metadata } from "next";
import Link from "next/link";
import { FindingList } from "@/components/domain/finding-list";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { PageHeader } from "@/components/ui/layout";
import { load } from "@/lib/api/guard";
import { bySignalThenConfidence, loadCurrentFindings, loadPortfolio } from "@/lib/workbench/data";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Findings" };

export default async function FindingsPage({ searchParams }: { searchParams: Promise<{ entity?: string; state?: string }> }) {
  const sp = await searchParams;
  const onlySignals = sp.state !== "all";
  const loaded = await load(async () => ({ rows: await loadCurrentFindings(), portfolio: await loadPortfolio() }));

  const chip = (href: string, active: boolean, label: string) => (
    <Link
      key={href}
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn("rounded-sm border px-2.5 py-1 text-[12.5px]", active ? "border-brand bg-brand-tint text-brand-strong" : "border-line bg-paper text-ink-2 hover:border-ink/40")}
    >
      {label}
    </Link>
  );
  const q = (entity?: string, state?: string) => {
    const p = new URLSearchParams(Object.entries({ entity, state }).filter((e): e is [string, string] => Boolean(e[1])));
    return p.toString() ? `/workbench/findings?${p}` : "/workbench/findings";
  };

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Supervision"
        title="Findings"
        description="Findings from each entity's current run: the latest run with a persisted risk profile, as the priority ranking uses it. Earlier runs are on each run's page."
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Findings" />
      ) : (
        (() => {
          const { rows, portfolio } = loaded.data;
          const names = new Map(portfolio.priorities.map((p) => [p.run_id, portfolio.entity.get(p.entity_id)?.display_name ?? p.entity_id]));
          const shown = rows
            .filter((r) => !sp.entity || r.priority.entity_id === sp.entity)
            .filter((r) => !onlySignals || r.finding.state === "signal")
            .map((r) => r.finding)
            .sort(bySignalThenConfidence);
          return (
            <>
              <div className="mb-4 flex flex-wrap gap-1.5">
                {chip(q(sp.entity, undefined), onlySignals, "Signals")}
                {chip(q(sp.entity, "all"), !onlySignals, "All states")}
                <span aria-hidden="true" className="mx-1 w-px bg-line" />
                {chip(q(undefined, sp.state), !sp.entity, "All entities")}
                {portfolio.priorities.map((p) => chip(q(p.entity_id, sp.state), sp.entity === p.entity_id, portfolio.entity.get(p.entity_id)?.display_name ?? p.entity_id))}
              </div>
              <FindingList
                findings={shown}
                runEntityNames={names}
                empty={portfolio.priorities.length ? "No findings match these filters" : "No analysed runs yet. Findings appear once a run's analytical stages finish."}
              />
              <p className="mt-3 text-[12px] text-muted">{shown.length} shown</p>
            </>
          );
        })()
      )}
    </div>
  );
}
