import { CATEGORY_LABEL, DIMENSION_LABEL, DIMENSION_ORDER } from "@/lib/domain/labels";
import { fmtNum } from "@/lib/domain/format";
import { EVIDENCE_CATEGORIES, type RiskDimension, type Submission } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

/** Seven dimension cells; fill depth = score / weight. A compact risk signature. */
export function RiskSignature({ dimensions, className }: { dimensions: RiskDimension[]; className?: string }) {
  const by = new Map(dimensions.map((d) => [d.name, d]));
  return (
    <ul aria-label="Risk signature by dimension" className={cn("flex gap-[3px]", className)}>
      {DIMENSION_ORDER.map((name) => {
        const d = by.get(name);
        const ratio = d && d.weight ? d.score / d.weight : 0;
        return (
          <li
            key={name}
            title={`${DIMENSION_LABEL[name]}: ${fmtNum(d?.score ?? 0, 1)} of ${d?.weight ?? 0}`}
            className="relative h-7 w-3.5 overflow-hidden rounded-[2px] bg-sunken"
          >
            <span
              aria-hidden="true"
              className={cn("absolute inset-x-0 bottom-0", ratio > 0.66 ? "bg-attention" : "bg-brand")}
              style={{ height: `${Math.round(ratio * 100)}%` }}
            />
            <span className="sr-only">
              {DIMENSION_LABEL[name]} {fmtNum(d?.score ?? 0, 1)} of {d?.weight ?? 0}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Six evidence categories: present (count) or missing. */
export function CompletenessStrip({ submission, className, showLabels = false }: { submission: Submission | null; className?: string; showLabels?: boolean }) {
  if (!submission) return <p className="text-[12px] text-muted">No submission</p>;
  return (
    <ul aria-label="Evidence categories submitted" className={cn(showLabels ? "grid grid-cols-2 gap-1.5 sm:grid-cols-3" : "flex gap-[3px]", className)}>
      {EVIDENCE_CATEGORIES.map((c) => {
        const n = submission.declaredCounts[c] ?? 0;
        return showLabels ? (
          <li key={c} className={cn("flex items-center justify-between rounded-sm border px-2.5 py-1.5 text-[12.5px]", n ? "border-line" : "border-dashed border-attention/50 bg-attention-tint/40")}>
            <span className={n ? "text-ink-2" : "text-attention-strong"}>{CATEGORY_LABEL[c]}</span>
            <span className={cn("num font-medium", n ? "text-ink" : "text-attention-strong")}>{n || "Missing"}</span>
          </li>
        ) : (
          <li key={c} title={`${CATEGORY_LABEL[c]}: ${n ? `${n} records` : "missing"}`} className={cn("size-3.5 rounded-[2px]", n ? "bg-ink/70" : "border border-dashed border-attention bg-paper")}>
            <span className="sr-only">
              {CATEGORY_LABEL[c]} {n ? `${n} records` : "missing"}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
