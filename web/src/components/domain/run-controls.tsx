"use client";

import { Loader2, ShieldCheck, XCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { ActionError } from "@/components/ui/api-state";
import { Tag } from "@/components/ui/badges";
import { Button } from "@/components/ui/button";
import type { ApiErrorInfo } from "@/lib/api/errors";
import type { DecisionAction, Verification } from "@/lib/api/types";
import { fmtDateTime } from "@/lib/domain/format";
import { DECISION_ACTION, VERIFICATION_STATUS } from "@/lib/domain/status";
import { cancelRunAction, decideAction, verifyAction } from "@/lib/workbench/actions";
import { cn } from "@/lib/utils";

const ACTIONS: DecisionAction[] = ["confirm", "dismiss", "escalate"];

/**
 * The supervisor's decision on a run awaiting review: POST /runs/{id}/decision.
 * One decision per run; the backend rejects other roles (403), a different
 * second decision (409) and runs that are not awaiting review (422).
 */
export function DecisionForm({ runId }: { runId: string }) {
  const router = useRouter();
  const [action, setAction] = useState<DecisionAction | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  const [pending, start] = useTransition();

  const submit = () =>
    start(async () => {
      if (!action) return;
      setError(null);
      const r = await decideAction(runId, action, reason.trim());
      if (!r.ok) setError(r.error);
      else router.refresh();
    });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      aria-label="Record the supervisory decision"
    >
      <fieldset>
        <legend className="label mb-2">Decision</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {ACTIONS.map((a) => (
            <label
              key={a}
              className={cn(
                "cursor-pointer rounded-md border px-3 py-2.5 transition-colors",
                action === a ? "border-brand bg-brand-tint" : "border-line bg-paper hover:border-ink/40",
              )}
            >
              <input type="radio" name="action" value={a} className="sr-only" checked={action === a} onChange={() => setAction(a)} />
              <span className="block text-[13.5px] font-semibold text-ink">{DECISION_ACTION[a].label}</span>
              <span className="mt-0.5 block text-[12px] leading-snug text-muted">{DECISION_ACTION[a].help}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <label htmlFor={`reason-${runId}`} className="label mt-4 mb-1.5 block">
        Reason
      </label>
      <textarea
        id={`reason-${runId}`}
        name="reason"
        value={reason}
        maxLength={4000}
        rows={3}
        onChange={(e) => setReason(e.target.value)}
        className="w-full rounded-md border border-line-2 bg-paper px-3 py-2 text-[13.5px] text-ink focus:border-brand focus:ring-2 focus:ring-brand/20 focus:outline-none"
        placeholder="What the evidence showed and why this decision follows"
      />
      <div className="mt-3 flex items-center gap-3">
        <Button type="submit" variant="primary" disabled={!action || pending}>
          {pending && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          Record decision
        </Button>
        <span className="text-[12px] text-muted">Recorded once, bound to your identity, then signed by TRUST-SAT.</span>
      </div>
      <ActionError error={error} />
    </form>
  );
}

/** POST /runs/{id}/verify: rebuilds the signed state and checks signature and ledger. */
export function VerifyButton({ runId }: { runId: string }) {
  const [result, setResult] = useState<Verification | null>(null);
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  const [pending, start] = useTransition();
  return (
    <div>
      <Button
        size="sm"
        disabled={pending}
        onClick={() =>
          start(async () => {
            setError(null);
            const r = await verifyAction(runId);
            if (r.ok) setResult(r.data);
            else setError(r.error);
          })
        }
      >
        {pending ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : <ShieldCheck className="size-3.5" aria-hidden="true" />}
        Verify now
      </Button>
      {result && (
        <div role="status" className="mt-3 space-y-1" data-verification={result.status}>
          <Tag tone={VERIFICATION_STATUS[result.status].tone}>{VERIFICATION_STATUS[result.status].label}</Tag>
          <p className="text-[12.5px] text-ink-2">{result.message}</p>
          <p className="text-[12px] text-muted">
            {VERIFICATION_STATUS[result.status].detail} Checked {fmtDateTime(result.verified_at)}.
          </p>
        </div>
      )}
      <ActionError error={error} />
    </div>
  );
}

/** POST /runs/{id}/cancel (supervisor or administrator): cooperative cancellation. */
export function CancelRunButton({ runId }: { runId: string }) {
  const router = useRouter();
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  const [pending, start] = useTransition();
  return (
    <div>
      <Button
        size="sm"
        variant="ghost"
        disabled={pending}
        onClick={() =>
          start(async () => {
            setError(null);
            const r = await cancelRunAction(runId);
            if (r.ok) router.refresh();
            else setError(r.error);
          })
        }
      >
        <XCircle className="size-3.5" aria-hidden="true" />
        Request cancellation
      </Button>
      <ActionError error={error} />
    </div>
  );
}
