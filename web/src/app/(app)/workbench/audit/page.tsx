import type { Metadata } from "next";
import Link from "next/link";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { DataTable } from "@/components/ui/data";
import { PageHeader } from "@/components/ui/layout";
import { offsetOf, Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { load } from "@/lib/api/guard";
import type { AuditEvent } from "@/lib/api/types";
import { fmtDateTime } from "@/lib/domain/format";

export const metadata: Metadata = { title: "Audit" };

export default async function AuditPage({ searchParams }: { searchParams: Promise<{ run?: string; offset?: string }> }) {
  const sp = await searchParams;
  const run = sp.run && /^[A-Za-z0-9_-]{1,128}$/.test(sp.run) ? sp.run : undefined;
  const loaded = await load(() => api.auditEvents({ run_id: run, offset: offsetOf(sp.offset), limit: 50 }));

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Trust"
        title="Audit"
        description="The organization's audit events and its members' sign-in and sign-out events, as the SAT-SA service recorded them."
        meta={
          run ? (
            <span className="text-[12.5px] text-muted">
              Filtered to run <span className="mono-id">{run}</span>.{" "}
              <Link href="/workbench/audit" className="text-brand hover:underline">
                Show all
              </Link>
            </span>
          ) : undefined
        }
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Audit events" />
      ) : (
        <>
          <DataTable
            caption="Audit events"
            rows={loaded.data.items}
            rowKey={(e) => e.event_id}
            dense
            empty={<EmptyState title="No audit events" />}
            columns={[
              { key: "time", header: "Time", cell: (e: AuditEvent) => fmtDateTime(e.timestamp) },
              { key: "action", header: "Action", cell: (e: AuditEvent) => <span className="font-mono text-[12px] text-ink">{e.action}</span> },
              { key: "resource", header: "Resource", cell: (e: AuditEvent) => <span className="mono-id">{e.resource}</span> },
              { key: "actor", header: "Actor", cell: (e: AuditEvent) => <span className="mono-id">{e.actor}</span> },
              { key: "result", header: "Result", cell: (e: AuditEvent) => <Tag tone={e.result === "SUCCESS" ? "neutral" : "attention"}>{e.result}</Tag> },
            ]}
          />
          <Pager page={loaded.data} path="/workbench/audit" params={{ run }} label="Audit event pages" />
        </>
      )}
    </div>
  );
}
