import type { Metadata } from "next";
import { SecurityDataBrowser } from "@/components/domain/security-data-browser";
import { PageHeader } from "@/components/ui/layout";
import { getSource } from "@/lib/api";

export const metadata: Metadata = { title: "Security data" };

export default async function SecurityDataPage() {
  const src = getSource();
  const [data, entities] = await Promise.all([src.getSecurityData(), src.listEntities()]);
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Data"
        title="Security data"
        description="The canonical records normalized from CSE submissions, in six evidence categories. Analysts appear only as the pseudonyms the entity submitted. This is periodic evidence, not live telemetry."
      />
      <SecurityDataBrowser data={data} entities={entities.map((e) => ({ id: e.id, name: e.displayName }))} />
    </div>
  );
}
