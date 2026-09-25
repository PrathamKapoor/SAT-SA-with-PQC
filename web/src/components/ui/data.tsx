import type { ReactNode } from "react";
import { CONFIDENCE_BUCKET_LABEL, DIMENSION_LABEL, DIMENSION_ORDER } from "@/lib/domain/labels";
import { fmtNum, fmtPct } from "@/lib/domain/format";
import type { ConfidenceVector, RiskDimension } from "@/lib/types/domain";
import { cn } from "@/lib/utils";

/** Thin horizontal meter. Always paired with a printed value. */
export function Meter({ value, max = 1, tone = "brand", className, label }: { value: number | null; max?: number; tone?: "brand" | "info" | "attention" | "ink" | "critical"; className?: string; label: string }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(1, value / max)) * 100;
  const color = { brand: "bg-brand", info: "bg-info", attention: "bg-attention", ink: "bg-ink", critical: "bg-critical" }[tone];
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value ?? undefined}
      aria-valuetext={value == null ? "not applicable" : undefined}
      className={cn("h-1.5 w-full overflow-hidden rounded-[1px] bg-sunken", className)}
    >
      {value != null && <div className={cn("h-full rounded-[1px]", color)} style={{ width: `${pct}%` }} />}
    </div>
  );
}

/** Compact overall-confidence readout for rows and cards. */
export function ConfidenceInline({ confidence, className }: { confidence: ConfidenceVector | null; className?: string }) {
  if (!confidence) return <span className={cn("text-[12.5px] text-faint", className)}>n/a</span>;
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="num w-9 text-right text-[12.5px] font-medium text-ink">{fmtPct(confidence.overall)}</span>
      <Meter value={confidence.overall} label="Overall confidence" className="w-12" />
    </span>
  );
}

/** Full confidence vector. Peer confidence of null is "not applicable", never zero. */
export function ConfidenceDisplay({ confidence }: { confidence: ConfidenceVector | null }) {
  if (!confidence) return <p className="text-[13px] text-muted">The detector did not attach a confidence vector to this finding.</p>;
  const rows: Array<[string, number | null, string]> = [
    ["Analytical support", confidence.analytical_support, "How strongly the statistic supports the signal"],
    ["Evidence completeness", confidence.evidence_completeness, "Share of the relevant evidence that was present"],
    ["Peer confidence", confidence.peer_confidence, confidence.peer_confidence == null ? "Not applicable: no peer cohort for this rule" : "Confidence in the peer comparison"],
  ];
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className="num text-[36px] leading-none font-semibold tracking-[-0.03em] text-ink">{fmtPct(confidence.overall)}</span>
        <span className="label">overall</span>
      </div>
      <dl className="mt-4 space-y-3">
        {rows.map(([label, value, hint]) => (
          <div key={label}>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-[13px] text-ink-2">{label}</dt>
              <dd className={cn("num text-[13px] font-medium", value == null ? "text-faint" : "text-ink")}>{value == null ? "n/a" : fmtPct(value)}</dd>
            </div>
            <Meter value={value} label={label} tone="ink" className="mt-1.5" />
            <p className="mt-1 text-[12px] text-muted">{hint}</p>
          </div>
        ))}
      </dl>
    </div>
  );
}

/** Risk score out of 100 with confidence bucket. */
export function RiskScore({ score, bucket, size = "md" }: { score: number | null; bucket?: string; size?: "sm" | "md" | "lg" }) {
  const scale = { sm: "text-[18px]", md: "text-[28px]", lg: "text-[48px]" }[size];
  return (
    <span className="inline-flex items-baseline gap-1.5">
      <span className={cn("num leading-none font-semibold tracking-[-0.03em] text-ink", scale)}>{score == null ? "n/a" : fmtNum(score, 1)}</span>
      <span className="text-[12px] text-muted">/100</span>
      {bucket && <span className="label ml-1">{CONFIDENCE_BUCKET_LABEL[bucket] ?? bucket} conf.</span>}
    </span>
  );
}

/**
 * The seven weighted risk dimensions. Bar length is the dimension's weight
 * (its ceiling); the filled part is the scored contribution.
 */
export function RiskBreakdown({ dimensions, compact = false }: { dimensions: RiskDimension[]; compact?: boolean }) {
  const byName = new Map(dimensions.map((d) => [d.name, d]));
  const maxWeight = Math.max(...dimensions.map((d) => d.weight), 1);
  return (
    <ul className={cn(compact ? "space-y-1.5" : "space-y-2.5")} aria-label="Risk dimensions">
      {DIMENSION_ORDER.map((name) => {
        const d = byName.get(name);
        if (!d) return null;
        const filled = d.weight ? d.score / d.weight : 0;
        return (
          <li key={name} className="grid grid-cols-[minmax(0,9.5rem)_1fr_3.25rem] items-center gap-3">
            <span className={cn("truncate text-[12.5px]", d.score > 0 ? "text-ink" : "text-faint")}>{DIMENSION_LABEL[name]}</span>
            <span className="relative h-2" style={{ width: `${(d.weight / maxWeight) * 100}%` }}>
              <span className="absolute inset-0 rounded-[1px] bg-sunken" />
              <span
                className={cn("absolute inset-y-0 left-0 rounded-[1px]", filled > 0.66 ? "bg-attention" : "bg-brand")}
                style={{ width: `${filled * 100}%` }}
              />
            </span>
            <span className="num text-right text-[12px] text-muted">
              <span className="font-medium text-ink">{fmtNum(d.score, 1)}</span>/{d.weight}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
  align?: "left" | "right";
}

/** Accessible table: caption, scoped headers, no zebra noise. */
export function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  empty,
  className,
  dense = false,
}: {
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  empty?: ReactNode;
  className?: string;
  dense?: boolean;
}) {
  if (!rows.length && empty) return <>{empty}</>;
  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full border-collapse text-left text-[13px]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line">
            {columns.map((c) => (
              <th key={c.key} scope="col" className={cn("label py-2 pr-4 font-normal whitespace-nowrap", c.align === "right" && "text-right", c.className)}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="border-b border-line/70 last:border-0 hover:bg-canvas/70">
              {columns.map((c) => (
                <td key={c.key} className={cn(dense ? "py-1.5" : "py-2.5", "pr-4 align-top text-ink-2", c.align === "right" && "text-right", c.className)}>
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export interface TimelineItem {
  id: string;
  title: ReactNode;
  at?: ReactNode;
  detail?: ReactNode;
  state?: "done" | "missing" | "current";
}

export function Timeline({ items, label }: { items: TimelineItem[]; label: string }) {
  return (
    <ol aria-label={label} className="relative space-y-4 border-l border-line pl-5">
      {items.map((it) => (
        <li key={it.id} className="relative">
          <span
            aria-hidden="true"
            className={cn(
              "absolute top-1 -left-[25px] size-2.5 rounded-full border-2 border-paper",
              it.state === "missing" ? "bg-paper ring-1 ring-attention" : it.state === "current" ? "bg-brand" : "bg-ink",
            )}
          />
          <div className="flex flex-wrap items-baseline justify-between gap-x-4">
            <p className="text-[13.5px] font-medium text-ink">
              {it.title}
              {it.state === "missing" && <span className="sr-only"> (missing)</span>}
            </p>
            {it.at && <p className="mono-id">{it.at}</p>}
          </div>
          {it.detail && <div className="mt-0.5 text-[13px] text-muted">{it.detail}</div>}
        </li>
      ))}
    </ol>
  );
}
