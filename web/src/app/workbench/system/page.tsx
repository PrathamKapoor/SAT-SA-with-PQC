import type { Metadata } from "next";
import { Tag } from "@/components/ui/badges";
import { KeyValue, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { apiBase, health } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { can, ROLE_LABEL } from "@/lib/auth/permissions";
import { fmtDateTime } from "@/lib/domain/format";

export const metadata: Metadata = { title: "System" };

export default async function SystemPage() {
  const ctx = await requireContext();
  const status = await health().catch(() => null);

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader eyebrow="Admin" title="System" description="Where this interface gets its data, whether the SAT-SA service is ready, and how your session is established." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel className="px-5 py-5">
          <SectionHeader title="SAT-SA service" />
          <KeyValue
            columns={1}
            items={[
              ...(can(ctx.role, "config.manage") ? [["API (internal address)", <span key="a" className="mono-id">{apiBase()}</span>] as [string, React.ReactNode]] : []),
              [
                "Liveness (GET /health/live)",
                status ? <Tag key="l" tone={status.live ? "brand" : "critical"}>{status.live ? "alive" : "not responding"}</Tag> : <Tag key="l" tone="critical">unreachable</Tag>,
              ],
              [
                "Readiness (GET /health/ready)",
                status ? (
                  <Tag key="r" tone={status.ready ? "brand" : "attention"}>{status.ready ? "ready" : `not ready (HTTP ${status.readyStatus})`}</Tag>
                ) : (
                  <Tag key="r" tone="critical">unreachable</Tag>
                ),
              ],
            ]}
          />
          <p className="mt-4 text-[12.5px] text-muted">
            Readiness covers the database, the schema version, the TRUST-SAT signing key and artifact storage. The worker has its own check on its host.
          </p>
        </Panel>
        <Panel className="px-5 py-5">
          <SectionHeader title="Session" as="h3" />
          <KeyValue
            columns={1}
            items={[
              ["Signed in as", ctx.session.name],
              ["Identity", <span key="i" className="mono-id">{ctx.session.identity_id}</span>],
              ["Organization", ctx.organization.name],
              ["Role in this organization", ROLE_LABEL[ctx.role] ?? ctx.role],
              ["Session expires", fmtDateTime(ctx.session.expires_at)],
              ["Stored in the browser", "A revocable session token in an HttpOnly cookie. The credential is not kept."],
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}
