import type { Metadata } from "next";
import { ScrollText } from "lucide-react";
import { Metric, PageHeader, Panel, SectionHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { getSource } from "@/lib/api";
import { can } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { fmtPct } from "@/lib/domain/format";

export const metadata: Metadata = { title: "Audit" };

export default async function AuditPage() {
  const session = (await getSession())!;
  if (!can(session.user.role, "audit.read")) {
    return (
      <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
        <EmptyState title="The audit log requires the auditor or administrator role" />
      </div>
    );
  }
  const audit = await getSource().getMetaAudit();

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Trust"
        title="Audit"
        description="A database-wide sweep of trust coverage: every run, finding and review decision checked against its receipt or binding, plus the decision ledger."
      />
      {audit ? (
        <>
          <Panel className="px-5 py-5">
            <dl className="grid grid-cols-2 gap-6 md:grid-cols-4">
              <Metric label="Overall" value={audit.fully_compliant ? "Compliant" : "Exceptions"} tone={audit.fully_compliant ? "brand" : "critical"} size="sm" />
              <Metric label="Runs verified" value={`${audit.runs_ok}/${audit.runs_checked}`} detail={`coverage ${fmtPct(audit.run_coverage)}`} />
              <Metric label="Findings verified" value={`${audit.findings_ok}/${audit.findings_checked}`} detail={`coverage ${fmtPct(audit.finding_coverage)}`} />
              <Metric label="Review bindings" value={`${audit.reviews_ok}/${audit.reviews_checked}`} detail={audit.reviews_checked ? `coverage ${fmtPct(audit.review_coverage)}` : "no decisions yet"} />
            </dl>
          </Panel>

          <section aria-labelledby="exc-h" className="mt-8">
            <SectionHeader id="exc-h" title="Exceptions" />
            {[...audit.runs_failed, ...audit.findings_failed, ...audit.reviews_failed].length ? (
              <Panel className="px-5 py-3">
                <ul className="divide-y divide-line text-[13px]">
                  {audit.runs_failed.map((r) => (
                    <li key={r.run_id} className="py-2">
                      Run <span className="font-mono">{r.run_id}</span>: {r.reason}
                    </li>
                  ))}
                  {audit.findings_failed.map((f) => (
                    <li key={f.finding_id} className="py-2">
                      Finding <span className="font-mono">{f.finding_id}</span>: {f.reason}
                    </li>
                  ))}
                </ul>
              </Panel>
            ) : (
              <p className="text-[13px] text-muted">No run, finding or review failed verification.</p>
            )}
          </section>
        </>
      ) : (
        <EmptyState title="No audit report available" />
      )}

      <section aria-labelledby="log-h" className="mt-8">
        <SectionHeader id="log-h" title="Platform audit log" />
        <EmptyState title="Audit events are not exposed yet" icon={<ScrollText className="size-5" />}>
          The backend records security and identity events (qsmlops.security.audit) but does not yet serve them over the API. This view will list them once
          GET /api/v1/audit/events exists.
        </EmptyState>
      </section>
    </div>
  );
}
