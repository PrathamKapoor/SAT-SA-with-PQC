"use client";

import { Check, FlaskConical, Lock } from "lucide-react";
import { useState, useTransition } from "react";
import { ReviewStatusTag } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import { fmtDateTime, shortDigest } from "@/lib/domain/format";
import { BACKEND_ACTION_LABEL, REVIEW_ACTIONS, STATUS_FOR_ACTION, type ReviewActionKey } from "@/lib/domain/review";
import { recordReview } from "@/lib/review-actions";
import { useReviewStore } from "@/lib/review-store";
import type { ReviewDecision } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

export interface ReviewPanelProps {
  findingId: string;
  contentDigest: string;
  canRecord: boolean;
  roleLabel: string;
  sessionMode: "development" | "backend";
  history: ReviewDecision[];
}

/** Supervisory review: the human terminal authority for a finding. */
export function ReviewPanel({ findingId, contentDigest, canRecord, roleLabel, sessionMode, history }: ReviewPanelProps) {
  const store = useReviewStore();
  const [selected, setSelected] = useState<ReviewActionKey | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const devHistory = store.decisions.filter((d) => d.findingId === findingId);
  const def = REVIEW_ACTIONS.find((a) => a.key === selected);
  const latest = history.at(-1)?.action ?? devHistory.at(-1)?.action;

  const submit = () => {
    if (!def?.backend) return;
    if (!reason.trim()) {
      setError("Record the rationale for this decision.");
      return;
    }
    setError(null);
    const action = def.backend;
    if (sessionMode === "development") {
      store.record({ findingId, action, reason: reason.trim(), role: roleLabel, findingContentDigest: contentDigest });
      setSelected(null);
      setReason("");
      return;
    }
    start(async () => {
      const r = await recordReview({ findingId, action, reason: reason.trim(), findingContentDigest: contentDigest });
      if (!r.ok) setError(r.error ?? "Not recorded.");
      else {
        setSelected(null);
        setReason("");
      }
    });
  };

  return (
    <section aria-labelledby="review-h" className="rounded-md border border-line bg-paper">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 id="review-h" className="text-[14px] font-semibold text-ink">
          Supervisory review
        </h2>
        <ReviewStatusTag status={latest ? STATUS_FOR_ACTION[latest] : "awaiting"} />
      </div>

      <div className="px-4 py-4">
        {!canRecord ? (
          <p className="flex items-start gap-2 text-[12.5px] leading-relaxed text-muted">
            <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            Your role ({roleLabel}) can read this finding but cannot record a decision. Supervisors and administrators hold that authority.
          </p>
        ) : (
          <>
            <fieldset>
              <legend className="label mb-2">Decision</legend>
              <div className="grid grid-cols-2 gap-1.5">
                {REVIEW_ACTIONS.map((a) => {
                  const unsupported = a.backend === null;
                  const active = selected === a.key;
                  return (
                    <button
                      key={a.key}
                      type="button"
                      disabled={unsupported}
                      aria-pressed={active}
                      title={a.hint}
                      onClick={() => setSelected(active ? null : a.key)}
                      className={cn(
                        "flex h-9 items-center justify-center gap-1.5 rounded-sm border text-[13px] font-medium transition-colors",
                        active && a.tone === "primary" && "border-ink bg-ink text-white",
                        active && a.tone === "attention" && "border-attention bg-attention text-white",
                        active && a.tone === "neutral" && "border-ink bg-sunken text-ink",
                        !active && "border-line-2 bg-paper text-ink-2 hover:border-ink/40 hover:text-ink",
                        unsupported && "border-dashed text-faint hover:border-line-2 hover:text-faint",
                      )}
                    >
                      {active && <Check className="size-3.5" aria-hidden="true" />}
                      {a.label}
                    </button>
                  );
                })}
              </div>
              <p className="mt-2 text-[11.5px] text-muted">Defer and False positive need backend support and are not recorded.</p>
            </fieldset>

            {def && (
              <div className="mt-4 animate-rise">
                <label htmlFor="review-reason" className="text-[12.5px] font-medium text-ink">
                  Rationale <span className="font-normal text-muted">(required)</span>
                </label>
                <textarea
                  id="review-reason"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  rows={3}
                  aria-invalid={error ? true : undefined}
                  aria-describedby="review-binding"
                  className="mt-1.5 w-full resize-y rounded-sm border border-line-2 bg-paper px-2.5 py-2 text-[13px] leading-relaxed focus:border-brand focus:ring-2 focus:ring-brand/15 focus:outline-none"
                  placeholder="What in the evidence supports this decision?"
                />
                {error && (
                  <p role="alert" className="mt-1 text-[12px] text-critical">
                    {error}
                  </p>
                )}
                <p id="review-binding" className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
                  Recorded as <span className="font-mono">{def.backend}</span> and bound to content digest{" "}
                  <span className="font-mono">{shortDigest(contentDigest)}</span>.
                </p>
                <Button variant={def.tone === "attention" ? "attention" : "primary"} className="mt-3 w-full" onClick={submit} disabled={pending}>
                  {pending ? "Recording" : `Record: ${def.label}`}
                </Button>
              </div>
            )}

            {sessionMode === "development" && (
              <p className="mt-4 flex items-start gap-2 rounded-sm bg-attention-tint px-2.5 py-2 text-[11.5px] leading-relaxed text-attention-strong">
                <FlaskConical className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                Development session: decisions are kept in this browser only and are not a backend record.
              </p>
            )}
          </>
        )}
      </div>

      <div className="border-t border-line px-4 py-3">
        <h3 className="label mb-2">Decision history</h3>
        {history.length === 0 && devHistory.length === 0 ? (
          <p className="text-[12.5px] text-muted">No decision has been recorded for this finding.</p>
        ) : (
          <ol className="space-y-2.5">
            {history.map((d) => (
              <li key={d.id} className="text-[12.5px]">
                <p className="font-medium text-ink">
                  {BACKEND_ACTION_LABEL[d.action]} <span className="font-normal text-muted">by {d.principalIdentityId}</span>
                </p>
                <p className="text-muted">{d.reason}</p>
                <p className="mono-id">{fmtDateTime(d.occurredAt)}</p>
              </li>
            ))}
            {devHistory.map((d) => (
              <li key={d.id} className="border-l-2 border-attention/40 pl-2.5 text-[12.5px]">
                <p className="font-medium text-ink">
                  {BACKEND_ACTION_LABEL[d.action]} <span className="font-normal text-muted">({d.role}, development)</span>
                </p>
                <p className="text-muted">{d.reason}</p>
                <p className="mono-id">{fmtDateTime(d.occurredAt)}</p>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}
