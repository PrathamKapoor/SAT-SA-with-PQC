import type { Metadata } from "next";
import { Check, Minus, Users } from "lucide-react";
import { KeyValue, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { getSource } from "@/lib/api";
import { can, ROLE_LABEL, ROLE_SUMMARY, ROLES_IN_ORDER, type Permission } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { DIMENSION_LABEL, DIMENSION_ORDER } from "@/lib/domain/labels";

export const metadata: Metadata = { title: "Administration" };

const PERMS: Array<[Permission, string]> = [
  ["finding.view", "View findings"],
  ["evidence.view", "View evidence"],
  ["trust.verify", "Verify trust"],
  ["analysis.run", "Run analysis and ingest"],
  ["report.export", "Export reports"],
  ["decision.record", "Record decisions"],
  ["calibration.approve", "Approve calibration"],
  ["audit.read", "Read audit log"],
  ["identity.manage", "Manage identities"],
  ["config.manage", "Manage configuration"],
];

export default async function AdminPage() {
  const session = (await getSession())!;
  if (!can(session.user.role, "identity.manage")) {
    return (
      <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
        <EmptyState title="Administration requires the administrator role" />
      </div>
    );
  }
  const weights = await getSource().getRiskWeights();

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Admin"
        title="Administration"
        description="Identities, roles and platform settings. The backend enforces every permission; this interface only reflects them."
      />

      <section aria-labelledby="users-h">
        <SectionHeader id="users-h" title="Users" />
        <EmptyState title="Identity management is not exposed over the API yet" icon={<Users className="size-5" />}>
          Identities and credentials exist in the backend (qsmlops.security.identity), created today with the bootstrap procedure in docs/deployment.md. This list, and issuing or
          revoking credentials, will use GET and POST /api/v1/identities once they exist.
        </EmptyState>
      </section>

      <section aria-labelledby="roles-h" className="mt-10">
        <SectionHeader id="roles-h" title="Roles and permissions" aside="mirrors the backend role model" />
        <Panel className="overflow-x-auto px-5 py-3">
          <table className="w-full min-w-[46rem] text-left text-[12.5px]">
            <caption className="sr-only">Permissions granted to each SAT-SA role</caption>
            <thead>
              <tr className="border-b border-line">
                <th scope="col" className="label py-2 font-normal">
                  Permission
                </th>
                {ROLES_IN_ORDER.map((r) => (
                  <th key={r} scope="col" className="py-2 text-center font-medium text-ink">
                    {ROLE_LABEL[r]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PERMS.map(([p, label]) => (
                <tr key={p} className="border-b border-line/60 last:border-0">
                  <th scope="row" className="py-2 font-normal text-ink-2">
                    {label} <span className="mono-id ml-1">{p}</span>
                  </th>
                  {ROLES_IN_ORDER.map((r) => (
                    <td key={r} className="py-2 text-center">
                      {can(r, p) ? <Check className="mx-auto size-4 text-brand" aria-label="granted" /> : <Minus className="mx-auto size-4 text-line-2" aria-label="not granted" />}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
        <ul className="mt-3 grid gap-x-6 gap-y-1 text-[12px] text-muted sm:grid-cols-2 lg:grid-cols-3">
          {ROLES_IN_ORDER.map((r) => (
            <li key={r}>
              <span className="font-medium text-ink-2">{ROLE_LABEL[r]}</span>: {ROLE_SUMMARY[r]}
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="model-h" className="mt-10 grid gap-6 lg:grid-cols-2">
        <Panel className="px-5 py-5">
          <SectionHeader id="model-h" title="Risk weights" aside="read only" />
          <KeyValue columns={2} items={DIMENSION_ORDER.map((d) => [DIMENSION_LABEL[d], weights[d] ?? "n/a"])} />
          <p className="mt-4 text-[12px] leading-relaxed text-muted">
            Weights are a starting hypothesis pending domain calibration. Detector thresholds change only through the governed calibration workflow (sat-sa calibrate: propose, test,
            approve, deploy), which requires calibration approval.
          </p>
        </Panel>
        <Panel className="px-5 py-5">
          <SectionHeader title="Platform configuration" as="h3" />
          <EmptyState title="Configuration is file-based">
            Settings live in configs/settings.*.yaml on the host and are not editable from the interface. A read-only view will use GET /api/v1/system/config.
          </EmptyState>
        </Panel>
      </section>
    </div>
  );
}
