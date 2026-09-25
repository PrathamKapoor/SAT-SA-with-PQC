import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface PipelineStage {
  key: string;
  label: string;
  value: ReactNode;
  detail?: ReactNode;
  state: "ok" | "attention" | "idle" | "failed";
}

const DOT: Record<PipelineStage["state"], string> = {
  ok: "bg-ink",
  attention: "bg-attention",
  idle: "bg-line-2",
  failed: "bg-critical",
};

const STATE_TEXT: Record<PipelineStage["state"], string> = {
  ok: "complete",
  attention: "needs attention",
  idle: "not started",
  failed: "failed",
};

/** The SAT-SA flow as counted stages, left to right (or stacked when narrow). */
export function PipelineStrip({ stages, orientation = "horizontal", label }: { stages: PipelineStage[]; orientation?: "horizontal" | "vertical"; label: string }) {
  if (orientation === "vertical") {
    return (
      <ol aria-label={label} className="relative space-y-3">
        <span aria-hidden="true" className="absolute top-2 bottom-2 left-[3px] w-px bg-line" />
        {stages.map((s) => (
          <li key={s.key} className="relative grid grid-cols-[0.5rem_minmax(0,1fr)_auto] items-baseline gap-3">
            <span aria-hidden="true" className={cn("relative top-[-1px] size-[7px] rounded-full ring-2 ring-paper", DOT[s.state])} />
            <span className="min-w-0 truncate text-[13px] text-ink-2">
              {s.label}
              <span className="sr-only">, {STATE_TEXT[s.state]}</span>
              {s.detail && <span className="block truncate text-[11.5px] text-muted">{s.detail}</span>}
            </span>
            <span className="num text-[13px] font-semibold text-ink">{s.value}</span>
          </li>
        ))}
      </ol>
    );
  }
  return (
    <ol aria-label={label} className="flex flex-wrap items-stretch gap-y-3">
      {stages.map((s, i) => (
        <li key={s.key} className="flex min-w-0 items-center">
          {i > 0 && <ArrowRight className="mx-2.5 size-3.5 shrink-0 text-faint" aria-hidden="true" />}
          <div className="min-w-0">
            <p className="label flex items-center gap-1.5">
              <span aria-hidden="true" className={cn("size-1.5 rounded-full", DOT[s.state])} />
              {s.label}
              <span className="sr-only">, {STATE_TEXT[s.state]}</span>
            </p>
            <p className="num mt-0.5 text-[18px] leading-tight font-semibold text-ink">{s.value}</p>
            {s.detail && <p className="text-[11.5px] text-muted">{s.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
