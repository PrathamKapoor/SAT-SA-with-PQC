"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { ActionError } from "@/components/ui/api-state";
import { Button } from "@/components/ui/button";
import type { ActionResult, ApiErrorInfo } from "@/lib/api/errors";
import type { MLDataset } from "@/lib/api/types";
import {
  acceptRetrainingAction,
  approveModelAction,
  createDatasetAction,
  deployModelAction,
  dismissRetrainingAction,
  driftCheckAction,
  requestRetrainingAction,
  retireModelAction,
  rollbackModelAction,
  startTrainingAction,
  validateDatasetAction,
} from "@/lib/workbench/actions";

/**
 * Model lifecycle controls. Each one calls a single API route through a server
 * action; the backend decides whether the caller may do it (403), whether the
 * lifecycle allows it (409/422), and job routes are idempotent per key.
 */

function useAction() {
  const router = useRouter();
  const [error, setError] = useState<ApiErrorInfo | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const run = <T,>(action: () => Promise<ActionResult<T>>, done?: string) =>
    start(async () => {
      setError(null);
      setNotice(null);
      const r = await action();
      if (!r.ok) setError(r.error);
      else {
        if (done) setNotice(done);
        router.refresh();
      }
    });
  return { error, notice, pending, run };
}

function Spinner({ on }: { on: boolean }) {
  return on ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : null;
}

function Feedback({ error, notice }: { error: ApiErrorInfo | null; notice: string | null }) {
  return (
    <>
      <ActionError error={error} />
      {notice && (
        <p role="status" className="mt-2 text-[12.5px] text-muted">
          {notice}
        </p>
      )}
    </>
  );
}

/** One idempotency key per mounted control: a repeated click reuses it. */
function useKey(prefix: string) {
  const [key] = useState(() => `${prefix}-${crypto.randomUUID()}`);
  return key;
}

export function CreateDatasetButton() {
  const { error, notice, pending, run } = useAction();
  return (
    <div>
      <Button variant="primary" disabled={pending} onClick={() => run(() => createDatasetAction("review-outcome"), "Dataset version recorded.")}>
        <Spinner on={pending} />
        Build dataset from recorded decisions
      </Button>
      <Feedback error={error} notice={notice} />
    </div>
  );
}

export function DatasetJobButton({ datasetId, kind }: { datasetId: string; kind: "validate" | "train" }) {
  const { error, notice, pending, run } = useAction();
  const key = useKey(`${kind}-${datasetId}`);
  const label = kind === "validate" ? "Validate" : "Train model";
  return (
    <div>
      <Button
        variant={kind === "train" ? "primary" : "secondary"}
        size="sm"
        disabled={pending}
        onClick={() =>
          run(
            () => (kind === "validate" ? validateDatasetAction(datasetId, key) : startTrainingAction(datasetId, key)),
            "Queued for the worker. Refresh to see the result.",
          )
        }
      >
        <Spinner on={pending} />
        {label}
      </Button>
      <Feedback error={error} notice={notice} />
    </div>
  );
}

export function DriftCheckButton() {
  const { error, notice, pending, run } = useAction();
  const key = useKey("drift");
  return (
    <div>
      <Button size="sm" disabled={pending} onClick={() => run(() => driftCheckAction(key), "Drift check queued.")}>
        <Spinner on={pending} />
        Check drift now
      </Button>
      <Feedback error={error} notice={notice} />
    </div>
  );
}

type ReasonKind = "approve" | "deploy" | "retire" | "rollback" | "request" | "dismiss";

const REASON_FORM: Record<ReasonKind, { label: string; field: string; required: boolean; variant: "primary" | "secondary" | "attention" }> = {
  approve: { label: "Approve for deployment", field: "Justification", required: true, variant: "primary" },
  deploy: { label: "Deploy", field: "Reason (optional)", required: false, variant: "primary" },
  retire: { label: "Retire", field: "Reason", required: true, variant: "secondary" },
  rollback: { label: "Roll back to previous approved model", field: "Reason", required: true, variant: "attention" },
  request: { label: "Request retraining", field: "Reason", required: true, variant: "secondary" },
  dismiss: { label: "Dismiss request", field: "Reason", required: true, variant: "secondary" },
};

export function ReasonAction({ kind, id }: { kind: ReasonKind; id?: string }) {
  const { error, notice, pending, run } = useAction();
  const [text, setText] = useState("");
  const spec = REASON_FORM[kind];
  const action = (): Promise<ActionResult<unknown>> => {
    const reason = text.trim();
    switch (kind) {
      case "approve":
        return approveModelAction(id!, reason);
      case "deploy":
        return deployModelAction(id!, reason);
      case "retire":
        return retireModelAction(id!, reason);
      case "rollback":
        return rollbackModelAction(reason);
      case "request":
        return requestRetrainingAction(reason);
      case "dismiss":
        return dismissRetrainingAction(id!, reason);
    }
  };
  const inputId = `${kind}-${id ?? "org"}`;
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        run(action);
      }}
      aria-label={spec.label}
    >
      <label htmlFor={inputId} className="label mb-1 block">
        {spec.field}
      </label>
      <textarea
        id={inputId}
        value={text}
        rows={2}
        maxLength={2000}
        onChange={(e) => setText(e.target.value)}
        className="w-full rounded-md border border-line-2 bg-paper px-3 py-2 text-[13px] text-ink focus:border-brand focus:ring-2 focus:ring-brand/20 focus:outline-none"
      />
      <Button type="submit" variant={spec.variant} size="sm" className="mt-2" disabled={pending || (spec.required && !text.trim())}>
        <Spinner on={pending} />
        {spec.label}
      </Button>
      <Feedback error={error} notice={notice} />
    </form>
  );
}

export function AcceptRetrainingForm({ requestId, datasets }: { requestId: string; datasets: MLDataset[] }) {
  const { error, notice, pending, run } = useAction();
  const [datasetId, setDatasetId] = useState(datasets[0]?.id ?? "");
  const key = useKey(`accept-${requestId}`);
  if (!datasets.length) {
    return <p className="text-[12.5px] text-muted">Accepting starts retraining and needs a validated dataset version.</p>;
  }
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        run(() => acceptRetrainingAction(requestId, datasetId, key), "Retraining queued. The new model will still need approval.");
      }}
      aria-label="Accept and start retraining"
    >
      <label htmlFor={`ds-${requestId}`} className="label mb-1 block">
        Training dataset
      </label>
      <select
        id={`ds-${requestId}`}
        value={datasetId}
        onChange={(e) => setDatasetId(e.target.value)}
        className="w-full rounded-md border border-line-2 bg-paper px-2 py-1.5 text-[13px] text-ink"
      >
        {datasets.map((d) => (
          <option key={d.id} value={d.id}>
            {d.name} v{d.version} · {d.record_count} runs · {d.data_origin}
          </option>
        ))}
      </select>
      <Button type="submit" variant="primary" size="sm" className="mt-2" disabled={pending || !datasetId}>
        <Spinner on={pending} />
        Accept and start retraining
      </Button>
      <Feedback error={error} notice={notice} />
    </form>
  );
}
