import { cn } from "@/lib/utils";

const STAGES = [
  { key: "observe", label: "Observe", detail: "Collect the run's observations and findings" },
  { key: "reason", label: "Reason", detail: "Select the strongest signal and its bounded recommendation" },
  { key: "act", label: "Act", detail: "Propose an action from the SAT-SA vocabulary" },
  { key: "verify", label: "Verify", detail: "Check the proposal requires human authority" },
  { key: "learn", label: "Learn", detail: "Append the decision to the lineage log" },
];

/**
 * satsa/supervisor/engine.py: one engine, five stages. A SAT-SA proposal is
 * never executed; it is surfaced for a human supervisor to decide.
 */
export function SupervisionLoop({ activeAction, className }: { activeAction?: string; className?: string }) {
  return (
    <figure className={cn("w-full", className)}>
      <ol className="grid grid-cols-1 gap-px overflow-hidden rounded-md border border-line bg-line sm:grid-cols-5" aria-label="Supervisor engine stages">
        {STAGES.map((s, i) => (
          <li key={s.key} className="relative bg-paper px-4 py-4">
            <span className="label text-faint">{String(i + 1).padStart(2, "0")}</span>
            <p className="mt-1 text-[15px] font-semibold text-ink">{s.label}</p>
            <p className="mt-1 text-[12.5px] leading-snug text-muted">{s.detail}</p>
            {s.key === "act" && activeAction && <p className="mt-2 font-mono text-[11.5px] text-brand-strong">{activeAction}</p>}
          </li>
        ))}
      </ol>
      <figcaption className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-[12.5px] text-muted">
        <span>
          <span className="font-medium text-ink-2">SAT-SA vocabulary</span>: surface, inspect, request evidence, escalate for review, defer, accept, close review.
          Every action requires a human.
        </span>
        <span>
          <span className="font-medium text-ink-2">MLOps vocabulary</span>: policy proposals for the ML platform (deploy, retrain, quarantine, rotate keys).
        </span>
      </figcaption>
    </figure>
  );
}
