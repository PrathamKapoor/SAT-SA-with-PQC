import type { Metadata } from "next";
import { IngestWorkflow } from "@/components/domain/ingest-workflow";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { all, api } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import { can } from "@/lib/auth/permissions";

export const metadata: Metadata = { title: "Ingest" };

export default async function IngestPage({ searchParams }: { searchParams: Promise<{ entity?: string }> }) {
  const ctx = await requireContext();
  const { entity } = await searchParams;
  const allowed = can(ctx.role, "analysis.run");
  const loaded = allowed ? await load(async () => ({ entities: await all((q) => api.entities(q)), assessments: await all((q) => api.assessments(q)) })) : null;
  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Data"
        title="Ingest a CSE submission"
        description="Register the entity and assessment period, upload the evidence files, and let the SAT-SA service validate every record. A valid version can then be analysed; the run stops for a supervisor's decision."
      />
      {!allowed ? (
        <EmptyState title="Your role cannot ingest submissions">Ingestion requires the analyst, supervisor or administrator role in this organization.</EmptyState>
      ) : !loaded!.ok ? (
        <ApiErrorPanel error={loaded!.error} context="Ingest" />
      ) : (
        <IngestWorkflow entities={loaded!.data.entities} assessments={loaded!.data.assessments} initialEntity={entity} />
      )}
    </div>
  );
}
