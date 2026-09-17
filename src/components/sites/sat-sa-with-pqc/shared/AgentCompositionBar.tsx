import { StatNumber } from "./StatNumber";

interface AgentCompositionBarProps {
  mlops: number;
  satsa: number;
  className?: string;
}

const MLOPS_COLOR = "#3987e5";
const SATSA_COLOR = "#7c3aed";

/** A 100%-stacked bar: retained MLOps agents vs SAT-SA supervisory agents. Both segments are
 * always directly labelled, so the two fixed hues never have to carry meaning alone. */
export function AgentCompositionBar({ mlops, satsa, className }: AgentCompositionBarProps) {
  const total = mlops + satsa;
  const mlopsPct = (mlops / total) * 100;
  const satsaPct = (satsa / total) * 100;

  return (
    <div className={className}>
      <div className="flex h-24 w-full overflow-hidden rounded-4" role="img" aria-label={`${mlops} retained MLOps agents and ${satsa} SAT-SA supervisory agents, of ${total} total`}>
        <div style={{ width: `${mlopsPct}%`, backgroundColor: MLOPS_COLOR }} />
        <div className="ml-2" style={{ width: `${satsaPct}%`, backgroundColor: SATSA_COLOR }} />
      </div>
      <div className="mt-12 flex items-center justify-between font-mono text-ui uppercase">
        <span className="flex items-center gap-6 text-dark-grey">
          <span aria-hidden="true" className="size-8 rounded-full" style={{ backgroundColor: MLOPS_COLOR }} />
          <StatNumber value={mlops} className="text-white" /> retained mlops
        </span>
        <span className="flex items-center gap-6 text-dark-grey">
          <span aria-hidden="true" className="size-8 rounded-full" style={{ backgroundColor: SATSA_COLOR }} />
          <StatNumber value={satsa} className="text-white" /> sat-sa supervisory
        </span>
      </div>
    </div>
  );
}
