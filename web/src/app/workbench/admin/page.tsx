import type { Metadata } from "next";
import { InviteMember, RevokeMember } from "@/components/domain/members-admin";
import { ApiErrorPanel } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { DataTable } from "@/components/ui/data";
import { PageHeader, SectionHeader } from "@/components/ui/layout";
import { offsetOf, Pager } from "@/components/ui/pager";
import { EmptyState } from "@/components/ui/states";
import { api } from "@/lib/api/client";
import { requireContext } from "@/lib/api/context";
import { load } from "@/lib/api/guard";
import type { Member } from "@/lib/api/types";
import { ROLE_LABEL } from "@/lib/auth/permissions";

export const metadata: Metadata = { title: "Members" };

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ offset?: string }> }) {
  const ctx = await requireContext();
  const offset = offsetOf((await searchParams).offset);
  const loaded = await load(() => api.members({ offset, limit: 50 }));

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Admin"
        title="Members"
        description={`Who can work in ${ctx.organization.name}, and in which role. Roles decide what the SAT-SA service allows; the workbench only mirrors them.`}
      />
      {!loaded.ok ? (
        <ApiErrorPanel error={loaded.error} context="Members" />
      ) : (
        <div className="space-y-10">
          <section aria-labelledby="invite-h">
            <SectionHeader id="invite-h" title="Add a member" />
            <InviteMember />
          </section>
          <section aria-labelledby="members-h">
            <SectionHeader id="members-h" title="Members" />
            <DataTable
              caption="Organization members"
              rows={loaded.data.items}
              rowKey={(m) => m.id}
              empty={<EmptyState title="No members" />}
              columns={[
                { key: "name", header: "Name", cell: (m: Member) => <span className="font-medium text-ink">{m.name}</span> },
                { key: "email", header: "Email", cell: (m: Member) => m.email },
                { key: "role", header: "Role", cell: (m: Member) => ROLE_LABEL[m.role] ?? m.role },
                { key: "status", header: "Status", cell: (m: Member) => <Tag tone={m.status === "active" ? "neutral" : "attention"}>{m.status}</Tag> },
                { key: "identity", header: "Identity", cell: (m: Member) => <span className="mono-id">{m.identity_id}</span> },
                {
                  key: "actions",
                  header: <span className="sr-only">Actions</span>,
                  align: "right",
                  cell: (m: Member) => (m.status === "active" && m.id !== ctx.session.user_id ? <RevokeMember userId={m.id} name={m.name} /> : null),
                },
              ]}
            />
            <Pager page={loaded.data} path="/workbench/admin" label="Member pages" />
          </section>
        </div>
      )}
    </div>
  );
}
