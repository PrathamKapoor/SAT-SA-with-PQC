import type { Metadata } from "next";
import { IngestWorkflow } from "@/components/domain/ingest-workflow";
import { PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { getSource, isFixtureMode } from "@/lib/api";
import { can } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Ingest" };

export default async function IngestPage() {
  const session = (await getSession())!;
  const entities = await getSource().listEntities();
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Data"
        title="Ingest a CSE submission"
        description="A periodic submission covers six evidence categories. It is validated, normalized into canonical records, frozen as a snapshot and made ready for analysis."
      />
      {can(session.user.role, "analysis.run") ? (
        <IngestWorkflow mode={isFixtureMode() ? "fixture" : "api"} entities={entities.map((e) => e.displayName)} />
      ) : (
        <EmptyState title="Your role cannot ingest submissions">Ingestion requires the analyst, supervisor or administrator role.</EmptyState>
      )}
    </div>
  );
}
