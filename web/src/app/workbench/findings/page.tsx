import type { Metadata } from "next";
import { toRowData } from "@/components/domain/finding-row";
import { FindingsExplorer } from "@/components/domain/findings-explorer";
import { PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { byPriority, loadEntityViews, loadFindingViews } from "@/lib/model";

export const metadata: Metadata = { title: "Findings" };

export default async function FindingsPage() {
  const [findings, entities] = await Promise.all([loadFindingViews(), loadEntityViews()]);
  const signal = findings.filter((f) => f.state === "signal").sort(byPriority);

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Supervision"
        title="Findings"
        description="Every signal the analytical workers raised, ordered by the backend's priority score. Each one links to its evidence, confidence and trust record."
      />
      {signal.length ? (
        <FindingsExplorer findings={signal.map(toRowData)} entities={entities.map((e) => ({ id: e.entity.id, name: e.entity.displayName }))} />
      ) : (
        <EmptyState title="No signal findings">No analysis run in the current period raised a signal.</EmptyState>
      )}
    </div>
  );
}
