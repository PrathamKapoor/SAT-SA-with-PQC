import { CircleSlash } from "lucide-react";
import { fmtDuration, fmtTime } from "@/lib/domain/format";
import { CATEGORY_LABEL, subjectKind } from "@/lib/domain/labels";
import { alertLifecycle, STAGE_LABEL, type StageKey } from "@/lib/domain/lifecycle";
import { EVIDENCE_CATEGORIES, type SecurityData, type Submission } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

const STAGES: StageKey[] = ["raised", "acknowledged", "investigated", "escalated", "dispositioned", "closed"];

function offset(from: number, to: number | null) {
  if (to == null) return null;
  const d = to - from;
  return d === 0 ? "0s" : `+${fmtDuration(d)}`;
}

/**
 * The operational sequence behind a finding, reconstructed from the
 * submitted records the finding is scoped to.
 */
export function EvidenceLifecycle({ subjects, data, submission }: { subjects: string[]; data: SecurityData; submission: Submission | null }) {
  const kinds = new Set(subjects.map(subjectKind));

  if (kinds.has("alert")) {
    const alerts = subjects.map((id) => data.alerts.find((a) => a.id === id)).filter((a): a is NonNullable<typeof a> => Boolean(a));
    const lifecycles = alerts.map((a) => alertLifecycle(a, data)).slice(0, 8);
    const missingCounts = STAGES.map((k) => lifecycles.filter((l) => l.stages.find((s) => s.key === k)?.state === "missing").length);
    return (
      <div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] table-fixed border-collapse text-left">
            <caption className="sr-only">Lifecycle of each alert in this finding. A stage with no submitted record is marked missing.</caption>
            <thead>
              <tr>
                <th scope="col" className="label w-20 pb-2 font-normal">
                  Alert
                </th>
                {STAGES.map((k, i) => (
                  <th key={k} scope="col" className="pb-2 font-normal">
                    <span className="label block">{STAGE_LABEL[k]}</span>
                    <span className={cn("block font-mono text-[10.5px]", missingCounts[i] ? "text-attention" : "text-transparent")}>
                      {missingCounts[i] ? `${missingCounts[i]}/${lifecycles.length} missing` : "."}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {lifecycles.map((l) => (
                <tr key={l.alert.id} className="border-t border-line/70">
                  <th scope="row" className="py-2.5 pr-3 align-top font-normal">
                    <span className="block font-mono text-[12.5px] font-medium text-ink">{l.alert.nativeId}</span>
                    <span className="block text-[11px] text-muted capitalize">{l.alert.mappedSeverity}</span>
                  </th>
                  {l.stages.map((s, i) => (
                    <td key={s.key} className="py-3 align-top">
                      <span aria-hidden="true" className="relative flex h-3 items-center">
                        {i > 0 && (
                          <span
                            className={cn("absolute right-[calc(100%-6px)] h-0 w-full border-t", s.state === "missing" ? "border-dashed border-attention/60" : "border-ink/30")}
                          />
                        )}
                        {s.state === "present" ? (
                          <span className="relative z-10 size-2.5 rounded-full bg-ink ring-2 ring-paper" />
                        ) : (
                          <CircleSlash className="relative z-10 size-3 bg-paper text-attention" />
                        )}
                      </span>
                      <span className={cn("mt-1.5 block text-[12px]", s.state === "present" ? "text-ink" : "font-medium text-attention-strong")}>
                        {s.state === "present" ? (s.key === "raised" ? fmtTime(s.at) : offset(l.alert.createdAt, s.at)) : "None"}
                        <span className="sr-only">{s.state === "missing" ? `, missing: ${s.detail}` : s.detail ? `, ${s.detail}` : ""}</span>
                      </span>
                      {s.state === "present" && s.detail && s.key !== "raised" && <span className="block truncate pr-2 text-[11px] text-muted">{s.detail}</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[12px] text-muted">
          Times are offsets from when each alert was raised (UTC). &ldquo;None&rdquo; means the submission contains no record for that stage.
          {alerts.length > lifecycles.length && ` Showing ${lifecycles.length} of ${alerts.length} alerts.`}
        </p>
      </div>
    );
  }

  if (kinds.has("case")) {
    const cases = subjects.map((id) => data.cases.find((c) => c.id === id)).filter((c): c is NonNullable<typeof c> => Boolean(c));
    return (
      <ul className="divide-y divide-line/70">
        {cases.map((c) => {
          const steps = data.investigationSteps.filter((s) => s.caseId === c.id).sort((a, b) => a.sequence - b.sequence);
          const esc = data.escalations.find((e) => e.caseId === c.id);
          return (
            <li key={c.id} className="grid gap-3 py-3 sm:grid-cols-[6rem_minmax(0,1fr)]">
              <div>
                <p className="font-mono text-[12.5px] font-medium text-ink">{c.nativeId}</p>
                <p className="text-[11px] text-muted">
                  {c.status} · {c.alertRefs.length} alert{c.alertRefs.length === 1 ? "" : "s"}
                </p>
              </div>
              <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px]" aria-label={`Case ${c.nativeId} sequence`}>
                <li className="text-ink">Opened {fmtTime(c.openedAt)}</li>
                {steps.length ? (
                  steps.map((s) => (
                    <li key={s.id} className="text-ink-2">
                      <span aria-hidden="true" className="text-faint">
                        →{" "}
                      </span>
                      {s.actionType}
                      {s.noteText && <span className="text-muted"> &ldquo;{s.noteText}&rdquo;</span>}
                    </li>
                  ))
                ) : (
                  <li className="font-medium text-attention-strong">→ no investigation step</li>
                )}
                <li className={esc ? "text-ink-2" : "text-attention-strong"}>→ {esc ? `escalated to ${esc.destinationRole}` : "no escalation"}</li>
                <li className="text-ink">→ {c.closedAt ? `closed +${fmtDuration(c.closedAt - c.openedAt)}` : "still open"}</li>
              </ol>
            </li>
          );
        })}
      </ul>
    );
  }

  if (kinds.has("asset")) {
    const assets = subjects.map((id) => data.assets.find((a) => a.id === id)).filter((a): a is NonNullable<typeof a> => Boolean(a));
    return (
      <ul className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {assets.map((a) => {
          const alerts = data.alerts.filter((x) => x.assetRefs.includes(a.id)).length;
          return (
            <li key={a.id} className="rounded-sm border border-line px-3 py-2.5">
              <p className="font-mono text-[12.5px] font-medium text-ink">{a.nativeId}</p>
              <p className="mt-0.5 text-[11.5px] text-muted capitalize">
                {a.criticality} · {a.environment || "no environment"}
              </p>
              <p className={cn("mt-2 text-[12.5px]", alerts ? "text-ink-2" : "font-medium text-attention-strong")}>
                {alerts} alert{alerts === 1 ? "" : "s"} in period
              </p>
            </li>
          );
        })}
      </ul>
    );
  }

  if (kinds.has("invstep")) {
    const steps = subjects.map((id) => data.investigationSteps.find((s) => s.id === id)).filter((s): s is NonNullable<typeof s> => Boolean(s));
    return (
      <ul className="divide-y divide-line/70">
        {steps.map((s) => (
          <li key={s.id} className="flex items-baseline justify-between gap-4 py-2 text-[12.5px]">
            <span className="text-ink">
              {s.actionType} <span className="text-muted">&ldquo;{s.noteText || "no note"}&rdquo;</span>
            </span>
            <span className="mono-id">{s.analystPseudonym}</span>
          </li>
        ))}
      </ul>
    );
  }

  if (kinds.has("entity") && submission) {
    return (
      <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {EVIDENCE_CATEGORIES.map((c) => {
          const n = submission.declaredCounts[c] ?? 0;
          return (
            <li key={c} className={cn("rounded-sm border px-3 py-2", n ? "border-line" : "border-dashed border-attention/50 bg-attention-tint/50")}>
              <p className="text-[12.5px] font-medium text-ink">{CATEGORY_LABEL[c]}</p>
              <p className={cn("num text-[12px]", n ? "text-muted" : "font-medium text-attention-strong")}>{n ? `${n} records` : "Not submitted"}</p>
            </li>
          );
        })}
      </ul>
    );
  }

  return <p className="text-[13px] text-muted">This finding is scoped to the entity as a whole; there is no per-record sequence to reconstruct.</p>;
}
