import type { Metadata } from "next";
import Link from "next/link";
import { ChevronDown, Upload } from "lucide-react";
import { CompletenessStrip } from "@/components/domain/entity-bits";
import { Tag } from "@/components/ui/badges";
import { ButtonLink } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/layout";
import { EmptyState } from "@/components/ui/states";
import { can } from "@/lib/auth/permissions";
import { getSession } from "@/lib/auth/session";
import { fmtDate, fmtPeriod, shortDigest, sourceName } from "@/lib/domain/format";
import { CATEGORY_LABEL } from "@/lib/domain/labels";
import { loadCore } from "@/lib/model";

export const metadata: Metadata = { title: "Submissions" };

interface CategoryReport {
  received?: number;
  accepted?: number;
  rejected?: number;
  present?: boolean;
}

export default async function SubmissionsPage() {
  const session = (await getSession())!;
  const core = await loadCore();
  const names = new Map(core.entities.map((e) => [e.id, e.displayName]));

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 md:px-8">
      <PageHeader
        eyebrow="Data"
        title="Submissions"
        description="Periodic CSE submissions as received. Each file is fingerprinted with SHA3-256 and each accepted snapshot is frozen before analysis."
        actions={
          can(session.user.role, "analysis.run") && (
            <ButtonLink href="/workbench/ingest" variant="primary">
              <Upload className="size-4" aria-hidden="true" />
              New submission
            </ButtonLink>
          )
        }
      />
      {core.submissions.length === 0 ? (
        <EmptyState title="No submissions yet" />
      ) : (
        <ul className="space-y-2">
          {core.submissions.map((s) => {
            const cats = ((s.ingestReport.categories ?? {}) as Record<string, CategoryReport>) ?? {};
            const rejected = Object.values(cats).reduce((n, c) => n + (c.rejected ?? 0), 0);
            return (
              <li key={s.id} className="rounded-md border border-line bg-paper">
                <details className="group">
                  <summary className="grid cursor-pointer list-none grid-cols-1 gap-x-6 gap-y-2 px-5 py-4 hover:bg-canvas md:grid-cols-[minmax(0,1fr)_minmax(0,12rem)_7rem_8rem_1rem] md:items-center [&::-webkit-details-marker]:hidden">
                    <span className="min-w-0">
                      <Link href={`/workbench/entities/${s.entityId}`} className="text-[14px] font-semibold text-ink hover:text-brand">
                        {names.get(s.entityId)}
                      </Link>
                      <span className="mt-0.5 block truncate text-[12.5px] text-muted">
                        {sourceName(s.sourceSystem)} · received {fmtDate(s.receivedAt)}
                      </span>
                    </span>
                    <span className="text-[12.5px] text-ink-2">{fmtPeriod(s.declaredPeriodStart, s.declaredPeriodEnd)}</span>
                    <CompletenessStrip submission={s} />
                    <span className="flex items-center gap-1.5">
                      <Tag tone={s.ingestStatus === "accepted" ? "brand" : "attention"}>{s.ingestStatus}</Tag>
                      {rejected > 0 && <Tag tone="attention">{rejected} rejected</Tag>}
                    </span>
                    <ChevronDown className="hidden size-4 text-faint transition-transform group-open:rotate-180 md:block" aria-hidden="true" />
                  </summary>
                  <div className="grid gap-6 border-t border-line bg-canvas/60 px-5 py-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
                    <table className="w-full text-left text-[12.5px]">
                      <caption className="label pb-2 text-left">Files</caption>
                      <thead className="sr-only">
                        <tr>
                          <th scope="col">File</th>
                          <th scope="col">SHA3-256</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(s.fileDigests).map(([file, digest]) => (
                          <tr key={file} className="border-t border-line/70">
                            <td className="py-1.5 pr-4 font-mono text-ink">{file}</td>
                            <td className="py-1.5 font-mono text-muted">{shortDigest(digest, 24)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <table className="w-full text-left text-[12.5px]">
                      <caption className="label pb-2 text-left">Validation</caption>
                      <thead>
                        <tr className="text-muted">
                          <th scope="col" className="pb-1 font-normal">
                            Category
                          </th>
                          <th scope="col" className="pb-1 text-right font-normal">
                            Received
                          </th>
                          <th scope="col" className="pb-1 text-right font-normal">
                            Accepted
                          </th>
                          <th scope="col" className="pb-1 text-right font-normal">
                            Rejected
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(CATEGORY_LABEL).map(([k, label]) => {
                          const c = cats[k];
                          return (
                            <tr key={k} className="border-t border-line/70">
                              <td className="py-1.5 text-ink">{label}</td>
                              <td className="num py-1.5 text-right">{c?.present ? c.received : "not submitted"}</td>
                              <td className="num py-1.5 text-right">{c?.present ? c.accepted : ""}</td>
                              <td className="num py-1.5 text-right">{c?.present ? c.rejected : ""}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <p className="text-[12px] text-muted lg:col-span-2">
                      Snapshot digest <span className="font-mono">{shortDigest(s.snapshotDigest, 24)}</span> · signature status {s.signatureStatus}
                    </p>
                  </div>
                </details>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
