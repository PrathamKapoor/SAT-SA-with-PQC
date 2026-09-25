import type { Metadata } from "next";
import { KeyValue, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { getSource } from "@/lib/api";
import { can, ROLE_LABEL } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { fmtDateTime } from "@/lib/domain/format";
import { loadCore } from "@/lib/model";

export const metadata: Metadata = { title: "System" };

export default async function SystemPage() {
  const session = (await getSession())!;
  if (!can(session.user.role, "config.manage")) {
    return (
      <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
        <EmptyState title="System status requires the administrator role" />
      </div>
    );
  }
  const src = getSource();
  const origin = src.origin();
  const core = await loadCore();
  const run = core.runs[0];

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader eyebrow="Admin" title="System" description="Where this interface gets its data, which versions produced it, and how the session is established." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="px-5 py-5">
          <SectionHeader title="Data source" />
          <KeyValue
            columns={1}
            items={
              origin.kind === "fixture"
                ? [
                    ["Mode", "Development fixture (SATSA_DATA_SOURCE=fixture)"],
                    ["Generated", fmtDateTime(origin.generatedAt)],
                    ["Produced by", `SAT-SA ${origin.satsaVersion}, web/scripts/export-demo-fixture.py`],
                    ["Content", origin.notice],
                  ]
                : [
                    ["Mode", "Live backend (SATSA_DATA_SOURCE=api)"],
                    ["API", origin.baseUrl],
                  ]
            }
          />
        </Panel>
        <Panel className="px-5 py-5">
          <SectionHeader title="Analytics" as="h3" />
          <KeyValue
            columns={1}
            items={[
              ["Code version", run?.codeVersion ?? "n/a"],
              ["Analytics version", run?.analyticsVersion ?? "n/a"],
              ["Workers per run", run?.summary.workers?.length ?? "n/a"],
              ["Signature", `${run?.summary.trust?.algorithm_id ?? "ML-DSA-65"} over SHA3-256`],
            ]}
          />
        </Panel>
        <Panel className="px-5 py-5">
          <SectionHeader title="Session" as="h3" />
          <KeyValue
            columns={1}
            items={[
              ["Mode", session.mode === "development" ? "Development role, not authenticated" : "Backend-issued credential"],
              ["Role", ROLE_LABEL[session.user.role]],
              ["Cookie", "HttpOnly, SameSite=Lax"],
            ]}
          />
        </Panel>
        <Panel className="px-5 py-5">
          <SectionHeader title="Health checks" as="h3" />
          <EmptyState title="Health checks run on the backend host">
            The backend&rsquo;s sat-sa doctor command checks dependencies, the PQC round trip, the database, key directories and offline posture. This view will show its result once
            GET /api/v1/system/doctor exists.
          </EmptyState>
        </Panel>
      </div>
    </div>
  );
}
