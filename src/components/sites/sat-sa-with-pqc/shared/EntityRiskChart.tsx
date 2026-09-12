"use client";

import { useId, useState } from "react";
import { cn } from "@/lib/utils";
import type { EntityRisk } from "@/components/sites/sat-sa-with-pqc/root/content/demo";

/** Fixed status palette (never re-themed) — icon + label always pairs with the color. */
const STATUS = {
  low: { color: "#0ca30c", label: "Low risk" },
  medium: { color: "#fab219", label: "Medium risk" },
} as const;

interface EntityRiskChartProps {
  data: readonly EntityRisk[];
  className?: string;
}

/**
 * Horizontal bar chart of live entity risk scores (0–100), coloured by risk band. A hover
 * tooltip shows the score's top contributor. Direct labels throughout, so colour never carries
 * meaning alone.
 */
export function EntityRiskChart({ data, className }: EntityRiskChartProps) {
  const [hovered, setHovered] = useState<number | null>(null);
  const uid = useId();
  const usedBands = Array.from(new Set(data.map((d) => d.band)));

  return (
    <div className={cn("relative", className)}>
      <ul className="flex flex-col gap-10" role="list" aria-label="Entities ranked by supervisory risk">
        {data.map((row, i) => {
          const status = STATUS[row.band];
          const active = hovered === i;
          return (
            <li key={row.entity} className="relative">
              <div className="mb-4 flex items-baseline justify-between gap-8 font-mono text-ui uppercase">
                <span className="text-white">
                  {String(row.rank).padStart(2, "0")} {row.entity}
                </span>
                <span className="tabular-nums text-dark-grey">{row.score}/100</span>
              </div>
              <div
                className="group relative h-14 w-full cursor-default rounded-2 bg-white/[0.06]"
                onMouseEnter={() => setHovered(i)}
                onMouseLeave={() => setHovered(null)}
                onFocus={() => setHovered(i)}
                onBlur={() => setHovered(null)}
                tabIndex={0}
                role="img"
                aria-label={`${row.entity}: ${row.score} of 100, ${status.label}. Top contributor: ${row.topContributor}.`}
                aria-describedby={active ? `${uid}-tip-${i}` : undefined}
              >
                <div
                  className="h-full rounded-r-4 transition-[filter] duration-150 group-hover:brightness-125"
                  style={{ width: `${row.score}%`, backgroundColor: status.color }}
                />
              </div>
              {active ? (
                <div
                  role="tooltip"
                  id={`${uid}-tip-${i}`}
                  className="pointer-events-none absolute top-full left-0 z-10 mt-6 w-max max-w-320 rounded-4 border border-white/15 bg-black-deep px-10 py-8 font-mono text-ui text-ghost-grey shadow-lg"
                >
                  <span className="text-white">{row.topContributor}</span>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
      <div className="mt-16 flex flex-wrap items-center gap-16 border-white/10 border-t pt-12 font-mono text-ui text-dark-grey uppercase">
        {usedBands.map((band) => (
          <span key={band} className="flex items-center gap-6">
            <span aria-hidden="true" className="size-8 rounded-full" style={{ backgroundColor: STATUS[band].color }} />
            {STATUS[band].label}
          </span>
        ))}
      </div>
    </div>
  );
}
