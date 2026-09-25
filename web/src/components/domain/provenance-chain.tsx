import { Check, CircleDashed, X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ProvenanceNode {
  key: string;
  stage: string;
  title: ReactNode;
  ref?: ReactNode;
  state: "verified" | "present" | "pending" | "failed";
  note?: ReactNode;
}

const STATE_LABEL: Record<ProvenanceNode["state"], string> = {
  verified: "Verified",
  present: "Recorded",
  pending: "Pending",
  failed: "Failed",
};

/**
 * source -> record -> observation -> finding -> risk -> recommendation -> decision.
 * Each link shows what exists and what was cryptographically checked.
 */
export function ProvenanceChain({ nodes, label }: { nodes: ProvenanceNode[]; label: string }) {
  return (
    <ol aria-label={label} className="relative">
      {nodes.map((n, i) => (
        <li key={n.key} className="relative grid grid-cols-[1.5rem_7.5rem_minmax(0,1fr)_auto] items-start gap-x-3 pb-4 last:pb-0">
          {i < nodes.length - 1 && (
            <span aria-hidden="true" className={cn("absolute top-6 bottom-0 left-[11px] w-px", n.state === "pending" ? "border-l border-dashed border-line-2" : "bg-line-2")} />
          )}
          <span
            aria-hidden="true"
            className={cn(
              "relative z-10 mt-0.5 flex size-[22px] items-center justify-center rounded-full border",
              n.state === "verified" && "border-brand bg-brand text-white",
              n.state === "present" && "border-ink/60 bg-paper text-ink",
              n.state === "pending" && "border-dashed border-line-2 bg-paper text-faint",
              n.state === "failed" && "border-critical bg-critical text-white",
            )}
          >
            {n.state === "verified" || n.state === "present" ? (
              <Check className="size-3" strokeWidth={2.5} />
            ) : n.state === "failed" ? (
              <X className="size-3" strokeWidth={2.5} />
            ) : (
              <CircleDashed className="size-3" />
            )}
          </span>
          <span className="label pt-1">{n.stage}</span>
          <span className="min-w-0 pt-0.5">
            <span className="block truncate text-[13px] font-medium text-ink">{n.title}</span>
            {n.ref && <span className="mono-id block truncate">{n.ref}</span>}
            {n.note && <span className="mt-0.5 block text-[11.5px] text-muted">{n.note}</span>}
          </span>
          <span
            className={cn(
              "pt-1 text-[11.5px] font-medium",
              n.state === "verified" ? "text-brand-strong" : n.state === "failed" ? "text-critical" : n.state === "pending" ? "text-faint" : "text-ink-2",
            )}
          >
            {STATE_LABEL[n.state]}
          </span>
        </li>
      ))}
    </ol>
  );
}
