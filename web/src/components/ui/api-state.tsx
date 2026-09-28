"use client";

import { RotateCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";
import { present, type ApiErrorInfo } from "@/lib/api/errors";

/** A backend error as the SAT-SA API reported it: what failed, retry if useful, request ID for tracing. */
export function ApiErrorPanel({ error, className, context }: { error: ApiErrorInfo; className?: string; context?: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  const p = present(error);
  return (
    <div className={className}>
      <ErrorState title={context ? `${context}: ${p.title}` : p.title}>
        <p>{p.message}</p>
        {error.requestId && (
          <p className="mt-1 font-mono text-[11.5px] text-muted">
            Request {error.requestId}
            {error.status ? ` · HTTP ${error.status} ${error.code}` : ""}
          </p>
        )}
      </ErrorState>
      {p.retry && (
        <Button className="mt-3" size="sm" disabled={pending} onClick={() => start(() => router.refresh())}>
          <RotateCw className={pending ? "size-3.5 animate-spin" : "size-3.5"} aria-hidden="true" />
          Try again
        </Button>
      )}
    </div>
  );
}

/** Inline form-level error for server-action results. */
export function ActionError({ error }: { error: ApiErrorInfo | null }) {
  if (!error) return null;
  const p = present(error);
  return (
    <div role="alert" className="mt-3 rounded-md border border-critical/30 bg-critical-tint px-3 py-2 text-[13px]">
      <p className="font-medium text-critical">{p.title}</p>
      <p className="mt-0.5 text-ink-2">{p.message}</p>
      {error.requestId && <p className="mt-0.5 font-mono text-[11.5px] text-muted">Request {error.requestId}</p>}
    </div>
  );
}
